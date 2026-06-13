class BindError(Exception):
    """A region binds a field absent from the format's typed beat data."""


def _walk(node, path: str):
    """Walk a dotted path with optional integer list indices. Returns (value, found)."""
    for part in path.split("."):
        if part.isdigit() and isinstance(node, list):
            i = int(part)
            if i >= len(node):
                return None, False
            node = node[i]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None, False
    return node, True


def _exists(path: str, data: dict) -> bool:
    return _walk(data, path)[1]


def validate_binds(binds: list[str], beat_data: dict) -> None:
    for b in binds:
        if b == "static":            # ADR 0007a §3 exempt case
            continue
        if not _exists(b, beat_data):
            raise BindError(f"region bind {b!r} not in beat data")
