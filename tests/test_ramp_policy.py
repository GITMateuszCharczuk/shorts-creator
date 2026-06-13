from shared.ramp.policy import DEFAULT_RAMP, can_widen_cadence, gate_active


def test_gate_lift_uses_the_LENIENT_bar():
    # approved_days is passed via cfg-injected accessor in real use; the test stubs it on the state
    s = {"approved": 10, "rejected": 1, "strikes": 0, "first_approval_ts": _days_ago(7)}
    assert gate_active(s, {}) is False                       # 10/7d/<=1 rejection -> lifted
    not_yet = {"approved": 5, "rejected": 0, "strikes": 0, "first_approval_ts": _days_ago(7)}
    assert gate_active(not_yet, {}) is True


def test_a_strike_keeps_the_gate_active():
    s = {"approved": 99, "rejected": 0, "strikes": 1, "first_approval_ts": _days_ago(99)}
    assert gate_active(s, {}) is True


def test_cadence_widening_uses_the_STRICTER_bar():
    lenient_only = {"approved": 12, "rejected": 1, "strikes": 0, "first_approval_ts": _days_ago(8)}
    assert gate_active(lenient_only, {}) is False             # gate lifted...
    assert can_widen_cadence(lenient_only, {}) is False       # ...but not enough to widen cadence
    strong = {"approved": 20, "rejected": 0, "strikes": 0, "first_approval_ts": _days_ago(14)}
    assert can_widen_cadence(strong, {}) is True
    assert DEFAULT_RAMP["lift"]["min_approved"] == 10
    assert DEFAULT_RAMP["widen"]["min_approved"] == 20


def _days_ago(n):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()
