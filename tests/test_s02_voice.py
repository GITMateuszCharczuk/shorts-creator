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
