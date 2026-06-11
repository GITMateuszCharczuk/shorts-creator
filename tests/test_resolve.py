import json
from pathlib import Path

import pytest

from shared.layout.bind import BindError
from shared.layout.resolve import resolve
from shared.schema import SchemaRegistry

FIX = Path(__file__).parent / "fixtures" / "m2"
REG = SchemaRegistry()


def _load(n): return json.loads((FIX / n).read_text())


def test_resolve_emits_manifest_validating_against_schema():
    m = resolve(layout=_load("layout_ranked_list.json"),
                beat_data=_load("beat_data_ranked_list.json"),
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}],
                seed=7)
    REG.validate("render_manifest", m)         # output is a versioned contract (ADR 0007a §2)
    assert m["fps"] == 30 and m["width"] == 1080 and m["height"] == 1920 and m["seed"] == 7
    assert len(m["scenes"]) == 2
    s0 = m["scenes"][0]
    assert s0["start"] == 0.0 and s0["end"] == 2.0
    title = next(r for r in s0["regions"] if r["name"] == "item_title")
    assert title["value"] == "ACME" and title["style"]["size"] == 72
    assert set(title["rect"]) == {"x", "y", "w", "h"}     # projected to PIXELS (§7a)


def test_resolve_is_pure_deterministic():
    args = dict(layout=_load("layout_ranked_list.json"),
                beat_data=_load("beat_data_ranked_list.json"),
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}], seed=7)
    assert resolve(**args) == resolve(**args)


def test_resolve_rejects_unbound_field():
    bad = _load("beat_data_ranked_list.json")
    del bad["beats"][0]["item"]["title"]
    with pytest.raises(BindError):
        resolve(layout=_load("layout_ranked_list.json"), beat_data=bad,
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}], seed=7)


def test_resolve_joins_assets_and_caption_words():
    # the Cluster-1 joins (re-review): MediaZone gets the CHOSEN clip path, captions get WORDS
    m = resolve(layout=_load("layout_ranked_list.json"),
                beat_data=_load("beat_data_ranked_list.json"),
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}], seed=7,
                media={0: "scenes/a.mp4", 1: "scenes/b.mp4"},
                words=[{"word": "Hi", "start": 0.2, "end": 0.5}])
    s0 = m["scenes"][0]
    bg = next(r for r in s0["regions"] if r["name"] == "bg_media")
    assert bg["src"] == "scenes/a.mp4"                      # not the media_query string
    cap = next(r for r in s0["regions"] if r["name"] == "caption")
    assert cap["value"] == [{"word": "Hi", "start": 0.2, "end": 0.5}]
