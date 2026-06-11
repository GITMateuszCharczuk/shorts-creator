from shared.safety.types import CheckResult


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / len(sa | sb) if (sa or sb) else 0.0


def not_repetitious(record: dict, ledger: list[dict], *, hook_sim: float = 0.6) -> CheckResult:
    """Repetition = SAME topic AND a near-duplicate hook. Same topic, fresh angle is allowed."""
    for past in ledger:
        if past.get("topic") == record.get("topic") and \
                _jaccard(record.get("hook", ""), past.get("hook", "")) >= hook_sim:
            return CheckResult(
                False, "repetition",
                f"near-duplicate of posted {past.get('topic')!r}",
            )
    return CheckResult(True, "repetition")
