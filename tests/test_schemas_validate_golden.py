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
