from shared.visual.dedup import filter_new, is_duplicate


def test_near_identical_hash_is_duplicate():
    assert is_duplicate("ffff0000ffff0000", {"ffff0000ffff0001"}, max_distance=2) is True


def test_distinct_hash_kept():
    assert is_duplicate("ffff0000ffff0000", {"0000ffff0000ffff"}, max_distance=2) is False


def test_filter_new_drops_seen():
    cands = [("a.jpg", "ffff0000ffff0000"), ("b.jpg", "0000ffff0000ffff")]
    used = {"ffff0000ffff0001"}
    assert filter_new(cands, used, max_distance=2) == [("b.jpg", "0000ffff0000ffff")]


# Controller addendum: malformed hash contract
# - malformed USED entry → skipped (treated as non-matching); ledger self-heals
# - malformed CANDIDATE hash → raises ValueError (locally computed; indicates a code bug)

def test_malformed_used_entry_is_skipped():
    """A corrupt ledger entry ('zz...') is non-parseable; is_duplicate silently skips it."""
    assert is_duplicate("ffff0000ffff0000", {"zz", "0000ffff0000ffff"}, max_distance=2) is False


def test_malformed_candidate_raises():
    """A bad candidate hash is a local bug; ValueError must propagate so the caller notices."""
    import pytest
    with pytest.raises(ValueError):
        is_duplicate("zz", {"ffff0000ffff0000"}, max_distance=2)
