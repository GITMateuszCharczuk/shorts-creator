from stages.s02_voice.stage import keyword_in_opening, spoken_text


def test_spoken_text_normalizes_and_joins_beats():
    script = {"narration_beats": [{"text": "CPI hit 3.2%"}, {"text": "$1.5M moved"}],
              "primary_keyword": "inflation"}
    out = spoken_text(script)
    assert "three point two percent" in out and "one point five million dollars" in out


def test_keyword_in_opening_detects_presence_and_absence():
    present = {"primary_keyword": "inflation",
               "narration_beats": [{"text": "Inflation cooled this month"}, {"text": "More later"}]}
    assert keyword_in_opening(present) is True
    buried = {"primary_keyword": "inflation",
              "narration_beats": [{"text": "Stocks rose"}, {"text": "Inflation later"}]}
    assert keyword_in_opening(buried, window_beats=1) is False


def test_spoken_text_tolerates_missing_text_key():
    assert spoken_text({"narration_beats": [{"prosody": "rising"}, {"text": "ok"}]}) == " ok"


def test_keyword_null_is_not_a_crash():
    assert keyword_in_opening({"primary_keyword": None,
                               "narration_beats": [{"text": "x"}]}) is False


def test_empty_narration_quarantines():
    import pytest
    from pathlib import Path
    from shared.ctx import Quarantined, StageContext
    from stages.s02_voice.stage import run
    import json as _json
    import tempfile
    d = Path(tempfile.mkdtemp())
    (d / "script.json").write_text(_json.dumps({"narration_beats": []}))
    ctx = StageContext(stage="02", run_dir=d, seed=1, job={}, config={},
                       input_paths={"script": "script.json"},
                       output_paths={"narration": "narration.wav"}, backends={})
    with pytest.raises(Quarantined):
        run(ctx)
