import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01a", inputs=["script"], outputs=["scenes_stock", "provenance"],
                     compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    json.loads(ctx.read_input("script").read_text())  # script available to the planner
    stock = ctx.write_output("scenes_stock")
    stock.write_text(json.dumps({"clips": [{"beat_id": "hook", "query": "acme logo"}]}))
    prov = ctx.write_output("provenance")
    prov.write_text(json.dumps({"schema_version": "1.0.0",
        "assets": [{"asset_id": "a0", "source": "pexels", "url": "https://pexels.com/x",
                    "license": "Pexels", "fetch_date": "2026-06-09"}]}))
    return StageResult(outputs={"scenes_stock": stock, "provenance": prov})
