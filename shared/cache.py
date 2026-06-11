import json
from pathlib import Path
from typing import Any


class StageCache:
    """Content-addressed cache: key (stage, input_hash, seed) -> recorded output map.

    File-backed: one JSON file per key under root/<stage>/<input_hash>-<seed>.json.
    Stores the declared-output path map produced by a stage so a hit skips recompute.
    """

    def __init__(self, root: Path):
        self._root = Path(root)

    def _path(self, key: tuple[str, str, int]) -> Path:
        stage, ih, seed = key
        return self._root / stage / f"{ih}-{seed}.json"

    def get(self, key: tuple[str, str, int]) -> dict[str, Any] | None:
        p = self._path(key)
        return json.loads(p.read_text()) if p.exists() else None

    def put(self, key: tuple[str, str, int], outputs: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(outputs))
        tmp.rename(p)  # atomic write (ADR 0003 D6)
