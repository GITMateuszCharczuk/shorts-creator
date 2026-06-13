import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage

# NB: the Remotion bridge (shared.layout.remotion, Task 11) is NOT imported at module level —
# it does not exist until Phase B3, and a module-level import would crash the stage registry.
# run() writes the chart SPECS; the bridge render call is wired when the bridge lands.


def chart_spec(data: dict, keys: list[str], kind: str, brand: dict,
               section: str = "market") -> dict:
    return {"kind": kind, "accent": brand["accent"],
            "series": [{"label": k, "value": data[section][k]["value"]} for k in keys]}


@stage(StageManifest(id="01e", inputs=["data", "script"], outputs=["scenes_viz"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    data = json.loads(ctx.read_input("data").read_text())
    script = json.loads(ctx.read_input("script").read_text())
    brand = {"accent": ctx.config.get("brand_accent", "#00E5FF")}
    keys = list(ctx.config.get("viz_keys", list(data.get("market", {}).keys())[:2]))
    keys = [k for k in keys if k in data.get("market", {})]   # a stale config key must not crash
    charts = []
    # ADR 0017 D2: data-viz is preferred wherever a number exists — M2-interim heuristic: any
    # beat whose text carries a digit gets a chart spec; Remotion renders them via the bridge.
    for i, beat in enumerate(script.get("narration_beats", [])):
        if keys and any(ch.isdigit() for ch in beat.get("text", "")):
            charts.append({"beat": i, "spec": chart_spec(data, keys=keys, kind="bar",
                                                         brand=brand)})
    out = ctx.write_output("scenes_viz")
    out.write_text(json.dumps({"charts": charts}))
    return StageResult(outputs={"scenes_viz": out})
