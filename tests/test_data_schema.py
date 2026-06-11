import json
from pathlib import Path

from shared.schema import SchemaRegistry

REG = SchemaRegistry()
FIX = Path(__file__).parent / "fixtures" / "m1"


def test_data_golden_validates():
    REG.validate("data", json.loads((FIX / "data.json").read_text()))
