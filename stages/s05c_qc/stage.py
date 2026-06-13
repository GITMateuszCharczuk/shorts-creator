import json

from shared.ctx import StageContext, StageResult
from shared.qc.creative import passes_floor, weighted_overall
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()

# Required keys the text judge must return (hook/original_insight/payoff).
# If any are absent the judge is treated as a failing zero so a deliberately-unhelpful
# judge cannot evade quarantine by crashing before the artifact is written (ADR 0016 D1).
_TEXT_JUDGE_KEYS = {"hook", "original_insight", "payoff"}


def _judge_text(llm, script: dict, observations: list[str]) -> dict:
    """The INDEPENDENT judge (non-Qwen lineage, resolved per-stage — ADR 0016 D1) scores the
    text-judgeable criteria from script + treatment + the 05x render observations.

    Missing required keys are filled with 0.0 (failing score) rather than propagating a
    KeyError: a deliberately-unhelpful judge must not crash before the artifact is written,
    because a crash before the write leaves no artifact and the quarantine path never fires."""
    prompt = ("Score 0-1 each of: hook, original_insight (a non-obvious, specific point of view — "
              "NOT a generic template fill), payoff. Respond as STRICT JSON "
              '{"hook": x, "original_insight": y, "payoff": z}.\n\n'
              f"SCRIPT: {json.dumps(script)}\nRENDER OBSERVATIONS: {json.dumps(observations)}")
    raw = llm.llm_json(prompt)   # constrained JSON + bounded retry (re-review)
    missing = _TEXT_JUDGE_KEYS - set(raw)
    if missing:
        # Zero-fill missing keys → weighted_overall can run → low score → quarantine.
        return {**{k: 0.0 for k in missing}, **{k: raw[k] for k in raw if k in _TEXT_JUDGE_KEYS}}
    return raw


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
