import json
from pathlib import Path

import pytest

from shared.schema import SchemaError, SchemaRegistry

REG = SchemaRegistry()
ROOT = Path(__file__).resolve().parents[1]


def test_ranked_list_layout_validates():
    REG.validate("layout", json.loads((ROOT / "formats/ranked_list/layout.json").read_text()))


def test_head_to_head_layout_validates():
    REG.validate("layout", json.loads((ROOT / "formats/head_to_head/layout.json").read_text()))


def test_layout_rejects_bbox_with_neither_anchor_nor_yh():
    # oneOf: vertical must be a named anchor OR a literal {y,h} — neither is invalid
    bad = json.loads((ROOT / "formats/ranked_list/layout.json").read_text())
    del bad["regions"][0]["bbox"]["y"]
    del bad["regions"][0]["bbox"]["h"]
    with pytest.raises(SchemaError):
        REG.validate("layout", bad)


def test_layout_rejects_unknown_primitive():
    bad = json.loads((ROOT / "formats/ranked_list/layout.json").read_text())
    bad["regions"][0]["primitive"]["type"] = "SparkleZone"
    with pytest.raises(SchemaError):
        REG.validate("layout", bad)
