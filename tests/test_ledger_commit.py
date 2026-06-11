import json

from shared.conductor.ledger import commit_ledgers


def test_single_fanin_appends_once_per_video(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    entries = [{"video_id": "a", "topic": "cpi"}, {"video_id": "b", "topic": "fed"}]
    commit_ledgers(ledger, entries)
    commit_ledgers(ledger, entries)               # idempotent: same entries not duplicated
    lines = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [line["video_id"] for line in lines] == ["a", "b"]


def test_corrupt_ledger_line_does_not_crash_commit(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    # Seed the ledger with one valid entry and one malformed JSON line.
    ledger.write_text('{"video_id": "a", "topic": "cpi"}\nnot-json\n')
    entries = [{"video_id": "b", "topic": "fed"}]
    commit_ledgers(ledger, entries)               # must not raise
    raw = ledger.read_text().splitlines()
    # Malformed line is preserved (forensic), new entry is appended, "a" not duplicated.
    assert "not-json" in raw
    video_ids = [json.loads(line)["video_id"] for line in raw if line != "not-json"]
    assert video_ids == ["a", "b"]
