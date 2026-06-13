from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="02", inputs=["script"], outputs=["narration"], compute="cpu",
                     capability="tts"))
def run(ctx: StageContext) -> StageResult:
    ctx.backend("tts").tts("narration text")  # exercise the seam (fake returns a path)
    out = ctx.write_output("narration")
    out.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfake-narration")  # placeholder wav (M0)
    return StageResult(outputs={"narration": out})
