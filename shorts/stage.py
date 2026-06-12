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
from shared.stage import REGISTRY
from stages.registry import load_all


class Heartbeat:
    """Daemon thread that rewrites a JSON heartbeat file every *interval_s* seconds.

    The file contains ``{"ts": <epoch float>}`` and is written atomically via a
    temp-file + os.replace so a reader never sees a partial write.  The thread
    stops (and the file timestamp freezes) as soon as :meth:`stop` is called,
    allowing an external stuck-detector to observe that the age is no longer
    advancing.
    """

    def __init__(self, path: Path, interval_s: float = 30.0) -> None:
        self._path = Path(path)
        self._interval_s = interval_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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
        payload = json.dumps({"ts": time.time()})
        # atomic write: write to a sibling temp file then replace
        dir_ = str(self._path.parent)
        fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            os.write(fd, payload.encode())
        finally:
            os.close(fd)
        os.replace(tmp, self._path)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage_id")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--config", default="{}")
    a = p.parse_args()
    load_all()
    reg = REGISTRY[a.stage_id]
    run_dir = Path(a.run_dir)
    job = json.loads((run_dir / "job.json").read_text())
    cfg = json.loads(a.config)
    for key in ("input_paths", "output_paths"):
        if key not in cfg:          # fail loud, not KeyError-deep (the stage_cmd contract)
            p.error(f"--config JSON must contain {key!r} "
                    f"(shape: shared/conductor/subproc.stage_cmd)")
    ctx = StageContext(stage=a.stage_id, run_dir=run_dir, seed=a.seed, job=job,
                      config=cfg.get("stage_config", {}),
                      input_paths=cfg["input_paths"], output_paths=cfg["output_paths"],
                      backends=_build_backends(cfg, job))
    from stages.s06_distribute.stage import HeldForReview
    hb = Heartbeat(run_dir / ".heartbeat" / f"{a.stage_id}.json")
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
