from shared.safety.types import CheckResult, SafetyThresholds


def test_check_result_shape():
    r = CheckResult(ok=False, name="disclaimer", detail="missing")
    assert (r.ok, r.name, r.detail) == (False, "disclaimer", "missing")


def test_thresholds_have_documented_defaults_and_are_overridable():
    t = SafetyThresholds()
    assert (t.lufs_min, t.lufs_max, t.tp_max) == (-16.0, -12.0, -1.0)
    assert t.hook_window_s == 2.5 and t.max_hook_silence_s == 0.4
    assert t.max_black_run_s == 0.25 and t.duration_tol == 0.08
    custom = SafetyThresholds.from_config({"lufs_max": -10.0})
    # partial override keeps defaults
    assert custom.lufs_max == -10.0 and custom.lufs_min == -16.0
