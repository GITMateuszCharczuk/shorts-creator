import json
import time
from pathlib import Path


class StageTimer:
    """Context manager that appends one {stage, elapsed_s, ts} record to a jsonl log."""

    def __init__(self, stage: str, log_path: Path):
        self._stage = stage
        self._log = Path(log_path)
        self._t0 = 0.0

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        rec = {"stage": self._stage, "elapsed_s": round(time.perf_counter() - self._t0, 3),
               "ts": time.time()}
        self._log.parent.mkdir(parents=True, exist_ok=True)
        with self._log.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return False
