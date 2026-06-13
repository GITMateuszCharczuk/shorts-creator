# tests/test_repetition.py
from shared.safety.repetition import _jaccard, not_repetitious


def test_fresh_topic_passes_and_recent_duplicate_fails():
    ledger = [{"topic": "cpi", "hook": "Inflation cooled again"}]
    assert not_repetitious({"topic": "fed", "hook": "The Fed blinked"}, ledger).ok
    assert not not_repetitious({"topic": "cpi", "hook": "Inflation cooled again"}, ledger).ok


def test_same_topic_different_angle_passes():
    ledger = [{"topic": "cpi", "hook": "Inflation cooled again"}]
    assert not_repetitious({"topic": "cpi", "hook": "Why your rent ignores the CPI"}, ledger).ok


# --- Addenda ---


def test_jaccard_symmetry():
    """Addendum: _jaccard(a, b) must equal _jaccard(b, a) for all non-empty inputs."""
    a = "Inflation cooled again"
    b = "Inflation is finally cooling"
    assert _jaccard(a, b) == _jaccard(b, a)


def test_empty_hook_not_repetitious():
    """Addendum: empty-hook case — record hook "" vs ledger hook "" on the same topic.
    _jaccard("", "") returns 0.0 (both sets empty, the (sa or sb) guard is False).
    0.0 < 0.6 threshold, so not_repetitious returns True (passes).
    This is intentional: an empty hook is not a meaningful duplicate."""
    ledger = [{"topic": "cpi", "hook": ""}]
    result = not_repetitious({"topic": "cpi", "hook": ""}, ledger)
    # jaccard of two empty strings is 0.0 -> below hook_sim threshold -> passes
    assert result.ok, (
        "empty hook should not be flagged as repetitious — jaccard 0.0 < 0.6 threshold"
    )
    # confirm jaccard itself
    assert _jaccard("", "") == 0.0
