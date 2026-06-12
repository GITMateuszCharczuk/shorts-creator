from shared.obs.metrics import render_batch_metrics, render_stage_metrics, write_metrics


def test_stage_metrics_carry_running_gauge_and_heartbeat():
    text = render_stage_metrics(batch_id="b1", stage="05b", video_id="v1", duration_s=12.5,
                                status="done", running=0, heartbeat_ts=1718000000)
    assert 'shorts_stage_duration_seconds{batch="b1",stage="05b",video="v1"} 12.5' in text
    assert 'shorts_stage_running{batch="b1",stage="05b",video="v1"} 0' in text
    assert "shorts_stage_heartbeat_timestamp" in text and "1718000000" in text


def test_batch_metrics_emit_the_series_the_alerts_read():
    text = render_batch_metrics(batch_id="b1", niche="finance", videos_total=4, quarantined=1,
                                failed=0, quarantine_rate=0.25, quarantine_baseline=0.10)
    assert 'shorts_batch_videos_total{batch="b1",niche="finance"} 4' in text
    assert 'shorts_batch_failed_total{batch="b1",niche="finance"} 0' in text
    assert 'shorts_quarantine_rate{batch="b1",niche="finance"} 0.25' in text
    assert 'shorts_quarantine_baseline{batch="b1",niche="finance"} 0.1' in text


def test_write_is_atomic(tmp_path):
    out = tmp_path / "m.prom"
    write_metrics(out, "shorts_test 1\n")
    assert out.read_text() == "shorts_test 1\n" and not list(tmp_path.glob("*.tmp"))
