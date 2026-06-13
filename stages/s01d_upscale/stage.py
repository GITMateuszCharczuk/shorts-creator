import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01d", inputs=["scenes_motion"], outputs=["assets"],
                     compute="gpu", capability="restore"))
def run(ctx: StageContext) -> StageResult:
    ctx.backend("restore").restore([ctx.read_input("scenes_motion")])  # ESRGAN/RIFE/GFPGAN (fake)
    out = ctx.write_output("assets")
    out.write_text(json.dumps({"schema_version": "1.0.0",
        "scenes": [{"beat_id": "hook", "clip_path": "fin-0001/scenes/00.mp4", "duration": 1.8}]}))
    return StageResult(outputs={"assets": out})
