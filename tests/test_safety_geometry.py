# tests/test_safety_geometry.py
from shared.safety.geometry import DEFAULT_SAFE_ZONES, in_safe_zone


def test_tiktok_right_rail_and_caption_band_are_unsafe():
    assert not in_safe_zone({"x": 980, "y": 1200, "w": 80, "h": 80}, platform="tiktok").ok
    assert in_safe_zone({"x": 120, "y": 900, "w": 600, "h": 200}, platform="tiktok").ok


def test_zones_are_config_overridable():
    zones = {"reels": {"x0": 0, "x1": 1080, "y0": 0, "y1": 1920}}     # a new platform via config
    assert in_safe_zone({"x": 10, "y": 10, "w": 10, "h": 10}, platform="reels", zones=zones).ok


def test_unknown_platform_uses_strictest_zone():
    z = DEFAULT_SAFE_ZONES["_strict"]
    assert in_safe_zone({"x": z["x0"], "y": z["y0"], "w": 10, "h": 10}, platform="???").ok
