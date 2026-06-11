import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01b", inputs=["script", "scenes_stock"], outputs=["scenes_gen"],
                     compute="gpu", capability="generate_image"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    stock = json.loads(ctx.read_input("scenes_stock").read_text())
    be = ctx.backend("generate_image")
    beats = script.get("narration_beats", [])
    frames = []
    # per-beat FLUX fill for beats 01a flagged ai_needed; the cache key for this stage folds in
    # model_id + graph_version (ADR 0010 D4) — the M4 conductor reads them off the backend.
    for i in stock.get("ai_needed", []):
        prompt = beats[i].get("text", "") if i < len(beats) else ""
        p = be.generate_image(prompt, ctx.seed)
        frames.append({"beat": i, "path": str(p)})
    out = ctx.write_output("scenes_gen")
    out.write_text(json.dumps({"frames": frames}))
    return StageResult(outputs={"scenes_gen": out})
