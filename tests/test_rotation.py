import pytest

from shared.planner.rotation import NoFormatError, pick_format

FMTS = [{"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}},
        {"id": "ranked_list", "lane_support": {"reach": True, "monetization": True}},
        {"id": "explainer", "lane_support": {"reach": False, "monetization": True}}]


def test_picks_lane_compatible_and_seed_deterministic():
    a = pick_format(FMTS, lane="reach", recent=[], seed=7)
    assert a["lane_support"]["reach"] and a == pick_format(FMTS, lane="reach", recent=[], seed=7)


def test_anti_repeat_excludes_recent_formats():
    got = pick_format(FMTS, lane="reach", recent=["ranked_list"], seed=7)
    assert got["id"] == "surprising_stat"


def test_no_compatible_format_raises():
    with pytest.raises(NoFormatError):
        pick_format(FMTS, lane="monetization", recent=["ranked_list", "explainer"], seed=7)
