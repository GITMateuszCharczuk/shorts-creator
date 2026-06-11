# tests/test_safety_checks.py
from shared.safety.checks import (
    artifact_clear,
    disclaimer_present,
    disclosure_set,
    no_prohibited_claims,
    profanity_clear,
    sources_cited,
)

PROFILE = {
    "defaults": {
        "disclaimer": "Educational only — not financial advice.",
        "denylist_terms": ["guaranteed", "you should buy"],
    }
}


def test_disclaimer_must_match_the_profile():
    assert disclaimer_present(
        {"disclaimer": "Educational only — not financial advice."}, PROFILE
    ).ok
    assert not disclaimer_present({"disclaimer": ""}, PROFILE).ok


def test_prohibited_terms_come_FROM_THE_PROFILE_not_hardcoded():
    # a term the profile does NOT list must pass; a listed term must fail -> proves data-driven
    p = {"defaults": {"disclaimer": "d", "denylist_terms": ["sasquatch"]}}
    assert no_prohibited_claims({"narration_beats": [{"text": "you should buy this"}]}, p).ok
    bad = no_prohibited_claims({"narration_beats": [{"text": "a wild sasquatch appears"}]}, p)
    assert not bad.ok and "sasquatch" in bad.detail


def test_sources_must_be_cited():
    assert sources_cited({"claims": [{"value": "3.2%", "source_ref": "data.cpi"}]}).ok
    assert not sources_cited({"claims": []}).ok


def test_ai_disclosure_flag_required():
    assert disclosure_set({"platform_meta": {"ai_disclosure": True}}).ok
    assert not disclosure_set({"platform_meta": {"ai_disclosure": False}}).ok


def test_profanity_uses_profile_wordlist_then_default():
    assert profanity_clear(
        {"narration_beats": [{"text": "clean copy"}]}, wordlist={"badword"}
    ).ok
    assert not profanity_clear(
        {"narration_beats": [{"text": "a badword here"}]}, wordlist={"badword"}
    ).ok


def test_artifact_check_reads_vision_observations():
    clean = {"judgment": {"observations": ["clean composition", "text legible"]}}
    dirty = {"judgment": {"observations": ["hand morphing in frame 3", "garbled text on end card"]}}
    assert artifact_clear(clean).ok
    bad = artifact_clear(dirty)
    assert not bad.ok and ("morph" in bad.detail or "garbled" in bad.detail)


# --- Addenda ---


def test_disclaimer_fails_when_script_has_different_disclaimer():
    """Addendum: substring match is NOT enough — the impl requires exact match (after strip).
    A script carrying a non-empty but DIFFERENT disclaimer must still fail."""
    different = {"disclaimer": "Educational only"}  # substring of the profile disclaimer
    result = disclaimer_present(different, PROFILE)
    assert not result.ok, (
        "different disclaimer (even a substring) must fail — exact match required"
    )
    assert "disclaimer != profile" in result.detail


def test_prohibited_claims_matches_term_in_captions():
    """Addendum: _text() concatenates narration_beats AND captions — a denylist term that
    appears only in captions (not narration) must still be caught."""
    script = {
        "narration_beats": [{"text": "markets moved today"}],
        "captions": [{"text": "guaranteed returns for everyone"}],
    }
    p = {"defaults": {"disclaimer": "d", "denylist_terms": ["guaranteed"]}}
    result = no_prohibited_claims(script, p)
    assert not result.ok, "denylist term in captions must be caught by no_prohibited_claims"
    assert "guaranteed" in result.detail


def test_profanity_with_attached_punctuation_is_caught():
    # "damn!" must NOT slip past the token match (HIGH false-negative class)
    assert not profanity_clear({"narration_beats": [{"text": "oh damn!"}]},
                               wordlist={"damn"}).ok
    assert not profanity_clear({"captions": [{"text": "what the hell,"}]},
                               wordlist={"hell"}).ok


def test_prohibited_term_matches_hyphen_space_variants():
    p = {"defaults": {"disclaimer": "d", "denylist_terms": ["risk-free"]}}
    assert not no_prohibited_claims({"narration_beats": [{"text": "a risk free bet"}]}, p).ok
    p2 = {"defaults": {"disclaimer": "d", "denylist_terms": ["risk free"]}}
    assert not no_prohibited_claims({"narration_beats": [{"text": "a risk-free bet"}]}, p2).ok
