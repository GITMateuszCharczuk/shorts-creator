"""python -m shorts.stage <id> --run-dir <dir> --seed <n> [--config <json>]"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

from shared.ctx import Degraded, Quarantined, StageContext
from shared.exitcodes import EXIT_DEGRADED, EXIT_HELD, EXIT_OK, EXIT_QUARANTINED
from shared.obs.metrics import render_stage_liveness, write_metrics
from shared.stage import REGISTRY, default_path
from stages.registry import load_all


class Heartbeat:
    """Daemon thread that rewrites a JSON heartbeat file every *interval_s* seconds.

    The file contains ``{"ts": <epoch float>}`` and is written atomically via a
    temp-file + os.replace so a reader never sees a partial write.  The thread
    stops (and the file timestamp freezes) as soon as :meth:`stop` is called,
    allowing an external stuck-detector to observe that the age is no longer
    advancing.

    When *prom_path* is supplied, each tick ALSO writes a Prometheus textfile gauge
    (``shorts_stage_running 1`` + the same heartbeat_timestamp) so a crashed/hung
    subprocess leaves ``running=1`` with an aging heartbeat — which is what the
    StageStuck alert reads.  :meth:`stop` then overwrites it with ``running=0`` so a
    cleanly-finished stage never false-pages.  The conductor's metered() post-completion
    write targets the SAME .prom file and is the authoritative final record.
    """

    def __init__(self, path: Path, interval_s: float = 30.0, *,
                 prom_path: Path | None = None, batch_id: str = "", stage: str = "",
                 video_id: str = "") -> None:
        self._path = Path(path)
        self._interval_s = interval_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._prom_path = Path(prom_path) if prom_path is not None else None
        self._batch_id = batch_id
        self._stage = stage
        self._video_id = video_id
        self._last_ts = 0.0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background daemon thread; writes the file immediately."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="heartbeat")
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        # A clean stop overwrites the in-flight gauge with running=0 (last ts preserved) so a
        # completed stage never trips StageStuck. metered() later overwrites the same file.
        if self._prom_path is not None:
            write_metrics(self._prom_path, render_stage_liveness(
                batch_id=self._batch_id, stage=self._stage, video_id=self._video_id,
                running=0, heartbeat_ts=self._last_ts))

    def read_ts(self) -> float:
        """Return the ``ts`` value from the heartbeat file, or 0.0 if absent."""
        try:
            return json.loads(self._path.read_text())["ts"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return 0.0

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while True:
            self._write()
            # wait up to interval_s; returns True immediately if stop was called
            if self._stop_event.wait(self._interval_s):
                break  # stop requested

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.time()
        self._last_ts = ts
        payload = json.dumps({"ts": ts})
        # atomic write: write to a sibling temp file then replace
        dir_ = str(self._path.parent)
        fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            os.write(fd, payload.encode())
        finally:
            os.close(fd)
        os.replace(tmp, self._path)
        # In-flight Prometheus gauge: running=1 with the SAME ts just written, so a crashed
        # subprocess leaves running=1 + an aging heartbeat for StageStuck to fire on.
        if self._prom_path is not None:
            write_metrics(self._prom_path, render_stage_liveness(
                batch_id=self._batch_id, stage=self._stage, video_id=self._video_id,
                running=1, heartbeat_ts=ts))


def resolve_argo_args(*, data_root, batch_id: str, video_id: str, stage_id: str) -> dict:
    """Argo mode (ADR 0015a B): address a stage by (batch, video); resolve the explicit run-dir,
    per-video seed, and config from the planner's batch.json on the PVC — so ``--batch/--video``
    and the M4 ``--run-dir/--seed/--config`` mode run the IDENTICAL stage body.

    The returned ``config`` carries the full stage_cmd contract
    (shared/conductor/subproc.stage_cmd):
    ``input_paths``/``output_paths`` are derived HERE from the stage manifest's declared
    inputs/outputs via the SAME ``default_path`` mapping the in-process runner uses. Argo shares
    one PVC run-dir per video, so an input's path equals its producer's output path — both sides
    derive from ``default_path``. Without this the IO gate in ``main()`` would ``p.error`` (exit 2)
    on every Argo pod (C3)."""
    batch = json.loads((Path(data_root) / "runs" / batch_id / "batch.json").read_text())
    video = next((v for v in batch["videos"] if v["video_id"] == video_id), None)
    if video is None:
        raise KeyError(f"video {video_id!r} not in batch {batch_id!r}")
    run_dir = str(Path(data_root) / "runs" / batch_id / video_id)
    manifest = REGISTRY[stage_id].manifest
    return {"run_dir": run_dir, "seed": video["seed"],
            "config": {"niche": video["niche"], "format": video.get("format"),
                       "input_paths": {n: default_path(n) for n in manifest.inputs},
                       "output_paths": {n: default_path(n) for n in manifest.outputs}}}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage_id")
    # Explicit mode (M4 / Variant A conductor): all three are required together.
    p.add_argument("--run-dir")
    p.add_argument("--seed", type=int)
    p.add_argument("--config", default="{}")
    # Argo mode (M7 / Variant B): address by (batch, video); resolves run-dir + seed from PVC.
    p.add_argument("--batch")
    p.add_argument("--video")
    a = p.parse_args()

    if (a.batch is None) != (a.video is None):
        p.error("--batch and --video must be given together (Argo mode)")
    argo_mode = a.batch is not None and a.video is not None

    if argo_mode:
        # Resolve run_dir + seed + niche/format from the planner's batch.json on the PVC.
        # DATA_ROOT is the mount-point of the Argo PVC (set by the Argo workflow template at
        # bring-up; absent in CI / explicit mode).
        resolved = resolve_argo_args(
            data_root=os.environ["DATA_ROOT"],
            batch_id=a.batch,
            video_id=a.video,
            stage_id=a.stage_id,
        )
        run_dir = Path(resolved["run_dir"])
        seed = resolved["seed"]
        # IO-path resolution in Argo mode (C3): resolve_argo_args derives input_paths/output_paths
        # from the stage manifest's declared inputs/outputs via the SAME default_path mapping the
        # in-process runner uses — one PVC run-dir per video means an input's path equals its
        # producer's output path. The Argo template therefore does NOT need to carry --config; the
        # full stage_cmd contract (input_paths/output_paths + niche/format) is built HERE, so the
        # IO gate below passes and the stage body runs instead of aborting (p.error / exit 2).
        # Any explicit --config (default "{}") is layered UNDER the resolved values so an operator
        # override can still set stage_config/backends without clobbering the derived IO paths.
        cfg = {**json.loads(a.config), **resolved["config"]}
    else:
        # Explicit mode (M4 / Variant A): --run-dir and --seed are required.
        if a.run_dir is None:
            p.error("--run-dir is required (explicit mode) unless --batch/--video are both given")
        if a.seed is None:
            p.error("--seed is required (explicit mode) unless --batch/--video are both given")
        run_dir = Path(a.run_dir)
        seed = a.seed
        cfg = json.loads(a.config)

    load_all()
    reg = REGISTRY[a.stage_id]
    job = json.loads((run_dir / "job.json").read_text())
    for key in ("input_paths", "output_paths"):
        if key not in cfg:          # fail loud, not KeyError-deep (the stage_cmd contract)
            p.error(f"--config JSON must contain {key!r} "
                    f"(shape: shared/conductor/subproc.stage_cmd)")
    ctx = StageContext(stage=a.stage_id, run_dir=run_dir, seed=seed, job=job,
                      config=cfg.get("stage_config", {}),
                      input_paths=cfg["input_paths"], output_paths=cfg["output_paths"],
                      backends=_build_backends(cfg, job))
    from stages.s06_distribute.stage import HeldForReview
    # In-flight gauge emission only when the conductor passed a textfile dir at bring-up (absent
    # in CI/offline -> JSON heartbeat only). The .prom filename MUST match metered()'s convention
    # (textfile_dir / f"{video_id}-{stage_id}.prom") so the post-completion write overwrites it.
    textfile_dir = cfg.get("textfile_dir")
    prom_path = (Path(textfile_dir) / f"{job['video_id']}-{a.stage_id}.prom"
                 if textfile_dir else None)
    hb = Heartbeat(run_dir / ".heartbeat" / f"{a.stage_id}.json", prom_path=prom_path,
                   batch_id=job.get("batch_id", ""), stage=a.stage_id,
                   video_id=job.get("video_id", ""))
    hb.start()
    try:
        reg.fn(ctx)
    except HeldForReview:
        return EXIT_HELD
    except Quarantined:
        return EXIT_QUARANTINED
    except Degraded:
        return EXIT_DEGRADED
    else:
        return EXIT_OK
    finally:
        hb.stop()


def _build_backends(cfg: dict, job: dict):
    # resolved from config: real Ollama/ComfyUI/Kokoro/QwenVL clients per capability (M1-M3),
    # or the fixture fakes when cfg["backends"] == "fake" (CI / the offline DAG).
    from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter
    if cfg.get("backends") == "fake":
        be = FixtureBackend(fixtures_dir=Path(cfg["fixtures_dir"]))
        caps = ["llm", "generate_image", "img2vid", "tts", "vlm_judge", "restore"]
        # 06 expects a dict[platform, adapter] (one DistributionAdapter per platform, Task 13)
        dist = {p: FixtureDistributionAdapter(p)
                for p in job.get("platform_targets", ["youtube"])}
        return {**{c: be for c in caps}, "distribution": dist}
    # real wiring resolves per-stage via shared.config.resolve_config (ADR 0010 D5)
    raise NotImplementedError("real-backend wiring lands at host bring-up; CI uses backends=fake")


if __name__ == "__main__":
    sys.exit(main())
