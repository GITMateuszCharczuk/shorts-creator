class BindError(Exception):
    """A region binds a field absent from the format's typed beat data."""


def _exists(path: str, data: dict) -> bool:
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def validate_binds(binds: list[str], beat_data: dict) -> None:
    for b in binds:
        if b == "static":            # ADR 0007a §3: literal "static"; content via primitive.params
            continue
        if not _exists(b, beat_data):
            raise BindError(f"region bind {b!r} not in beat data")
