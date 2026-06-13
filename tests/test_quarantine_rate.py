from shared.obs.quarantine_rate import is_spike, trailing_rate


def test_trailing_rate_over_window():
    assert abs(trailing_rate(["done"] * 16 + ["quarantined"] * 4, window=20) - 0.20) < 1e-9


def test_spike_matches_the_alert_two_part_condition():
    assert is_spike(rate=0.35, baseline=0.30, abs_floor=0.30, mult=2.0) is True   # absolute path
    assert is_spike(rate=0.25, baseline=0.10, abs_floor=0.30, mult=2.0) is True   # 2x baseline path
    assert is_spike(rate=0.12, baseline=0.10, abs_floor=0.30, mult=2.0) is False


def test_exact_boundaries_do_not_fire_matching_the_strict_promql():
    # parity with the Task 6 alert rule (strict >): exactly-at-floor / exactly-2x do NOT fire
    assert is_spike(rate=0.30, baseline=0.20, abs_floor=0.30, mult=2.0) is False
    assert is_spike(rate=0.20, baseline=0.10, abs_floor=0.30, mult=2.0) is False


def test_clean_cold_start_is_not_a_spike():
    # zero history (baseline 0) + zero rate must NOT page a brand-new deployment
    assert is_spike(rate=0.0, baseline=0.0, abs_floor=0.30, mult=2.0) is False
    assert trailing_rate([], window=20) == 0.0
