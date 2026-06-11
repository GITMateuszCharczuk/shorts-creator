import json
import subprocess

from shared.audio.loudness import loudnorm_args
from shared.audio.music import select_track
from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


def build_mix_cmd(*, narration, music, platform: str, out) -> list[str]:
    # duck music under VO (sidechain), then normalize the bed to the platform target
    fc = (f"[1:a]sidechaincompress=threshold=0.05:ratio=8[duck];"
          f"[0:a][duck]amix=inputs=2:duration=longest,{loudnorm_args(platform)}[a]")
    return ["ffmpeg", "-y", "-i", str(narration), "-i", str(music),
            "-filter_complex", fc, "-map", "[a]", str(out)]


@stage(StageManifest(id="04", inputs=["script", "narration"], outputs=["music"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    library = json.loads(
        (ctx.run_dir / ctx.config.get("music_index", "music/index.json")).read_text())
    # batch anti-repeat (resolved from ledger)
    recent = set(ctx.config.get("recent_track_ids", []))
    track = select_track(library, mood=script["music"]["mood"],
                         energy=script["music"]["energy"], seed=ctx.seed, recent_ids=recent)
    out = ctx.write_output("music")
    plat = ctx.job.get("platform_targets", ["youtube"])[0]
    r = subprocess.run(
        build_mix_cmd(narration=ctx.read_input("narration"),
                      music=ctx.run_dir / track["path"], platform=plat, out=out),
        capture_output=True, text=True)
    if r.returncode != 0:
        # surface the ffmpeg stderr tail — a bare CalledProcessError gives the conductor nothing
        raise RuntimeError(f"music mix failed (exit {r.returncode}):\n{r.stderr[-2000:]}")
    ctx.log.info("music mixed", track=track["id"])
    return StageResult(outputs={"music": out})
