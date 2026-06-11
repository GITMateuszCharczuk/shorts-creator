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
