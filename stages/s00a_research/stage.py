import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="00a", inputs=[], outputs=["data"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    # M0: fixed research payload (seed-independent); M1 lands real retrieval.
    out = ctx.write_output("data")
    out.write_text(json.dumps({"schema_version": "1.0.0", "topic": "finance",
                               "facts": [{"k": "cpi_yoy", "v": "7.2%"}]}))
    ctx.log.info("research written", path=str(out))
    return StageResult(outputs={"data": out})
