EXIT_OK = 0
EXIT_DEGRADED = 75      # EX_TEMPFAIL: completed with a degrade (budget trip etc.) — WARN, not fail
EXIT_QUARANTINED = 77   # EX_NOPERM: a gate parked this video


def status_for_exit(code: int) -> str:
    if code in (EXIT_OK, EXIT_DEGRADED):
        return "done"
    if code == EXIT_QUARANTINED:
        return "quarantined"
    return "failed"
