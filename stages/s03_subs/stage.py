import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="03", inputs=["script", "narration"], outputs=["captions"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    out = ctx.write_output("captions")
    out.write_text(json.dumps({"cues": [{"t": 0.0, "text": "3 that beat inflation"}]}))
    return StageResult(outputs={"captions": out})
