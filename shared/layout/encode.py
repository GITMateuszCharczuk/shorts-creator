from pathlib import Path


def build_nvenc_cmd(*, frames_glob: str, audio: Path, fps: int, out: Path) -> list[str]:
    # `audio` is the Stage-04 duck+loudnorm MIX (narration already in it) — not raw narration.
    return ["ffmpeg", "-y", "-framerate", str(fps), "-i", frames_glob,
            "-i", str(audio), "-c:v", "h264_nvenc", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out)]
