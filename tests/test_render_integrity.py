# tests/test_render_integrity.py
from shared.safety.render_integrity import black_run_ok, no_clipping_ok
from shared.safety.types import SafetyThresholds

T = SafetyThresholds()


def test_black_run():
    assert black_run_ok(black_spans=[(5.0, 5.1)], t=T).ok        # 0.1s blink ok
    assert not black_run_ok(black_spans=[(5.0, 5.5)], t=T).ok    # 0.5s black > 0.25s


def test_clipping_guard():
    assert no_clipping_ok(true_peak_dbtp=-1.0, t=T).ok
    assert not no_clipping_ok(true_peak_dbtp=0.0, t=T).ok
