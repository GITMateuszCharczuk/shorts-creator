from shared.obs.baselines import classify, stage_baselines


def test_nearest_rank_p95_is_exact():
    timings = [{"stage": "05", "elapsed_s": s} for s in (100, 110, 120, 130, 900)]
    assert stage_baselines(timings)["05"] == 900        # nearest-rank p95 of 5 = the top sample


def test_classify_running_slow_vs_stuck_only_when_running():
    base = {"05": 120.0}
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600,
                    last_heartbeat_age_s=5, running=1) == "ok"
    assert classify("05", elapsed_s=250, base=base, hard_deadline_s=600,
                    last_heartbeat_age_s=5, running=1) == "slow"
    assert classify("05", elapsed_s=700, base=base, hard_deadline_s=600,
                    last_heartbeat_age_s=5, running=1) == "stuck"
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600,
                    last_heartbeat_age_s=300, running=1) == "stuck"
    # a COMPLETED stage (running=0) is never slow/stuck regardless of a stale heartbeat file
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600,
                    last_heartbeat_age_s=99999, running=0) == "ok"


def test_unknown_stage_never_falsely_slow():
    assert classify("99", elapsed_s=10, base={}, hard_deadline_s=600,
                    last_heartbeat_age_s=1, running=1) == "ok"
