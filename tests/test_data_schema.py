import json
from pathlib import Path

import pytest

from shared.schema import SchemaError, SchemaRegistry

REG = SchemaRegistry()
FIX = Path(__file__).parent / "fixtures" / "m1"


def _golden() -> dict:
    return json.loads((FIX / "data.json").read_text())


def test_data_golden_validates():
    REG.validate("data", _golden())


@pytest.mark.parametrize("mutate", [
    lambda d: d["market"].__setitem__("cpi_yoy", {"value": "3.2", "source": "x", "as_of": "y"}),
    lambda d: d["news"][0].pop("url"),
    lambda d: d.__setitem__("extra_top_level", 1),
    lambda d: d.__setitem__("market", {}),        # zero-data fetch must fail at the gate
])
def test_data_schema_rejects_malformed(mutate):
    bad = _golden()
    mutate(bad)
    with pytest.raises(SchemaError):
        REG.validate("data", bad)
