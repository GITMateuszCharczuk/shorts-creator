# tests/test_audio_defect.py
from shared.safety.audio_defect import hook_dead_air_ok, loudness_ok, synth_duration_ok
from shared.safety.types import SafetyThresholds

T = SafetyThresholds()


def test_loudness_window():
    assert loudness_ok(integrated_lufs=-14.0, true_peak_dbtp=-1.5, t=T).ok
    assert not loudness_ok(integrated_lufs=-9.0, true_peak_dbtp=-1.5, t=T).ok    # too hot
    assert not loudness_ok(integrated_lufs=-14.0, true_peak_dbtp=-0.2, t=T).ok   # clipped peak


def test_hook_dead_air():
    assert hook_dead_air_ok(silences=[(3.0, 3.6)], t=T).ok                       # outside the hook
    assert not hook_dead_air_ok(silences=[(0.5, 1.1)], t=T).ok                   # 0.6s dead hook


def test_synth_duration_within_tolerance():
    assert synth_duration_ok(actual_s=30.0, projected_s=31.0, t=T).ok            # ~3% < 8%
    assert not synth_duration_ok(actual_s=20.0, projected_s=30.0, t=T).ok        # 33% off
