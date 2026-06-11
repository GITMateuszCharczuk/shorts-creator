from stages.s03_subs.stage import tag_emphasis


def test_tag_emphasis_marks_script_punch_words():
    aligned = [{"word": "Inflation", "start": 0.1, "end": 0.5},
               {"word": "cooled", "start": 0.5, "end": 0.9}]
    out = tag_emphasis(aligned, emphasis_words={"inflation"})
    assert out[0]["emphasis"] is True and out[1]["emphasis"] is False


def test_tag_emphasis_matches_numeric_token():
    aligned = [{"word": "3.2%", "start": 1.0, "end": 1.6}]
    assert tag_emphasis(aligned, {"3.2%"})[0]["emphasis"] is True   # raw numeric punch word
