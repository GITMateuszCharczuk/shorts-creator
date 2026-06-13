import json
import warnings
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


class SchemaError(Exception):
    """Raised on validation failure or incompatible schema_version."""


def _parse_semver(v: str) -> tuple[int, int, int]:
    if not isinstance(v, str):  # int schema_version -> SchemaError, not a raw AttributeError
        raise SchemaError(f"bad semver: {v!r}")
    parts = v.split(".")
    if len(parts) != 3:
        raise SchemaError(f"bad semver: {v!r}")
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError as e:  # non-numeric component, e.g. "1.0.0-rc1" — keep the error contract
        raise SchemaError(f"bad semver: {v!r}") from e


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
        self._ref_registry: Registry | None = None

    def _registry(self) -> Registry:
        # Build a referencing Registry of every schema (keyed by its $id) once, so a cross-file
        # $ref (e.g. job.schema's "profile" -> profile.schema.json) resolves instead of being
        # fetched off the network. Internal #/$defs refs are unaffected.
        if self._ref_registry is None:
            resources = []
            for p in sorted(self._dir.glob("*.schema.json")):
                doc = json.loads(p.read_text())
                rid = doc.get("$id", p.name)
                resources.append(
                    (rid, Resource.from_contents(doc, default_specification=DRAFT202012)))
            self._ref_registry = Registry().with_resources(resources)
        return self._ref_registry

    def schema(self, name: str) -> dict[str, Any]:
        if name not in self._cache:
            path = self._dir / f"{name}.schema.json"
            if not path.exists():
                raise SchemaError(f"no schema named {name!r} at {path}")
            self._cache[name] = json.loads(path.read_text())
        return self._cache[name]

    def validate(self, name: str, instance: dict[str, Any]) -> None:
        # a non-dict instance -> clean SchemaError, not a raw AttributeError on .get()
        if not isinstance(instance, dict):
            raise SchemaError(
                f"{name} instance must be a JSON object, got {type(instance).__name__}")
        schema = self.schema(name)
        version_compatible(
            schema=schema.get("schema_version", "0.0.0"),
            instance=instance.get("schema_version"),
        )
        try:
            validator = Draft202012Validator(schema, registry=self._registry())
            errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
        except Exception as e:  # a malformed schema file -> surface as SchemaError, not a raw crash
            raise SchemaError(f"{name} schema is malformed: {e}") from e
        if errors:
            msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise SchemaError(f"{name} instance invalid: {msgs}")
