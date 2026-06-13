import time

from shorts.stage import Heartbeat


def test_heartbeat_file_advances_while_running(tmp_path):
    hb = Heartbeat(tmp_path / ".heartbeat" / "05.json", interval_s=0.05)
    hb.start()
    time.sleep(0.16)
    first = hb.read_ts()
    time.sleep(0.16)
    assert hb.read_ts() > first        # advancing while the stage runs
    hb.stop()
    stopped = hb.read_ts()
    time.sleep(0.16)
    assert hb.read_ts() == stopped     # frozen after stop (conductor sees age grow -> stuck)
    assert not list(tmp_path.glob("*.prom"))  # no prom side effects when prom_path is None


def test_heartbeat_emits_running_1_prom_while_alive(tmp_path):
    prom = tmp_path / "v1-05.prom"
    hb = Heartbeat(tmp_path / ".heartbeat" / "05.json", interval_s=0.05,
                   prom_path=prom, batch_id="b1", stage="05", video_id="v1")
    hb.start()
    try:
        time.sleep(0.16)
        first = prom.read_text()
        assert 'shorts_stage_running{batch="b1",stage="05",video="v1"} 1' in first
        ts1 = float(first.split("shorts_stage_heartbeat_timestamp")[1].split()[1])
        time.sleep(0.16)
        second = prom.read_text()
        assert 'shorts_stage_running{batch="b1",stage="05",video="v1"} 1' in second
        ts2 = float(second.split("shorts_stage_heartbeat_timestamp")[1].split()[1])
        assert ts2 > ts1               # heartbeat_timestamp advances while alive
    finally:
        hb.stop()


def test_heartbeat_prom_shows_running_0_after_stop(tmp_path):
    prom = tmp_path / "v1-05.prom"
    hb = Heartbeat(tmp_path / ".heartbeat" / "05.json", interval_s=0.05,
                   prom_path=prom, batch_id="b1", stage="05", video_id="v1")
    hb.start()
    time.sleep(0.16)
    hb.stop()
    text = prom.read_text()
    assert 'shorts_stage_running{batch="b1",stage="05",video="v1"} 0' in text
    assert "shorts_stage_heartbeat_timestamp" in text  # final ts preserved
