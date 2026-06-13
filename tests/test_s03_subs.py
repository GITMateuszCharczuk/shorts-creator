import pytest

from stages.s03_subs.stage import tag_emphasis


def test_tag_emphasis_marks_script_punch_words():
    aligned = [{"word": "Inflation", "start": 0.1, "end": 0.5},
               {"word": "cooled", "start": 0.5, "end": 0.9}]
    out = tag_emphasis(aligned, emphasis_words={"inflation"})
    assert out[0]["emphasis"] is True and out[1]["emphasis"] is False


def test_tag_emphasis_matches_numeric_token():
    aligned = [{"word": "3.2%", "start": 1.0, "end": 1.6}]
    assert tag_emphasis(aligned, {"3.2%"})[0]["emphasis"] is True   # raw numeric punch word


def test_tag_emphasis_tolerates_missing_word_key():
    # WhisperX can emit silence segments without "word"
    out = tag_emphasis([{"start": 0.0, "end": 0.2}], {"x"})
    assert out[0]["emphasis"] is False


@pytest.mark.integration
def test_whisperx_align_live(tmp_path):
    # host-only: requires whisperx installed (M1 acceptance criterion 6).
    # Exercises the real _align_to_script seam once it is wired at host bring-up.
    import numpy as np
    import soundfile as sf

    from stages.s03_subs.stage import _align_to_script
    wav = tmp_path / "n.wav"
    sf.write(wav, np.zeros(24000, dtype="float32"), 24000)
    words = _align_to_script(wav, "hello world")
    assert isinstance(words, list)
