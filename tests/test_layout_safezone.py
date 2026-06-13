import json
from pathlib import Path

from shared.layout.resolve import resolve

FIX = Path(__file__).parent / "fixtures" / "m2"


def _load(n):
    return json.loads((FIX / n).read_text())


def _resolved(safe_rect=None):
    return resolve(
        layout=_load("layout_ranked_list.json"),
        beat_data=_load("beat_data_ranked_list.json"),
        brand_kit=_load("brand_kit.json"),
        timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}],
        seed=7,
        safe_rect=safe_rect,
    )


def _overlaps(a: dict, b: dict) -> bool:
    # vertical overlap of two pixel rects
    return a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def test_no_region_bbox_exceeds_platform_safe_rect():
    # ADR 0007a §10: no region bbox (incl. injected caption/cta_bump) projects outside the
    # platform safe rect for any of the 3 platforms.
    canvas = {"w": 1080, "h": 1920}
    platforms = {
        "tiktok": {"t": 0.10, "r": 0.12, "b": 0.20, "l": 0.04},
        "youtube": {"t": 0.08, "r": 0.06, "b": 0.16, "l": 0.04},
        "reels": {"t": 0.10, "r": 0.10, "b": 0.18, "l": 0.04},
    }
    for name, ins in platforms.items():
        safe = {
            "x": round(canvas["w"] * ins["l"]),
            "y": round(canvas["h"] * ins["t"]),
            "w": round(canvas["w"] * (1 - ins["l"] - ins["r"])),
            "h": round(canvas["h"] * (1 - ins["t"] - ins["b"])),
        }
        m = _resolved(safe_rect=safe)
        for scene in m["scenes"]:
            for r in scene["regions"]:
                rect = r["rect"]
                assert rect["x"] >= safe["x"], f"{name}: {r['name']} left of safe rect"
                assert rect["y"] >= safe["y"], f"{name}: {r['name']} above safe rect"
                assert rect["x"] + rect["w"] <= safe["x"] + safe["w"] + 1, (
                    f"{name}: {r['name']} right of safe rect")
                assert rect["y"] + rect["h"] <= safe["y"] + safe["h"] + 1, (
                    f"{name}: {r['name']} below safe rect")


def test_stat_region_does_not_occlude_caption_band():
    # ADR 0007a §7a: stat (.42-.52) sits well above the caption band (.82-.94). The stat (z=2)
    # must NOT vertically overlap the caption band (z=8) — otherwise the stat is permanently
    # hidden behind the caption in every ranked_list render (the C4 defect).
    m = _resolved()
    scene = m["scenes"][0]
    stat = next(r for r in scene["regions"] if r["name"] == "item_stat")
    caption = next(r for r in scene["regions"] if r["name"] == "caption")
    assert not _overlaps(stat["rect"], caption["rect"]), (
        f"item_stat {stat['rect']} vertically overlaps caption band {caption['rect']} — "
        "the stat is occluded (ADR 0007a §7a/§10)")
    # the stat is the lower-z element; if they DID overlap it would be the occluded one
    assert stat["z"] < caption["z"]
