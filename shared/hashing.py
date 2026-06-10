import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
