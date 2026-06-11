import json

from shared.timing import StageTimer


def test_timer_appends_jsonl(tmp_path):
    log = tmp_path / "timing.jsonl"
    with StageTimer("00b", log):
        pass
    rec = json.loads(log.read_text().strip())
    assert rec["stage"] == "00b" and "elapsed_s" in rec and rec["elapsed_s"] >= 0


def test_timer_records_even_when_the_stage_raises(tmp_path):
    # a failing stage must still leave its timing record (the baseline includes failures)
    log = tmp_path / "timing.jsonl"
    try:
        with StageTimer("05", log):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert json.loads(log.read_text().strip())["stage"] == "05"
