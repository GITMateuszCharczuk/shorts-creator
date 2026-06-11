import json
from typing import Callable

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage
from shared.visual.clip import rank_candidates
from shared.visual.dedup import filter_new
from shared.visual.fallback import AssetChoice, choose_asset
from shared.visual.stock import license_ok, provenance_record


def select_for_beat(*, beat: str, candidates: list[tuple[str, str]],
                    scorer: Callable[[str], float], used_hashes: set[str],
                    stock_threshold: float, ai_available: bool,
                    is_hook: bool) -> AssetChoice:
    fresh = filter_new(candidates, used_hashes)
    ranked_paths = rank_candidates([p for p, _ in fresh], scorer, threshold=0.0)
    stock_ranked = [(p, scorer(p)) for p in ranked_paths]
    return choose_asset(beat=beat, stock_ranked=stock_ranked, stock_threshold=stock_threshold,
                        ai_available=ai_available, is_hook=is_hook)


@stage(StageManifest(id="01a", inputs=["script"], outputs=["scenes_stock", "provenance"],
                     compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    stock = ctx.backends.get("stock")
    if stock is None:
        raise NotImplementedError("01a needs a 'stock' backend (live client at host bring-up; "
                                  "the offline DAG injects a fixture client)")
    used = set(ctx.config.get("used_hashes", []))   # cross-video ledger arrives in M3; config seam
    thr = float(ctx.config.get("stock_threshold", 0.30))
    choices, prov, ai_needed = [], [], []
    for i, beat in enumerate(script.get("narration_beats", [])):
        text = beat.get("text", "")
        cands = stock.search(text, n=4)   # [{"path","phash","score","source","url","license"}...]
        pairs = [(c["path"], c["phash"]) for c in cands if license_ok(c.get("license", ""))]
        scores = {c["path"]: float(c.get("score", 0.0)) for c in cands}
        choice = select_for_beat(beat=text, candidates=pairs,
                                 scorer=lambda p, s=scores: s[p],
                                 used_hashes=used, stock_threshold=thr,
                                 ai_available=True, is_hook=False)
        choices.append({"beat": i, "kind": choice.kind, "ref": choice.ref})
        if choice.kind == "ai":
            ai_needed.append(i)
        if choice.kind == "stock":
            c = next(c for c in cands if c["path"] == choice.ref)
            prov.append(provenance_record(asset_id=c["path"], source=c.get("source", "fixture"),
                                          url=c.get("url", ""), license=c["license"],
                                          fetch_date=c.get("fetch_date", "2026-06-09")))
    out = ctx.write_output("scenes_stock")
    out.write_text(json.dumps({"choices": choices, "ai_needed": ai_needed}))
    pv = ctx.write_output("provenance")
    pv.write_text(json.dumps({"schema_version": "1.0.0", "assets": prov}))
    return StageResult(outputs={"scenes_stock": out, "provenance": pv})
