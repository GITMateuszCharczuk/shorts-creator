from dataclasses import dataclass


@dataclass(frozen=True)
class Judgment:
    overall: float
    scores: dict[str, float]
    passed: bool
    # per-pass VLM observations (ADR 0016 D5); verdicts stay in the gates, not here
    observations: tuple[str, ...] = ()
