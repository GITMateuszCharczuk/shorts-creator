from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="04", inputs=["script"], outputs=["music"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    out = ctx.write_output("music")
    out.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfake-music")  # placeholder wav (M0)
    return StageResult(outputs={"music": out})
