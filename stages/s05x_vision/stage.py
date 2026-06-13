import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="05x", inputs=["render", "script"], outputs=["vision"],
                     compute="gpu", capability="vlm_judge"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    ctx.backend("vlm_judge").vlm_judge([ctx.read_input("render")], script)  # canned Judgment (M0)
    out = ctx.write_output("vision")
    out.write_text(json.dumps({"schema_version": "1.0.0",
        "keyframes": [{"frame_id": "0", "kind": "hook",
                       "observations": ["clean typographic card"]}]}))
    return StageResult(outputs={"vision": out})
