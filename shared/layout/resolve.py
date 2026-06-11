import random as _random
from typing import Any

from shared.layout.bind import BindError, validate_binds

# §7a default named anchors: name -> [y, h] as fractions of the safe rect.
DEFAULT_ANCHORS = {
    "badge": [0.06, 0.10], "headline": [0.62, 0.16], "stat": [0.80, 0.12],
    "label": [0.04, 0.10], "caption": [0.82, 0.12],
}


def _standard_regions() -> list[dict]:
    # §6 standard regions injected into every layout (caption band + brand bug).
    return [
        {"name": "caption", "bbox": {"colA": 1, "colB": 12, "anchor": "caption"}, "z": 8,
         "primitive": {"type": "KaraokeCaption", "params": {}}, "bind": "static",
         "enter": "none", "exit": "none", "style": "brand.caption"},
        {"name": "brand_overlay", "bbox": {"colA": 9, "colB": 12, "y": 0.02, "h": 0.06}, "z": 9,
         "primitive": {"type": "BrandOverlay", "params": {}}, "bind": "static",
         "enter": "none", "exit": "none", "style": "brand.bug"},
    ]


def _project(bbox: dict, anchors: dict, safe: dict) -> dict:
    # review-driven guard: colB < colA produces w <= 0 — reject eagerly
    if bbox["colB"] < bbox["colA"]:
        raise BindError("bbox colB < colA in region projection")
    col_w = safe["w"] / 12.0
    x = safe["x"] + (bbox["colA"] - 1) * col_w
    w = (bbox["colB"] - bbox["colA"] + 1) * col_w          # colA-colB INCLUSIVE (§7a)
    if "anchor" in bbox:
        if bbox["anchor"] not in anchors:
            raise BindError(
                f"anchor {bbox['anchor']!r} not in defaults ∪ format anchors (§3)"
            )
        y_frac, h_frac = anchors[bbox["anchor"]]
    else:
        y_frac, h_frac = bbox["y"], bbox["h"]
    # NOTE: anchor fractions outside 0..1 are schema-legal; _project does not clamp (M2 scope)
    return {"x": round(x), "y": round(safe["y"] + y_frac * safe["h"]),
            "w": round(w), "h": round(h_frac * safe["h"])}


def _applies(region: dict, beat: dict) -> bool:
    on = region.get("on")
    if on is not None:                       # explicit beat-kind gate (e.g. vs_badge -> round)
        return beat["kind"] in on
    if region["bind"] == "static":           # §6 standard regions ride every beat
        return True
    return region["bind"].split(".")[0] in beat   # data-driven: bind root present in this beat


def _resolve_bind(bind: str, beat: dict, primitive: dict) -> Any:
    if bind == "static":
        return primitive.get("params", {}).get("content")   # §3: content from the primitive
    node: Any = beat
    for part in bind.split("."):
        if not isinstance(node, dict) or part not in node:
            raise BindError(f"bind {bind!r} missing in beat {beat.get('kind')!r}")
        node = node[part]
    return node


def resolve(
    *, layout: dict, beat_data: dict, brand_kit: dict, timings: list[dict],
    seed: int, safe_rect: dict | None = None,
    media: dict[int, str] | None = None, words: list[dict] | None = None,
) -> dict:
    """Pure fn: layout + typed beat data + THE VISUAL LANE'S CHOSEN ASSETS (`media`: beat index ->
    DATA_ROOT-relative clip path, from assets.json) + brand kit + word timings (`words`, threaded
    into KaraokeCaption) + seed -> render_manifest with PROJECTED PIXEL rects, §6 injected regions,
    and marker frame-indices (ADR 0007a §2)."""
    safe = safe_rect or {"x": 0, "y": 0, "w": 1080, "h": 1920}
    anchors = {**DEFAULT_ANCHORS, **layout.get("anchors", {})}
    beats = beat_data["beats"]
    all_regions = layout["regions"] + _standard_regions()
    styles = brand_kit.get("styles", {})
    fps = 30

    # author-time bind validation (§3): every non-static bind must exist in the format
    # contract (union of all beat shapes), regardless of which beat renders it.
    contract: dict = {}
    for b in beats:
        contract.update({k: v for k, v in b.items() if k != "kind"})
    validate_binds([r["bind"] for r in all_regions], contract)

    scenes, markers = [], {}
    for i, (beat, t) in enumerate(zip(beats, timings)):
        regs = []
        for r in all_regions:
            if not _applies(r, beat):
                continue
            ptype = r["primitive"]["type"]
            reg = {
                "name": r["name"], "primitive": r["primitive"],
                "rect": _project(r["bbox"], anchors, safe),
                "z": r["z"], "enter": r.get("enter", "none"), "exit": r.get("exit", "none"),
                "value": _resolve_bind(r["bind"], beat, r["primitive"]),
                "style": styles.get(r.get("style", ""), {}),
            }
            if ptype == "MediaZone":
                # the assets.json JOIN (re-review): render the visual lane's CHOSEN clip —
                # the bound media_query stays in `value` for provenance, the path goes in `src`.
                reg["src"] = (media or {}).get(i)
            if ptype == "KaraokeCaption":
                # word-timed captions need the WORDS, not just scene spans (ADR 0007a §4)
                reg["value"] = [w for w in (words or [])
                                if t["start"] <= w["start"] < t["end"]]
            regs.append(reg)
            if r["name"] in ("cta_bump", "vs_badge"):   # named markers for §10 golden samples
                markers[r["name"]] = round(t["start"] * fps)
        scenes.append({"start": t["start"], "end": t["end"], "kind": beat["kind"],
                       "regions": sorted(regs, key=lambda x: x["z"])})

    # §6 injected CTABump (ADR 0005 D10): one SEEDED mid-roll bump on an eligible body scene —
    # never the hook/cta/first/last, never stepping on the moments that carry the video.
    eligible = [i for i, s in enumerate(scenes)
                if 0 < i < len(scenes) - 1 and s["kind"] not in ("hook", "cta")]
    if eligible:
        i = _random.Random(seed).choice(eligible)
        scenes[i]["regions"].append({
            "name": "cta_bump",
            "primitive": {"type": "CTABump", "params": {"verb": "Follow"}},
            "rect": _project({"colA": 3, "colB": 10, "anchor": "caption"}, anchors, safe),
            "z": 7, "enter": "pop", "exit": "fade", "value": None,
            "style": styles.get("brand.cta", {}),
        })
        scenes[i]["regions"].sort(key=lambda x: x["z"])
        markers["cta_bump"] = round(scenes[i]["start"] * fps)

    return {"schema_version": "1.0.0", "fps": fps, "width": 1080, "height": 1920, "seed": seed,
            "accent": brand_kit.get("accent"), "safe_rect": safe, "markers": markers,
            "scenes": scenes}
