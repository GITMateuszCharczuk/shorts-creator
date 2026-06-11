from typing import Any


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_config(*, global_defaults: dict[str, Any], niche: dict[str, Any],
                   batch: dict[str, Any], per_platform: dict[str, Any]) -> dict[str, Any]:
    """Precedence: global -> niche -> batch -> per-platform (later wins)."""
    cfg: dict[str, Any] = {}
    for layer in (global_defaults, niche, batch, per_platform):
        cfg = _deep_merge(cfg, layer)
    return cfg
