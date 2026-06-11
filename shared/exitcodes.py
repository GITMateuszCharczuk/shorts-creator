EXIT_OK = 0
EXIT_DEGRADED = 75      # EX_TEMPFAIL: completed with a degrade (budget trip etc.) — WARN, not fail
EXIT_QUARANTINED = 77   # EX_NOPERM: a gate parked this video
EXIT_HELD = 70          # video awaiting human approval at the publish ramp (ADR 0014 D2)


def status_for_exit(code: int) -> str:
    if code in (EXIT_OK, EXIT_DEGRADED):
        return "done"
    if code == EXIT_QUARANTINED:
        return "quarantined"
    if code == EXIT_HELD:
        return "held"
    return "failed"
