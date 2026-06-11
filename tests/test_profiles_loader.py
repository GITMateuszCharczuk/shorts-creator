from pathlib import Path

import pytest
import yaml

from shared.profiles.loader import load_profile
from shared.schema import SchemaError

ROOT = Path(__file__).resolve().parents[1]


def test_finance_and_business_profiles_load_and_validate():
    for niche in ("finance", "business"):
        p = load_profile(ROOT / "profiles" / niche / "profile.yaml")
        assert p["niche"] == niche
        assert {"palette", "font", "logo"} <= set(p["brand_kit"])
        assert p["persona"]["voice"]


def test_profile_requires_stances(tmp_path):
    # ADR 0017 D3: a persona without stances has nothing for 00b to ARGUE FROM -> invalid
    profile = yaml.safe_load((ROOT / "profiles/finance/profile.yaml").read_text())
    del profile["persona"]["stances"]
    bad = tmp_path / "profile.yaml"
    bad.write_text(yaml.safe_dump(profile))
    with pytest.raises(SchemaError):
        load_profile(bad)
