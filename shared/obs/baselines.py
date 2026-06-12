import math
from collections import defaultdict


def _p95(xs: list[float]) -> float:
    s = sorted(xs)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)] if s else 0.0   # nearest-rank


def stage_baselines(timings: list[dict]) -> dict[str, float]:
    by: dict[str, list[float]] = defaultdict(list)
    for t in timings:
        by[t["stage"]].append(t["elapsed_s"])
    return {stage: _p95(v) for stage, v in by.items()}


def classify(stage: str, *, elapsed_s: float, base: dict[str, float], hard_deadline_s: float,
             last_heartbeat_age_s: float, running: int, slow_factor: float = 1.5,
             heartbeat_timeout_s: float = 180.0) -> str:
    """ok | slow | stuck. Only a RUNNING stage can be slow/stuck — a completed stage's stale .prom
    never false-pages. STUCK = past the hard deadline OR a dead heartbeat. SLOW (warn) = past
    p95*slow_factor. Unknown stage (no baseline) can only be stuck via deadline/heartbeat."""
    if running != 1:
        return "ok"
    if elapsed_s > hard_deadline_s or last_heartbeat_age_s > heartbeat_timeout_s:
        return "stuck"
    b = base.get(stage)
    return "slow" if (b and elapsed_s > b * slow_factor) else "ok"
