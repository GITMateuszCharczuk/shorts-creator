import json

from shared.ctx import StageContext, StageResult
from shared.qc.creative import passes_floor, weighted_overall
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()


def _judge_text(llm, script: dict, observations: list[str]) -> dict:
    """The INDEPENDENT judge (non-Qwen lineage, resolved per-stage — ADR 0016 D1) scores the
    text-judgeable criteria from script + treatment + the 05x render observations."""
    prompt = ("Score 0-1 each of: hook, original_insight (a non-obvious, specific point of view — "
              "NOT a generic template fill), payoff. Respond as STRICT JSON "
              '{"hook": x, "original_insight": y, "payoff": z}.\n\n'
              f"SCRIPT: {json.dumps(script)}\nRENDER OBSERVATIONS: {json.dumps(observations)}")
    return llm.llm_json(prompt)   # constrained JSON + bounded retry (re-review)


@stage(StageManifest(id="05c", inputs=["render", "vision", "script"], outputs=["creative_qc"],
                     compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    vision = json.loads(ctx.read_input("vision").read_text())
    script = json.loads(ctx.read_input("script").read_text())
    visual = vision["judgment"]["visual_scores"]                 # coherence, pacing (05x VLM)
    text = _judge_text(ctx.backend("llm"), script, vision["judgment"]["observations"])
    scores = {**visual, **text}                                  # the full 5-criterion rubric
    overall = weighted_overall(scores)
    floor = float(ctx.config.get("quality_floor", 0.70))
    ok = passes_floor(overall, floor)
    payload = {"schema_version": "1.0.0", "scores": scores,
               "overall": overall, "floor": floor, "pass": ok}
    _REG.validate("creative_qc", payload)            # boundary validation (Ch.5)
    out = ctx.write_output("creative_qc")
    out.write_text(json.dumps(payload))             # write the artifact BEFORE any quarantine raise
    if not ok:
        ctx.quarantine(f"creative-QC below floor: {overall:.3f} < {floor}")
    ctx.log.info("creative-QC pass", overall=round(overall, 3))
    return StageResult(outputs={"creative_qc": out})
