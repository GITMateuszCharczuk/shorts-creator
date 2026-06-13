from shared.audio.prosody import speech_segments


def test_maps_prosody_to_segment_params_and_normalizes_text():
    script = {"narration_beats": [
        {"text": "CPI hit 3.2%", "prosody": "emphatic", "emphasis": ["3.2%"]},
        {"text": "Slow down here", "prosody": "measured"}]}
    segs = speech_segments(script)
    # emphatic = slower, deliberate
    assert segs[0]["text"].endswith("percent") and segs[0]["rate"] < 1.0
    assert segs[0]["pause_after"] >= 0.3
    assert segs[1]["rate"] == 1.0                                          # measured = baseline
