import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01b", inputs=["script", "scenes_stock"], outputs=["scenes_gen"],
                     compute="gpu", capability="generate_image"))
def run(ctx: StageContext) -> StageResult:
    ctx.backend("generate_image").generate_image("hook typographic card", ctx.seed)  # seam
    out = ctx.write_output("scenes_gen")
    out.write_text(json.dumps({"frames": [{"beat_id": "hook", "path": "scenes/00.png"}]}))
    return StageResult(outputs={"scenes_gen": out})
