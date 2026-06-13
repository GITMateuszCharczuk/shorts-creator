import json
from pathlib import Path

from shared.captions.ass import build_ass, group_words

FIX = Path(__file__).parent / "fixtures" / "m1"


def test_group_caps_words_per_line():
    words = json.loads((FIX / "aligned_words.json").read_text())
    groups = group_words(words, max_words=4)
    assert all(len(g) <= 4 for g in groups)
    assert len(groups) == 2  # 6 words -> [4, 2]


def test_build_ass_has_header_and_dialogue_and_emphasis_color():
    words = json.loads((FIX / "aligned_words.json").read_text())
    ass = build_ass(words, max_words=4, font="Inter", emphasis_hex="00E5FF",
                    safe_bottom_pct=18)
    assert "[Script Info]" in ass and "Dialogue:" in ass
    assert "PrimaryColour" in ass
    assert r"{\c&H" in ass  # inline emphasis color override present


def test_timing_uses_first_and_last_word_of_group():
    words = json.loads((FIX / "aligned_words.json").read_text())
    ass = build_ass(words, max_words=4, font="Inter", emphasis_hex="00E5FF", safe_bottom_pct=18)
    assert "0:00:00.10," in ass  # first group start


def test_ts_never_emits_60_seconds():
    from shared.captions.ass import _ts
    assert _ts(59.999) == "0:01:00.00"   # carry propagates; "0:00:60.00" is illegal ASS
    assert _ts(3599.999) == "1:00:00.00"
    assert _ts(2.07) == "0:00:02.07"     # no float-floor undershoot
    assert _ts(0.10) == "0:00:00.10"


def test_emphasis_color_is_bgr_converted():
    # callers pass natural RGB; ASS wants &HBBGGRR — cyan 00E5FF must become FFE500
    words = [{"word": "x", "start": 0.0, "end": 1.0, "emphasis": True}]
    ass = build_ass(words, max_words=4, font="Inter", emphasis_hex="00E5FF", safe_bottom_pct=18)
    assert r"{\c&HFFE500&}" in ass
    assert r"{\r}" in ass                # reset to STYLE colour, not hardcoded white


def test_braces_in_words_cannot_inject_overrides():
    words = [{"word": "{\\an8}hack", "start": 0.0, "end": 1.0, "emphasis": False}]
    ass = build_ass(words, max_words=4, font="Inter", emphasis_hex="00E5FF", safe_bottom_pct=18)
    assert "{\\an8}" not in ass
