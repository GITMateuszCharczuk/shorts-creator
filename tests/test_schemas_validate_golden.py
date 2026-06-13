import json
from pathlib import Path

import pytest

from shared.schema import SchemaError, SchemaRegistry

REG = SchemaRegistry()
GOLDEN = Path(__file__).parent / "fixtures" / "golden"


def _job():
    return json.loads((GOLDEN / "job.json").read_text())


def test_rejects_wrong_typed_field():
    bad = _job()
    bad["seed"] = "not-an-int"
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


def test_rejects_missing_required_field():
    bad = _job()
    del bad["video_id"]
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


def test_rejects_major_version_mismatch():
    bad = _job()
    bad["schema_version"] = "2.0.0"
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


def test_rejects_unknown_status_enum():
    bad = _job()
    bad["stages"]["00a"]["status"] = "frozen"
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


ALL_SCHEMAS = ["job", "script", "assets", "provenance", "vision", "qc",
               "creative_qc", "posts", "profile", "format", "feature_record"]


@pytest.mark.parametrize("name", ALL_SCHEMAS)
def test_golden_fixture_validates(name):
    REG.validate(name, json.loads((GOLDEN / f"{name}.json").read_text()))


# --- Bounded QC scores: out-of-range scores must be REJECTED (floor-inflation guard) ---


def test_vision_rejects_out_of_range_visual_score():
    bad = json.loads((GOLDEN / "vision.json").read_text())
    bad["judgment"] = {"visual_scores": {"coherence": 2.0, "pacing": 0.5},
                       "observations": ["clean"]}
    with pytest.raises(SchemaError):
        REG.validate("vision", bad)


def test_creative_qc_rejects_out_of_range_score():
    bad = json.loads((GOLDEN / "creative_qc.json").read_text())
    bad["scores"] = {"hook": 2.0, "original_insight": 0.7}
    with pytest.raises(SchemaError):
        REG.validate("creative_qc", bad)
