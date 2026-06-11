# ADR 0005 D2 + ADR 0014 D1: 5 criteria; original_insight is the policy-survival criterion (0.30).
RUBRIC = {"hook": 0.20, "original_insight": 0.30, "coherence": 0.20, "pacing": 0.15, "payoff": 0.15}
CRITERIA = set(RUBRIC)


def weighted_overall(scores: dict[str, float]) -> float:
    extra = set(scores) - CRITERIA
    if extra:
        raise ValueError(f"unexpected score keys: {sorted(extra)}")  # silent pollution guard
    return sum(scores[c] * w for c, w in RUBRIC.items())   # KeyError if a criterion is missing


def passes_floor(overall: float, floor: float = 0.70) -> bool:
    return overall >= floor
