import pytest

from shared.planner.topics import TopicStarvation, claim_topics


def test_claims_skip_ledger_and_intra_batch_duplicates():
    claimed = claim_topics(["cpi", "fed", "cpi", "gold"], ledger_topics={"fed"}, n=2)
    assert claimed == ["cpi", "gold"]            # ledger dedup + intra-batch dedup (ADR 0003 D5)


def test_starvation_raises_when_not_enough_topics():
    with pytest.raises(TopicStarvation):
        claim_topics(["cpi"], ledger_topics={"cpi"}, n=1)
