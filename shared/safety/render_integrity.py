# shared/safety/render_integrity.py
from shared.safety.types import CheckResult, SafetyThresholds


def black_run_ok(
    *, black_spans: list[tuple[float, float]], t: SafetyThresholds
) -> CheckResult:
    worst = max((e - s for s, e in black_spans), default=0.0)
    return CheckResult(
        worst <= t.max_black_run_s, "black_run",
        "" if worst <= t.max_black_run_s else f"{worst:.2f}s black run",
    )


def no_clipping_ok(*, true_peak_dbtp: float, t: SafetyThresholds) -> CheckResult:
    return CheckResult(
        true_peak_dbtp <= t.tp_max, "clipping",
        "" if true_peak_dbtp <= t.tp_max else f"true-peak {true_peak_dbtp} dBTP",
    )
