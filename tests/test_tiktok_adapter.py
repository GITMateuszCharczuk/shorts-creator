import pytest

from shared.adapters.base import DistributionAdapter
from shared.adapters.tiktok import TikTokAdapter


def test_protocol_and_aigc_flag_in_post_info():
    a = TikTokAdapter(token=None)
    assert isinstance(a, DistributionAdapter) and a.platform == "tiktok"
    assert a.allowed_visibility({}) == {"SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS",
                                        "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"}
    body = a._init_body({"title": "t"}, visibility="SELF_ONLY")
    assert body["post_info"]["privacy_level"] == "SELF_ONLY"
    assert body["post_info"]["brand_content_toggle"] is False
    assert body["post_info"]["aigc_content"] is True       # AIGC flag in post_info, not source_info
    assert "is_ai_generated" not in body.get("source_info", {})


@pytest.mark.integration
def test_tiktok_confirms_only_after_publish_complete(tmp_path):
    # _post must block on /publish/status/fetch/ until PUBLISH_COMPLETE before returning, so a
    # 'confirmed' ledger record can never mean a still-processing video. We poll through the
    # intermediate states and assert the confirm lands only at the terminal one.
    seen = []

    def init(_body, _media):
        return "pub_1"

    def upload(_pid, _media):
        return None

    def poll(pid):
        # the real poller blocks, looping /publish/status/fetch/ until a terminal status;
        # this fake walks the intermediate states and returns only the terminal one.
        for s in ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "PUBLISH_COMPLETE"):
            seen.append((pid, s))
        return seen[-1][1]

    a = TikTokAdapter(token=None, init=init, upload=upload, poll=poll)
    led = tmp_path / "v" / "posts.jsonl"
    rec = a.publish(video_id="v", media_path="m.mp4",
                    metadata={"title": "t", "idempotency_key": "k"},
                    visibility="SELF_ONLY", ledger_path=led)
    from shared.distribution.posts_ledger import already_confirmed
    assert seen[-1] == ("pub_1", "PUBLISH_COMPLETE")
    assert rec["remote_id"] == "pub_1" and already_confirmed(led, "v", "tiktok")


@pytest.mark.integration
def test_tiktok_raises_and_does_not_confirm_on_failed_publish(tmp_path):
    # A FAILED terminal status must raise (no 'confirmed' written) — a failed publish is never
    # silently treated as posted (spec Ch.8 no silent failures, ADR 0003 D1).
    def poll(_pid):
        return "FAILED"

    a = TikTokAdapter(token=None, init=lambda b, m: "pub_2",
                      upload=lambda p, m: None, poll=poll)
    led = tmp_path / "v" / "posts.jsonl"
    with pytest.raises(RuntimeError):
        a.publish(video_id="v", media_path="m.mp4",
                  metadata={"title": "t", "idempotency_key": "k"},
                  visibility="SELF_ONLY", ledger_path=led)
    from shared.distribution.posts_ledger import already_confirmed
    assert not already_confirmed(led, "v", "tiktok")
