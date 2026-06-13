# shared/safety/audio_defect.py
from shared.safety.types import CheckResult, SafetyThresholds


def loudness_ok(
    *, integrated_lufs: float, true_peak_dbtp: float, t: SafetyThresholds
) -> CheckResult:
    ok = t.lufs_min <= integrated_lufs <= t.lufs_max and true_peak_dbtp <= t.tp_max
    return CheckResult(
        ok, "loudness",
        "" if ok else f"I={integrated_lufs} TP={true_peak_dbtp} outside window",
    )


def hook_dead_air_ok(
    *, silences: list[tuple[float, float]], t: SafetyThresholds
) -> CheckResult:
    for start, end in silences:
        if start < t.hook_window_s and (min(end, t.hook_window_s) - start) > t.max_hook_silence_s:
            return CheckResult(False, "hook_dead_air", f"silence in first {t.hook_window_s}s")
    return CheckResult(True, "hook_dead_air")


def synth_duration_ok(
    *, actual_s: float, projected_s: float, t: SafetyThresholds
) -> CheckResult:
    if projected_s <= 0:
        return CheckResult(False, "synth_duration", "no projected runtime")
    off = abs(actual_s - projected_s) / projected_s
    return CheckResult(
        off <= t.duration_tol, "synth_duration",
        "" if off <= t.duration_tol else f"{off:.0%} off projected",
    )
