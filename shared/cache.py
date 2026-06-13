import json
import os
import uuid
from pathlib import Path
from typing import Any


class StageCache:
    """Content-addressed cache: key (stage, input_hash, seed) -> recorded output map.

    File-backed: one JSON file per key under root/<stage>/<input_hash>-<seed>.json.
    Stores the declared-output path map produced by a stage so a hit skips recompute.

    Stale-hit contract: get() returns the recorded path map WITHOUT checking the files
    still exist. A caller (the M4 conductor) must verify the returned paths are live before
    trusting a hit, because M6 GC can delete artifacts independently of this cache.
    """

    def __init__(self, root: Path):
        self._root = Path(root)

    def _path(self, key: tuple[str, str, int]) -> Path:
        stage, ih, seed = key
        if "/" in stage or ".." in stage:   # stage ids are registry keys; guard the path anyway
            raise ValueError(f"unsafe stage id for cache path: {stage!r}")
        return self._root / stage / f"{ih}-{seed}.json"

    def get(self, key: tuple[str, str, int]) -> dict[str, Any] | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None  # a corrupt/unreadable entry is treated as a miss (self-healing)

    def put(self, key: tuple[str, str, int], outputs: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # unique tmp per call (same dir -> rename stays atomic) so concurrent puts can't
        # clobber a shared tmp mid-write
        tmp = p.with_name(f"{p.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(outputs))
        tmp.rename(p)  # atomic write (ADR 0003 D6)
