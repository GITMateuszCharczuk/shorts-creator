from stages.s05_render.stage import _safe_rect, _scene_spans, platform_delta


def test_platform_delta_changes_only_declared_fields():
    base = {"fps": 30, "scenes": [], "cta": {"verb": "Follow"}, "safe_bottom_pct": 12}
    yt = platform_delta(base, platform="youtube")
    assert yt["cta"]["verb"] == "Subscribe"        # YT delta
    assert yt["fps"] == 30 and yt["scenes"] == []   # everything else identical


def test_scene_spans_partition_words_into_contiguous_beat_spans():
    words = [{"start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(6)]
    spans = _scene_spans(words, {"beats": [{"kind": "item"}, {"kind": "item"}]})
    assert len(spans) == 2
    # contiguous, non-overlapping spans in word order
    assert spans[0]["end"] <= spans[1]["start"]
    # total coverage: first span starts at the first word, last span ends at the last word
    assert spans[0]["start"] == words[0]["start"]
    assert spans[1]["end"] == words[-1]["end"]
    # each span covers its OWN group's first->last word (6 words / 2 beats = 3 each)
    assert spans[0]["end"] == words[2]["end"]
    assert spans[1]["start"] == words[3]["start"]


def test_safe_rect_tiktok_insets_are_tighter_than_youtube():
    assert _safe_rect("tiktok", {})["h"] < _safe_rect("youtube", {})["h"]


def test_delta_manifest_still_schema_validates():
    # platform_delta injects a top-level "cta", inject_finishing a top-level "loop" + an end_card
    # region + markers.end_card — the schema must accept the DELTA'd AND FINISHED manifest
    # (an M4/M5 gate re-validating it must not fail on additionalProperties)
    import json
    from pathlib import Path

    from shared.layout.finishing import inject_finishing
    from shared.schema import SchemaRegistry
    golden = json.loads((Path(__file__).parent / "fixtures" / "m2"
                         / "render_manifest_golden.json").read_text())
    delta = platform_delta(golden, "tiktok")
    SchemaRegistry().validate("render_manifest", delta)
    finished = inject_finishing(delta, brand_kit={}, seed=3, platform="tiktok")
    SchemaRegistry().validate("render_manifest", finished)


def test_scene_spans_zero_beats_returns_empty():
    assert _scene_spans([{"start": 0.0, "end": 1.0}], {"beats": []}) == []
