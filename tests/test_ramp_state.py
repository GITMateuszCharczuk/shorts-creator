from datetime import datetime, timedelta, timezone

from shared.ramp.policy import gate_active
from shared.ramp.state import (
    approved_days,
    is_warmed,
    load_state,
    mark_provisioned,
    record_decision,
    record_strike,
)


def _days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


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


def test_record_strike_increments_logs_and_persists(tmp_path):
    p = tmp_path / "ramp.finance.json"
    record_strike(p, note="yt copyright")
    record_strike(p, note="tiktok guideline")
    s = load_state(p)                                       # reload from disk
    assert s["strikes"] == 2
    assert [e["note"] for e in s["strike_log"]] == ["yt copyright", "tiktok guideline"]
    assert all(e["ts"] for e in s["strike_log"])            # each entry stamped


def test_a_recorded_strike_keeps_the_gate_active(tmp_path):
    # An otherwise lift-passing state (10 approvals / 7 days / <=1 rejection) would lift the gate;
    # one real recorded strike must hold it ACTIVE through the real gate_active.
    p = tmp_path / "ramp.finance.json"
    for i in range(10):
        record_decision(p, video_id=f"v{i}", approved=True)
    s = load_state(p)
    s["first_approval_ts"] = _days_ago(7)
    assert gate_active(s, {}) is False                      # lift bar met -> gate lifts
    record_strike(p, note="strike")
    s2 = {**load_state(p), "first_approval_ts": _days_ago(7)}
    assert s2["strikes"] == 1
    assert gate_active(s2, {}) is True                      # one strike re-activates the gate


def test_load_state_returns_independent_strike_logs(tmp_path):
    # Aliasing fix: two loads of a missing path must NOT share the _DEFAULT mutable list.
    missing = tmp_path / "absent.json"
    a = load_state(missing)
    b = load_state(missing)
    a["strike_log"].append({"ts": "x", "note": "mutate-a"})
    assert b["strike_log"] == []                            # b unaffected by mutating a
    from shared.ramp.state import _DEFAULT
    assert _DEFAULT["strike_log"] == []                     # module global untouched
