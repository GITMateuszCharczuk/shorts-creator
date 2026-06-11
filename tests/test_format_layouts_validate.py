import pytest

from shared.schema import SchemaError, SchemaRegistry

REG = SchemaRegistry()


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
