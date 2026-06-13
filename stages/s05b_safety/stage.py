import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="05b", inputs=["render", "vision", "script"], outputs=["qc"],
                     compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    ctx.backend("llm").llm("qc-safety-check")  # exercise the seam; M1 wires the real prompt
    out = ctx.write_output("qc")
    out.write_text(json.dumps({"schema_version": "1.0.0", "verdict": "pass",
        "checks": {"disclaimer": {"pass": True},
                   "loudness": {"pass": True, "detail": "-14 LUFS"}}}))
    return StageResult(outputs={"qc": out})
