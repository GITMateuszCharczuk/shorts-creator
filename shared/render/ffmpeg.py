from pathlib import Path

from shared.render.kenburns import zoompan_expr


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
    cmd: list[str] = ["ffmpeg", "-y"]
    for img, dur in zip(scene_images, scene_durations):
        cmd += ["-loop", "1", "-t", f"{dur}", "-i", str(img)]
    cmd += ["-i", str(narration), "-i", str(brand_overlay)]
    n = len(scene_images)
    # per-still Ken Burns (zoompan), concat, burn captions, then overlay the brand bug
    filters = "".join(
        f"[{i}:v]scale=1080:1920,setsar=1,"
        f"{zoompan_expr(zoom_start=1.0, zoom_end=1.08, frames=int(dur * fps))}[v{i}];"
        for i, dur in enumerate(scene_durations)
    )
    filters += "".join(f"[v{i}]" for i in range(n))
    filters += f"concat=n={n}:v=1:a=0[vc];"
    filters += f"[vc]ass={captions_ass}[vs];"
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
