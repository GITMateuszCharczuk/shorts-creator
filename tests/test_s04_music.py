from stages.s04_music.stage import build_mix_cmd


def test_mix_applies_duck_and_loudnorm(tmp_path):
    cmd = build_mix_cmd(narration=tmp_path / "narration.wav", music=tmp_path / "t1.mp3",
                        platform="youtube", out=tmp_path / "music.wav")
    s = " ".join(cmd)
    assert "sidechaincompress" in s and "loudnorm=I=-14" in s
    assert s.endswith(str(tmp_path / "music.wav"))
