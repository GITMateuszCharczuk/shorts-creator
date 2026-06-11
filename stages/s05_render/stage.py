import json
import subprocess

from shared.ctx import StageContext, StageResult
from shared.render.ffmpeg import build_ffmpeg_cmd
from shared.stage import StageManifest, stage


def scene_durations_from_words(words: list[dict], n_scenes: int) -> list[float]:
    # word-timed cuts (ADR 0005 D4 / 0007a §2): partition words into n_scenes contiguous
    # groups; each scene spans its group's first->last word, not a flat division.
    k, m = divmod(len(words), n_scenes)
    durs, idx = [], 0
    for s in range(n_scenes):
        size = k + (1 if s < m else 0)
        group = words[idx:idx + size]
        idx += size
        durs.append(round(group[-1]["end"] - group[0]["start"], 6) if group else 0.0)
    return durs


@stage(StageManifest(
    id="05",
    inputs=["script", "assets", "narration", "captions"],
    outputs=["render"],
    compute="cpu",
))
def run(ctx: StageContext) -> StageResult:
    _script = json.loads(ctx.read_input("script").read_text())  # loaded for M2 compositor
    assets = json.loads(ctx.read_input("assets").read_text())
    images = [ctx.run_dir / s["clip_path"] for s in assets["scenes"]]
    aligned_path = ctx.run_dir / "aligned_words.json"
    words = json.loads(aligned_path.read_text()) if aligned_path.exists() else []
    durs = (
        scene_durations_from_words(words, len(images)) if words else [2.0] * len(images)
    )
    out = ctx.write_output("render")
    cmd = build_ffmpeg_cmd(
        scene_images=images,
        scene_durations=durs,
        narration=ctx.read_input("narration"),
        captions_ass=ctx.read_input("captions"),
        brand_overlay=ctx.run_dir / ctx.config.get("brand_logo", "logo.png"),
        out=out,
        fps=int(ctx.config.get("fps", 30)),
    )
    subprocess.run(cmd, check=True)
    ctx.log.info("render complete", path=str(out))
    return StageResult(outputs={"render": out})
