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
