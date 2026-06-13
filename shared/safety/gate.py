from shared.safety.types import CheckResult


def aggregate(results: list[CheckResult]) -> dict:
    """ALL-must-hold (spec Ch.8). Record EVERY check (pass and fail) for the weekly spot-audit
    and the calibration set."""
    checks = [{"name": r.name, "ok": r.ok, **({"detail": r.detail} if r.detail else {})}
              for r in results]
    return {"schema_version": "1.0.0", "passed": all(r.ok for r in results), "checks": checks}
