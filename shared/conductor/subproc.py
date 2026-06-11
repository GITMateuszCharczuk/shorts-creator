import subprocess
import sys
import time
from dataclasses import dataclass

from shared.exitcodes import status_for_exit


@dataclass(frozen=True)
class StageOutcome:
    status: str          # done | quarantined | failed
    exit_code: int
    elapsed_s: float
    timed_out: bool = False


def stage_cmd(stage_id: str, *, run_dir: str, seed: int, config_json: str) -> list[str]:
    """config_json contract (enforced by shorts/stage.py): {"input_paths": {...},
    "output_paths": {...}, "stage_config": {...}, "backends": "fake"|"real",
    "fixtures_dir": "..."} — input_paths/output_paths are REQUIRED."""
    return [sys.executable, "-m", "shorts.stage", stage_id,
            "--run-dir", run_dir, "--seed", str(seed), "--config", config_json]


def run_stage_subprocess(*, cmd: list[str], timeout_s: float) -> StageOutcome:
    """Real per-stage timeout + crash isolation (ADR 0015 D6). `start_new_session` puts the
    stage in its OWN process group so a timeout kills its ffmpeg/helper grandchildren too —
    a leaked GPU helper would silently violate never-co-resident."""
    import os
    import signal
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, start_new_session=True)
    try:
        code = proc.wait(timeout=timeout_s)
        return StageOutcome(status=status_for_exit(code), exit_code=code,
                            elapsed_s=round(time.perf_counter() - t0, 3))
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)   # the whole process GROUP
        except ProcessLookupError:
            pass   # child already exited between timeout and kill; harmless (established pattern)
        proc.wait()
        return StageOutcome(status="failed", exit_code=-1,
                            elapsed_s=round(time.perf_counter() - t0, 3), timed_out=True)
