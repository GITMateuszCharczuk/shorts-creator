import os
from pathlib import Path


def to_relative(path: str, *, data_root: str) -> str:
    """ADR 0015a D4: convert ComfyUI's host-ABSOLUTE output path to DATA_ROOT-relative AT THE API
    BOUNDARY — the only place an absolute path is allowed. Outside DATA_ROOT -> fail loud (a pod
    could never resolve it)."""
    p = Path(path)
    if not p.is_absolute():
        return path
    try:
        return str(p.relative_to(data_root))
    except ValueError:
        raise ValueError(
            f"{path!r} is outside DATA_ROOT {data_root!r} — cannot store cross-mode"
        ) from None


def resolve(rel_path: str, *, data_root: str | None = None) -> Path:
    """Resolve a DATA_ROOT-relative path against THIS process's DATA_ROOT (/data in a pod, the WSL2
    dir on the host) — every process maps the same relative path to its own mount (D4)."""
    return Path(data_root or os.environ["DATA_ROOT"]) / rel_path
