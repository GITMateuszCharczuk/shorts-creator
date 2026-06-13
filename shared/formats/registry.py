import json
from pathlib import Path

from shared.schema import SchemaRegistry

_ROOT = Path(__file__).resolve().parents[2] / "formats"
_REG = SchemaRegistry()


def compatible(fmt: dict, lane: str) -> bool:
    return bool(fmt.get("lane_support", {}).get(lane, False))


class FormatRegistry:
    def __init__(self, root: Path = _ROOT):
        self._fmts = {}
        for p in sorted(root.glob("*/format.json")):
            fmt = json.loads(p.read_text())
            _REG.validate("format", fmt)
            self._fmts[fmt["id"]] = fmt

    def get(self, fid: str) -> dict:
        return self._fmts[fid]

    def all(self) -> list[dict]:
        return list(self._fmts.values())
