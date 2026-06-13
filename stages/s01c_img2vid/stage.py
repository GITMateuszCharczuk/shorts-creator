import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01c", inputs=["scenes_gen"], outputs=["scenes_motion"],
                     compute="gpu", capability="img2vid"))
def run(ctx: StageContext) -> StageResult:
    ctx.backend("img2vid").img2vid(ctx.read_input("scenes_gen"), ctx.seed)  # reads the prior output
    out = ctx.write_output("scenes_motion")
    out.write_text(json.dumps({"clips": [{"beat_id": "hook", "path": "scenes/00.mp4"}]}))
    return StageResult(outputs={"scenes_motion": out})
