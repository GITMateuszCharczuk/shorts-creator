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
