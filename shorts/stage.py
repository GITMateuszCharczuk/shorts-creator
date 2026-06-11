"""python -m shorts.stage <id> --run-dir <dir> --seed <n> [--config <json>]"""
import argparse
import json
import sys
from pathlib import Path

from shared.ctx import Degraded, Quarantined, StageContext
from shared.exitcodes import EXIT_DEGRADED, EXIT_OK, EXIT_QUARANTINED
from shared.stage import REGISTRY
from stages.registry import load_all


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
                      backends=_build_backends(cfg))
    try:
        reg.fn(ctx)
    except Quarantined:
        return EXIT_QUARANTINED
    except Degraded:
        return EXIT_DEGRADED
    return EXIT_OK


def _build_backends(cfg: dict):
    # resolved from config: real Ollama/ComfyUI/Kokoro/QwenVL clients per capability (M1-M3),
    # or the fixture fakes when cfg["backends"] == "fake" (CI / the offline DAG).
    from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter
    if cfg.get("backends") == "fake":
        be = FixtureBackend(fixtures_dir=Path(cfg["fixtures_dir"]))
        caps = ["llm", "generate_image", "img2vid", "tts", "vlm_judge", "restore"]
        return {**{c: be for c in caps}, "distribution": FixtureDistributionAdapter()}
    # real wiring resolves per-stage via shared.config.resolve_config (ADR 0010 D5)
    raise NotImplementedError("real-backend wiring lands at host bring-up; CI uses backends=fake")


if __name__ == "__main__":
    sys.exit(main())
