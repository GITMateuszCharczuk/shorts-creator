import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="05c", inputs=["render", "vision", "script"], outputs=["creative_qc"],
                     compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    ctx.backend("llm").llm("creative-qc-check")  # exercise the seam; M1 wires the real prompt
    out = ctx.write_output("creative_qc")
    out.write_text(json.dumps({"schema_version": "1.0.0",
        "scores": {"hook": 0.8, "original_insight": 0.7}, "overall": 0.76, "floor": 0.70,
        "pass": True}))
    return StageResult(outputs={"creative_qc": out})
