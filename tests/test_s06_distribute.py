import pytest

from stages.s06_distribute.stage import HeldForReview, distribute


class _Adapter:
    def __init__(self, platform):
        self.platform = platform
        self.calls = []

    def publish(self, *, video_id, media_path, metadata, visibility, ledger_path):
        self.calls.append((video_id, visibility))
        return {"remote_id": "r", "url": "u"}


def test_posts_each_platform_when_approved(tmp_path):
    adapters = {"youtube": _Adapter("youtube"), "tiktok": _Adapter("tiktok")}
    posted = distribute(video_id="v", platforms=["youtube", "tiktok"], adapters=adapters,
                        renders={"youtube": "y.mp4", "tiktok": "t.mp4"},
                        metadata={"youtube": {"title": "t", "idempotency_key": "k1"},
                                  "tiktok": {"title": "t", "idempotency_key": "k2"}},
                        visibilities={"youtube": "public", "tiktok": "SELF_ONLY"},
                        ledger_path=tmp_path / "posts.jsonl", approved=True)
    assert adapters["youtube"].calls and adapters["tiktok"].calls
    assert set(posted) == {"youtube", "tiktok"}


def test_unapproved_video_is_held_not_failed(tmp_path):
    adapters = {"youtube": _Adapter("youtube")}
    with pytest.raises(HeldForReview):
        distribute(video_id="v", platforms=["youtube"], adapters=adapters,
                   renders={"youtube": "y.mp4"},
                   metadata={"youtube": {"title": "t", "idempotency_key": "k"}},
                   visibilities={"youtube": "public"}, ledger_path=tmp_path / "posts.jsonl",
                   approved=False)
    assert not adapters["youtube"].calls
