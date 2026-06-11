def next_lane(history: list[str], *, monetization_share: float, window: int = 20) -> str:
    """Rolling-window lane choice (ADR 0006 D2 as amended): pick `monetization` only while the
    trailing window is UNDER the configured share; default posture is reach-first."""
    recent = history[-window:]
    if not recent:
        return "reach"
    actual = sum(1 for x in recent if x == "monetization") / len(recent)
    return "monetization" if actual < monetization_share else "reach"
