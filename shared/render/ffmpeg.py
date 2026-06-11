from pathlib import Path

from shared.render.kenburns import zoompan_expr


def _escape_filter_path(p: Path) -> str:
    # a filtergraph arg splits on ':' and ignores nothing — escape ':' '\' and spaces so a
    # run_dir containing either can't break the ass= filter parse
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace(" ", "\\ ")


def build_ffmpeg_cmd(
    *,
    scene_images: list[Path],
    scene_durations: list[float],
    narration: Path,
    captions_ass: Path,
    brand_overlay: Path,
    out: Path,
    fps: int,
) -> list[str]:
    """M1 interim render: Ken Burns stills -> concat -> burn captions -> brand overlay -> + audio.

    Inputs are ordered: images 0..n-1, narration = n, brand_overlay = n+1.
    """
    if not scene_images:
        raise ValueError("build_ffmpeg_cmd: no scenes (concat=n=0 is invalid)")
    if len(scene_images) != len(scene_durations):
        raise ValueError("build_ffmpeg_cmd: scene_images and scene_durations length mismatch")
    cmd: list[str] = ["ffmpeg", "-y"]
    for img, dur in zip(scene_images, scene_durations):
        cmd += ["-loop", "1", "-t", f"{dur}", "-i", str(img)]
    cmd += ["-i", str(narration), "-i", str(brand_overlay)]
    n = len(scene_images)
    # per-still Ken Burns (zoompan), concat, burn captions, then overlay the brand bug.
    # max(...,1): a sub-frame duration must never emit d=0 (ffmpeg treats it as infinite).
    filters = "".join(
        f"[{i}:v]scale=1080:1920,setsar=1,"
        f"{zoompan_expr(zoom_start=1.0, zoom_end=1.08, frames=max(int(dur * fps), 1))}[v{i}];"
        for i, dur in enumerate(scene_durations)
    )
    filters += "".join(f"[v{i}]" for i in range(n))
    filters += f"concat=n={n}:v=1:a=0[vc];"
    filters += f"[vc]ass={_escape_filter_path(captions_ass)}[vs];"
    filters += f"[vs][{n + 1}:v]overlay=W-w-40:40[vo]"   # brand bug, top-right (input n+1)
    cmd += [
        "-filter_complex", filters,
        "-map", "[vo]",
        "-map", f"{n}:a",
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out),
    ]
    return cmd
