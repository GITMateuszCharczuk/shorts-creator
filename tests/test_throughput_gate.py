import pytest

from shared.conductor.throughput import ThroughputBust, project_batch


def test_projection_sums_stage_means_times_videos():
    timings = [{"stage": "00b", "elapsed_s": 300.0}, {"stage": "00b", "elapsed_s": 500.0},
               {"stage": "05", "elapsed_s": 600.0}]
    p = project_batch(timings, n_videos=4, window_hours=8.0)
    assert p["per_video_s"] == 1000.0             # mean(00b)=400 + mean(05)=600
    assert p["batch_s"] == 4000.0 and p["fits"] is True


def test_bust_raises_with_the_breakdown():
    timings = [{"stage": "05", "elapsed_s": 14400.0}]
    with pytest.raises(ThroughputBust):
        project_batch(timings, n_videos=4, window_hours=8.0, raise_on_bust=True)


@pytest.mark.integration
def test_overnight_window_gate_on_the_box():
    import json
    from pathlib import Path
    timings = [json.loads(line)
               for line in Path("runs/.metrics/timing.jsonl").read_text().splitlines()]
    report = project_batch(timings, n_videos=4, window_hours=8.0, raise_on_bust=True)
    Path("runs/.metrics/throughput_report.json").write_text(json.dumps(report))


def test_empty_timings_never_pass_the_gate():
    with pytest.raises(ThroughputBust):
        project_batch([], n_videos=4, window_hours=8.0, raise_on_bust=True)


def test_partial_run_timings_rejected_when_stage_set_required():
    with pytest.raises(ThroughputBust, match="missing required stages"):
        project_batch([{"stage": "00b", "elapsed_s": 1.0}], n_videos=1, window_hours=8.0,
                      required_stages={"00b", "05"})


def test_series_due_slot_honored_first():
    from shared.planner.batch import plan_batch
    fmts = [{"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}}]
    b = plan_batch(batch_id="b", niches=["finance"], per_niche=1, formats=fmts,
                   lane_history=[], topic_candidates=["cpi"], ledger_topics=set(),
                   monetization_share=0.20, master_seed=1,
                   series_due={"finance": {"format": "market_30s", "lane": "reach"}})
    v = b["videos"][0]
    assert v["format"] == "market_30s" and v["lane"] == "reach"   # the fixed series slot
