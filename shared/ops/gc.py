PROTECTED = {"history", "models"}        # never GC'd: unrecoverable state + weight cache


def runs_to_delete(runs: list[dict], *, keep_days: int = 7, keep_count: int = 14,
                   protected_ids: set[str] | None = None) -> list[dict]:
    """Delete a run only if older than keep_days AND outside the newest keep_count AND not in
    protected_ids (the current batch + any reconciler-resumed batch — ADR 0003 D9: GC must never
    reclaim a run the boot reconciler just re-ran)."""
    protected = PROTECTED | (protected_ids or set())   # PROTECTED is never-GC by default (D9)
    kept_by_count = {r["id"] for r in sorted(runs, key=lambda r: r["age_days"])[:keep_count]}
    return [r for r in runs if r["age_days"] > keep_days
            and r["id"] not in kept_by_count and r["id"] not in protected]


def quarantine_to_delete(quarantines: list[dict], *, keep_days: int = 30) -> list[dict]:
    return [q for q in quarantines if q["age_days"] > keep_days]
