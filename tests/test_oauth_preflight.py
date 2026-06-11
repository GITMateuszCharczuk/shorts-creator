import pytest

from shared.conductor.preflight import PreflightFailure, oauth_token_age_gate


def test_testing_mode_enforces_7_day_margin():
    oauth_token_age_gate(token_age_days=2.0, mode="testing")          # ok
    with pytest.raises(PreflightFailure):
        oauth_token_age_gate(token_age_days=8.0, mode="testing")      # > 6d margin -> would expire


def test_production_mode_checks_inactivity_not_issue_age():
    # Production refresh tokens don't expire on a 7-day schedule; only long inactivity/revocation.
    oauth_token_age_gate(token_age_days=40.0, last_used_days=3.0, mode="production")    # ok
    with pytest.raises(PreflightFailure):
        # ~6mo idle
        oauth_token_age_gate(token_age_days=40.0, last_used_days=200.0, mode="production")
