import hashlib
import json
from typing import Any


def _reject_non_json(o: Any) -> Any:
    # Called by json.dumps only for types it can't natively encode (Path, set, datetime, ...).
    # Fail LOUD with the offending type rather than blowing up opaquely deep inside the hash.
    raise TypeError(f"non-JSON value in hashed payload: {type(o).__name__} ({o!r})")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace.

    Contract: inputs must be JSON-native (dict/list/str/int/float/bool/None). This holds for hashed
    payloads here because `resolved_config` is JSON-loaded by the config resolver (Task 8), so it
    never contains tuples/sets. Note canonical JSON treats a tuple and a list identically (json
    coerces tuple->list); callers must therefore not hand-construct configs with tuples where a
    list-vs-tuple distinction would matter. Non-JSON types raise TypeError."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=_reject_non_json)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_hash(
    *,
    declared_input_digests: dict[str, str],
    resolved_config: Any,
    stage_version: str,
    model_id: str | None = None,
    graph_version: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "declared_input_digests": dict(sorted(declared_input_digests.items())),
        "resolved_config": resolved_config,
        "stage_version": stage_version,
    }
    if model_id is not None:
        payload["model_id"] = model_id
    if graph_version is not None:
        payload["graph_version"] = graph_version
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def cache_key(stage: str, input_hash_hex: str, seed: int) -> tuple[str, str, int]:
    return (stage, input_hash_hex, seed)
