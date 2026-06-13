import json
from pathlib import Path

import pytest

from shared.schema import SchemaError, SchemaRegistry

REG = SchemaRegistry()

ROOT = Path(__file__).resolve().parents[1]
ALL_FORMATS = [
    "ranked_list",
    "head_to_head",
    "myth_buster",
    "explainer",
    "news_reaction",
    "cautionary_tale",
    "surprising_stat",
    "how_to_steps",
]


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_layout_validates(fmt):
    REG.validate("layout", json.loads((ROOT / f"formats/{fmt}/layout.json").read_text()))


def _script(layout_data: dict) -> dict:
    return {
        "schema_version": "1.0.0",
        "format": layout_data["kind"],
        "treatment": {
            "thesis": "t",
            "angle": "a",
            "tone": "x",
            "visual_motif": ["m"],
            "energy_curve": [0.3, 1.0],
        },
        "hook": {
            "spoken": "h",
            "on_screen_text": "h",
            "first_frame_visual": "card",
            "duration": 1.8,
        },
        "narration_beats": [{"text": "n"}],
        "captions": [{"text": "c"}],
        "music": {"mood": "confident", "energy": "mid"},
        "platform_meta": {
            "youtube": {
                "title": "t",
                "description": "Not advice.",
                "hashtags": ["x"],
            }
        },
        "claims": [],
        "disclaimer": "Not financial advice.",
        "layout_data": layout_data,
    }


_VALID_INSTANCES = [
    pytest.param(
        {
            "kind": "myth_buster",
            "claim": {"text": "You need 10k to start investing"},
            "why_wrong": {"text": "Fractional shares exist"},
            "truth": {"text": "You can start with $1"},
        },
        id="myth_buster",
    ),
    pytest.param(
        {
            "kind": "explainer",
            "concept": {"title": "Compound interest"},
            "steps": [{"label": "Year 1", "value": "$100"}],
            "takeaway": {"text": "Start early"},
        },
        id="explainer",
    ),
    pytest.param(
        {
            "kind": "news_reaction",
            "event": {"headline": "Fed raises rates", "source_ref": "reuters.fed_2024"},
            "implications": [{"text": "Mortgage costs rise"}],
            "takeaway": {"text": "Lock in rates now"},
        },
        id="news_reaction",
    ),
    pytest.param(
        {
            "kind": "cautionary_tale",
            "setup": {"text": "Bought at the top"},
            "mistake": {"text": "No stop-loss"},
            "cost": {"stat": "-40%"},
            "lesson": {"text": "Always set a stop-loss"},
        },
        id="cautionary_tale",
    ),
    pytest.param(
        {
            "kind": "surprising_stat",
            "stat": {"value": "90%", "source_ref": "market.day_traders"},
            "unpack": {"text": "u"},
            "so_what": {"text": "s"},
        },
        id="surprising_stat",
    ),
    pytest.param(
        {
            "kind": "how_to_steps",
            "steps": [{"n": 1, "title": "Open account", "body": "Go to broker site"}],
        },
        id="how_to_steps",
    ),
]


@pytest.mark.parametrize("layout_data", _VALID_INSTANCES)
def test_new_layout_kinds_validate(layout_data: dict) -> None:
    REG.validate("script", _script(layout_data))


def test_surprising_stat_layout_data_validates() -> None:
    REG.validate(
        "script",
        _script(
            {
                "kind": "surprising_stat",
                "stat": {"value": "90%", "source_ref": "market.day_traders"},
                "unpack": {"text": "u"},
                "so_what": {"text": "s"},
            }
        ),
    )


def test_malformed_layout_data_rejected() -> None:
    with pytest.raises(SchemaError):
        REG.validate(
            "script",
            _script(
                {
                    "kind": "surprising_stat",
                    "stat": {"value": "90%"},  # missing source_ref
                }
            ),
        )


def test_zero_step_formats_rejected():
    # a steps/implications array with 0 entries would produce 0 render beats — fail at the gate
    with pytest.raises(SchemaError):
        REG.validate("script", _script({"kind": "how_to_steps", "steps": []}))
    with pytest.raises(SchemaError):
        REG.validate("script", _script({"kind": "explainer", "concept": {"title": "t"},
                                        "steps": [], "takeaway": {"text": "t"}}))


def test_indexed_bind_resolves_and_missing_raises():
    import pytest as _pt

    from shared.layout.bind import BindError, _exists
    from shared.layout.resolve import _resolve_bind
    beat = {"kind": "implication", "implications": [{"text": "first"}]}
    assert _exists("implications.0.text", beat) is True
    assert _resolve_bind("implications.0.text", beat, {"params": {}}) == "first"
    with _pt.raises(BindError):
        _resolve_bind("implications.5.text", beat, {"params": {}})
