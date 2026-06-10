import json
import warnings
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


class SchemaError(Exception):
    """Raised on validation failure or incompatible schema_version."""


def _parse_semver(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    if len(parts) != 3:
        raise SchemaError(f"bad semver: {v!r}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def version_compatible(*, schema: str, instance: str | None) -> bool:
    if instance is None:
        raise SchemaError("instance is missing schema_version")
    smaj, smin, _ = _parse_semver(schema)
    imaj, imin, _ = _parse_semver(instance)
    if smaj != imaj:
        raise SchemaError(f"major schema_version mismatch: schema {schema} vs instance {instance}")
    if smin != imin:
        warnings.warn(
            f"minor schema_version mismatch: schema {schema} vs instance {instance}",
            UserWarning,
            stacklevel=2,
        )
    return True


class SchemaRegistry:
    """Loads schemas/<name>.schema.json once and validates instances against them."""

    def __init__(self, schemas_dir: Path = SCHEMAS_DIR):
        self._dir = schemas_dir
        self._cache: dict[str, dict[str, Any]] = {}

    def schema(self, name: str) -> dict[str, Any]:
        if name not in self._cache:
            path = self._dir / f"{name}.schema.json"
            if not path.exists():
                raise SchemaError(f"no schema named {name!r} at {path}")
            self._cache[name] = json.loads(path.read_text())
        return self._cache[name]

    def validate(self, name: str, instance: dict[str, Any]) -> None:
        schema = self.schema(name)
        version_compatible(
            schema=schema.get("schema_version", "0.0.0"),
            instance=instance.get("schema_version"),
        )
        errors = sorted(Draft202012Validator(schema).iter_errors(instance),
                        key=lambda e: e.json_path)
        if errors:
            msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise SchemaError(f"{name} instance invalid: {msgs}")
