from shared.ramp.state import approved_days

# Two tiers (ADR 0014 D2): a LENIENT bar lifts the per-post gate (achievable in a PoC window);
# a STRICTER bar widens cadence 1->2. Both are config (ctx.config["ramp"]).
DEFAULT_RAMP = {
    "lift":  {"min_approved": 10, "min_days": 7,  "max_rejected": 1, "max_strikes": 0},
    "widen": {"min_approved": 20, "min_days": 14, "max_rejected": 0, "max_strikes": 0},
}


def _meets(state: dict, bar: dict) -> bool:
    return (state.get("approved", 0) >= bar["min_approved"]
            and approved_days(state) >= bar["min_days"]
            and state.get("rejected", 0) <= bar["max_rejected"]
            and state.get("strikes", 0) <= bar["max_strikes"])


def gate_active(state: dict, cfg: dict) -> bool:
    """Human-at-publish gate stays ACTIVE until the LENIENT bar is met (ADR 0014 D2)."""
    return not _meets(state, {**DEFAULT_RAMP["lift"], **cfg.get("lift", {})})


def can_widen_cadence(state: dict, cfg: dict) -> bool:
    return _meets(state, {**DEFAULT_RAMP["widen"], **cfg.get("widen", {})})
