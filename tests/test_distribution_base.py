from shared.adapters.base import DistributionAdapter
from shared.distribution.posts_ledger import already_confirmed, write_intent


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
        self.searchable[metadata["idempotency_key"]] = rid
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
    a.searchable["k"] = "rid_prior"                         # the post actually landed
    a.publish(video_id="v", media_path="m.mp4",
              metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 0                                     # found remote -> no re-post


def test_retry_when_post_did_not_land_reposts_cleanly(tmp_path):
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    write_intent(led, video_id="v", platform="youtube")     # intent only; nothing landed remotely
    a.publish(video_id="v", media_path="m.mp4",
              metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 1                                     # legitimate single re-post
