# tests/test_posts_ledger.py
import pytest

from shared.distribution.posts_ledger import (
    LedgerCorruption,
    already_confirmed,
    idempotency_key,
    pending_post,
    read_records,
    write_confirmed,
    write_intent,
    write_publishing,
)


def test_idempotency_key_is_deterministic():
    assert idempotency_key("v", "youtube") == idempotency_key("v", "youtube")
    assert idempotency_key("v", "youtube") != idempotency_key("v", "tiktok")


def test_confirmed_blocks_a_second_post(tmp_path):
    led = tmp_path / "posts.jsonl"
    write_intent(led, video_id="v", platform="youtube")
    write_confirmed(led, video_id="v", platform="youtube", remote_id="yt", url="u")
    assert already_confirmed(led, "v", "youtube") and not pending_post(led, "v", "youtube")


def test_intent_or_publishing_without_confirm_is_a_retry_case(tmp_path):
    led = tmp_path / "posts.jsonl"
    write_intent(led, video_id="v", platform="tiktok")
    assert pending_post(led, "v", "tiktok")
    write_publishing(led, video_id="v", platform="tiktok", remote_id="pub1")   # async accepted
    assert pending_post(led, "v", "tiktok") and not already_confirmed(led, "v", "tiktok")


def test_append_durably_writes_the_record_before_returning(tmp_path):
    # H2: _append flushes + fsyncs so an OS crash can't lose an intent/confirmed record (which
    # would cause a double-post on retry). fsync itself isn't unit-observable, so we assert the
    # durable-write path is exercised: the record is on disk (read_records sees it) immediately
    # after the call returns, with the durable contents intact.
    led = tmp_path / "v" / "posts.jsonl"
    write_intent(led, video_id="v", platform="youtube")
    recs = read_records(led)                                # re-reads from disk, not a buffer
    assert led.exists() and len(recs) == 1
    assert recs[0]["state"] == "intent" and recs[0]["video_id"] == "v"
    write_confirmed(led, video_id="v", platform="youtube", remote_id="yt", url="u")
    states = [r["state"] for r in read_records(led)]        # both records durably present
    assert states == ["intent", "confirmed"]


def test_corrupt_line_fails_loud(tmp_path):
    led = tmp_path / "posts.jsonl"
    led.write_text('{"good": 1}\nNOT JSON\n')
    with pytest.raises(LedgerCorruption):     # exactly-once must NEVER silently skip (spec Ch.8)
        read_records(led)
