import pytest

from shared.adapters.base import DistributionAdapter, UnresolvedPendingPost
from shared.distribution.posts_ledger import (
    already_confirmed,
    idempotency_key,
    write_intent,
)


class FakeAdapter(DistributionAdapter):
    platform = "youtube"

    def __init__(self):
        self.posts = 0
        self.searchable = {}

    def allowed_visibility(self, cfg):
        return {"private", "public"}

    def _post(self, media_path, metadata, visibility):
        self.posts += 1
        rid = f"rid{self.posts}"
        # key off the INTERNALLY-derived key the base exposes (never caller metadata) — C1
        self.searchable[self._idempotency_key] = rid
        return rid, f"https://yt/{rid}"

    def _find_existing(self, idempotency_key):
        rid = self.searchable.get(idempotency_key)
        return (rid, f"https://yt/{rid}") if rid else None


def test_publish_returns_a_confirmed_record_and_writes_the_per_video_ledger(tmp_path):
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    rec = a.publish(video_id="v", media_path="m.mp4",
                    metadata={"title": "t", "idempotency_key": "k"},
                    visibility="private", ledger_path=led)
    assert a.posts == 1 and rec["remote_id"] == "rid1"
    assert already_confirmed(led, "v", "youtube")


def test_confirmed_video_is_never_reposted(tmp_path):
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    md = {"title": "t", "idempotency_key": "k"}
    a.publish(video_id="v", media_path="m.mp4", metadata=md, visibility="private", ledger_path=led)
    a.publish(video_id="v", media_path="m.mp4", metadata=md, visibility="private", ledger_path=led)
    assert a.posts == 1                                     # second call no-ops


def test_retry_after_crash_confirms_via_find_existing(tmp_path):
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    write_intent(led, video_id="v", platform="youtube")
    # the post actually landed — keyed under the INTERNALLY-derived key (C1), not caller metadata
    key = idempotency_key("v", "youtube")
    a.searchable[key] = "rid_prior"
    a.publish(video_id="v", media_path="m.mp4",
              metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 0                                     # found remote -> no re-post


def test_pending_without_findable_remote_raises_instead_of_blind_reposting(tmp_path):
    # C1: a pending intent with NO findable remote post must NOT be blind-reposted (the video may
    # already be live and only transiently unfindable). The base raises for a human/bounded retry.
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    write_intent(led, video_id="v", platform="youtube")     # intent only; nothing findable remotely
    with pytest.raises(UnresolvedPendingPost):
        a.publish(video_id="v", media_path="m.mp4",
                  metadata={"title": "t", "idempotency_key": "k"},
                  visibility="private", ledger_path=led)
    assert a.posts == 0                                     # NEVER a blind re-post


def test_wrong_metadata_key_does_not_defeat_derived_key_recovery(tmp_path):
    # C1: the recovery lookup uses the internally-derived key, so a wrong/missing caller-supplied
    # metadata["idempotency_key"] cannot silently defeat crash-recovery into a double-post.
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    write_intent(led, video_id="v", platform="youtube")
    a.searchable[idempotency_key("v", "youtube")] = "rid_prior"     # landed under the DERIVED key
    rec = a.publish(video_id="v", media_path="m.mp4",
                    metadata={"title": "t", "idempotency_key": "WRONG"},   # caller key is bogus
                    visibility="private", ledger_path=led)
    assert a.posts == 0 and rec["recovered"] is True and rec["remote_id"] == "rid_prior"
