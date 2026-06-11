import json
import sys
from datetime import datetime, timezone


class StructuredLogger:
    def __init__(self, stage: str):
        self._stage = stage

    def _emit(self, level: str, msg: str, **kw):
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
               "stage": self._stage, "msg": msg, **kw}
        print(json.dumps(rec), file=sys.stderr)

    def info(self, msg: str, **kw): self._emit("info", msg, **kw)
    def warning(self, msg: str, **kw): self._emit("warning", msg, **kw)
    def error(self, msg: str, **kw): self._emit("error", msg, **kw)


def get_logger(stage: str) -> StructuredLogger:
    return StructuredLogger(stage)
