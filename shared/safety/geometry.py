from shared.safety.types import CheckResult

DEFAULT_SAFE_ZONES = {
    "tiktok":  {"x0": 40, "x1": 950, "y0": 80, "y1": 1500},   # right-rail >950, caption band >1500
    "youtube": {"x0": 40, "x1": 1040, "y0": 80, "y1": 1800},  # lower controls >1800
    "_strict": {"x0": 40, "x1": 950, "y0": 80, "y1": 1500},
}


def in_safe_zone(rect: dict, *, platform: str, zones: dict | None = None) -> CheckResult:
    table = zones or DEFAULT_SAFE_ZONES
    z = table.get(platform) or table.get("_strict") or DEFAULT_SAFE_ZONES["_strict"]
    ok = (rect["x"] >= z["x0"] and rect["x"] + rect["w"] <= z["x1"]
          and rect["y"] >= z["y0"] and rect["y"] + rect["h"] <= z["y1"])
    return CheckResult(ok, "safe_zone", "" if ok else f"CTA rect outside {platform} safe zone {z}")
