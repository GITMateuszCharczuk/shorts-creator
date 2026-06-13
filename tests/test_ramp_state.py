from datetime import datetime, timedelta, timezone

from shared.ramp.state import (
    approved_days,
    is_warmed,
    load_state,
    mark_provisioned,
    record_decision,
)


def test_load_defaults_for_a_new_niche(tmp_path):
    s = load_state(tmp_path / "ramp.finance.json")
    assert s["approved"] == 0 and s["rejected"] == 0 and s["warming_until"] is None
    assert s["first_approval_ts"] is None and s["approved_videos"] == {}


def test_record_decision_increments_persists_and_stamps_first_approval(tmp_path):
    p = tmp_path / "ramp.finance.json"
    record_decision(p, video_id="v1", approved=True)
    record_decision(p, video_id="v2", approved=False)
    s = load_state(p)
    assert s["approved"] == 1 and s["rejected"] == 1
    assert s["approved_videos"] == {"v1": True, "v2": False}
    assert s["first_approval_ts"] is not None              # stamped on the first approval


def test_is_warmed_is_a_calendar_predicate(tmp_path):
    p = tmp_path / "ramp.finance.json"
    assert is_warmed(load_state(p)) is False               # not provisioned -> not warmed
    mark_provisioned(p, warming_days=7)
    assert is_warmed(load_state(p)) is False                # within the window
    past = {"warming_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
    assert is_warmed(past) is True                          # window elapsed


def test_approved_days_counts_distinct_calendar_days(tmp_path):
    s = {"first_approval_ts": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()}
    assert approved_days(s) >= 10
