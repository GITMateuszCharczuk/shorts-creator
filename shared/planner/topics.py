class TopicStarvation(Exception):
    """Fewer fresh topics than videos — the ADR 0002 starvation ladder triggers upstream."""


def claim_topics(candidates: list[str], *, ledger_topics: set[str], n: int) -> list[str]:
    """Reserve n topics: skip anything in the cross-run ledger AND anything already claimed in
    this batch (the intra-batch claim, ADR 0003 D5)."""
    claimed: list[str] = []
    for t in candidates:
        if t in ledger_topics or t in claimed:
            continue
        claimed.append(t)
        if len(claimed) == n:
            return claimed
    raise TopicStarvation(f"needed {n} fresh topics, found {len(claimed)}")
