import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from shared.render.ffmpeg import build_ffmpeg_cmd


def test_cmd_burns_captions_and_audio_and_outputs_mp4(tmp_path):
    cmd = build_ffmpeg_cmd(
        scene_images=[tmp_path / "a.png", tmp_path / "b.png"],
        scene_durations=[2.0, 2.5],
        narration=tmp_path / "narration.wav",
        captions_ass=tmp_path / "captions.ass",
        brand_overlay=tmp_path / "logo.png",
        out=tmp_path / "youtube.mp4",
        fps=30,
    )
    s = " ".join(cmd)
    assert cmd[0] == "ffmpeg"
    assert "ass=" in s                      # caption burn-in
    assert str(tmp_path / "narration.wav") in s
    assert s.endswith(str(tmp_path / "youtube.mp4"))
    assert "-r 30" in s or "fps=30" in s
    assert "zoompan=" in s                  # Ken Burns applied per still
    assert "overlay=" in s                  # brand bug enabled


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_cmd_actually_renders_a_tiny_mp4(tmp_path):
    # 2 tiny PNGs (solid colour, via ffmpeg itself to avoid a Pillow dep here)
    for name, colour in (("a.png", "red"), ("b.png", "blue"), ("logo.png", "white")):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=108x192:d=1",
             "-frames:v", "1", str(tmp_path / name)],
            check=True, capture_output=True,
        )
    sf.write(tmp_path / "narration.wav", np.zeros(2400, dtype="float32"), 24000)
    (tmp_path / "captions.ass").write_text(
        "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Outline, Shadow, Alignment, MarginV\n"
        "Style: Base,Arial,72,&H00FFFFFF,&H00000000,&H64000000,1,4,2,2,300\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:00.50,Base,hi\n"
    )
    cmd = build_ffmpeg_cmd(
        scene_images=[tmp_path / "a.png", tmp_path / "b.png"],
        scene_durations=[0.3, 0.3],
        narration=tmp_path / "narration.wav",
        captions_ass=tmp_path / "captions.ass",
        brand_overlay=tmp_path / "logo.png",
        out=tmp_path / "youtube.mp4",
        fps=10,
    )
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    assert (tmp_path / "youtube.mp4").stat().st_size > 0
