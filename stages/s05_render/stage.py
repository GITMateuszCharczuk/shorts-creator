from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="05", inputs=["script", "assets", "narration", "captions", "music"],
                     outputs=["render"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    out = ctx.write_output("render")
    out.write_bytes(b"\x00\x00\x00\x18ftypmp42fake-render")  # placeholder mp4 (M0)
    return StageResult(outputs={"render": out})
