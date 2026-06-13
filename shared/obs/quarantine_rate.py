def trailing_rate(outcomes: list[str], *, window: int = 20) -> float:
    recent = outcomes[-window:]
    return sum(1 for o in recent if o == "quarantined") / len(recent) if recent else 0.0


def is_spike(*, rate: float, baseline: float, abs_floor: float = 0.30, mult: float = 2.0) -> bool:
    """The SAME two-part condition the alert rule uses (no divergence): trip on the absolute floor
    OR a multiple of the trailing baseline.  Both arms use strict > to match the Task 6 PromQL
    (shorts_quarantine_rate > 0.30 or shorts_quarantine_rate > 2 * shorts_quarantine_baseline),
    which also prevents a zero-baseline cold-start false alarm (0.0 > 0.0 is False)."""
    return rate > abs_floor or rate > baseline * mult
