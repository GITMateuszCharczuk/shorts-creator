from shared.layout.encode import build_nvenc_cmd


def test_nvenc_cmd_uses_h264_nvenc_and_audio(tmp_path):
    cmd = build_nvenc_cmd(frames_glob=str(tmp_path / "frames/%05d.png"),
                          audio=tmp_path / "music.wav", fps=30,   # the 04 mix, not raw narration
                          out=tmp_path / "youtube.mp4")
    s = " ".join(cmd)
    assert "h264_nvenc" in s and "-framerate 30" in s
    assert s.endswith(str(tmp_path / "youtube.mp4"))
