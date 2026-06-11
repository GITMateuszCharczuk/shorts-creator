import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="00b", inputs=["data"], outputs=["script"], compute="cpu",
                     capability="llm"))
def run(ctx: StageContext) -> StageResult:
    data = json.loads(ctx.read_input("data").read_text())
    # M0: the LLM backend is a fake replaying a fixture; real Qwen lands in M1.
    _ = ctx.backend("llm").llm(json.dumps({"data": data, "seed": ctx.seed}))
    # In M0 the canonical script is the golden fixture content the fake encodes.
    out = ctx.write_output("script")
    out.write_text(json.dumps(_canonical_script(data, ctx.seed)))
    ctx.log.info("script written", path=str(out))
    return StageResult(outputs={"script": out})


def _canonical_script(data: dict, seed: int) -> dict:
    # Minimal valid script.schema instance; M1 replaces with real generation.
    return {
        "schema_version": "1.0.0", "format": "ranked_list",
        "treatment": {"thesis": "t", "angle": "a", "tone": "measured",
                      "visual_motif": ["m"], "energy_curve": [0.3, 1.0]},
        "hook": {"spoken": "h", "on_screen_text": "h", "first_frame_visual": "card",
                 "duration": 1.8},
        "narration_beats": [{"text": "n"}], "captions": [{"text": "c"}],
        "music": {"mood": "confident", "energy": "mid"},
        "platform_meta": {
            "youtube": {"title": "t", "description": "Not advice.", "hashtags": ["x"]}},
        "claims": [{"value": "7.2%", "source_ref": "data.cpi"}],
        "disclaimer": "Not financial advice.",
        "layout_data": {"kind": "ranked_list",
            "items": [{"rank": 1, "title": "ACME", "body": "b", "media_query": "q"}]},
    }
