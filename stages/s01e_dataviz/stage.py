import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01e", inputs=["data", "script"], outputs=["scenes_viz"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    json.loads(ctx.read_input("data").read_text())  # data drives the chart values
    out = ctx.write_output("scenes_viz")
    out.write_text(json.dumps({"charts": [{"beat_id": "body", "kind": "bar"}]}))
    return StageResult(outputs={"scenes_viz": out})
