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


def test_pending_post_recovers_via_injected_find_without_reposting(tmp_path):
    # crash recovery: an intent record is pending and the post actually landed remotely. The
    # injected `find` (host wiring re-polls the publish_id stored in the ledger's publishing
    # record) returns it, so the base confirms WITHOUT calling init/upload (zero re-posts).
    calls = {"init": 0, "upload": 0}

    def init(_body, _media):
        calls["init"] += 1
        return "pub_never"

    def upload(_pid, _media):
        calls["upload"] += 1

    a = TikTokAdapter(token=None, init=init, upload=upload, poll=None,
                      find=lambda k: ("pub9", "https://tiktok.com/@me/video/pub9"))
    led = tmp_path / "v" / "posts.jsonl"
    from shared.distribution.posts_ledger import write_intent
    write_intent(led, video_id="v", platform="tiktok")
    rec = a.publish(video_id="v", media_path="m.mp4",
                    metadata={"title": "t", "idempotency_key": "k"},
                    visibility="SELF_ONLY", ledger_path=led)
    assert rec == {"remote_id": "pub9", "url": "https://tiktok.com/@me/video/pub9",
                   "recovered": True}
    assert calls == {"init": 0, "upload": 0}               # posts == 0: recovery is a no-op post


def test_publishing_record_with_publish_id_persists_across_post_init_crash(tmp_path):
    # H3: a crash AFTER init returns the publish_id but BEFORE confirm must leave a 'publishing'
    # ledger record carrying that publish_id, so recovery has a re-pollable id (TikTok has no
    # search-by-marker; the publish_id IS the marker). We simulate the crash by having upload raise
    # after init/_record_publishing has run, then assert the publish_id is durably on the ledger.
    from shared.distribution.posts_ledger import read_records

    def init(_body, _media):
        return "pub_init_42"

    def boom_upload(_pid, _media):
        raise RuntimeError("network died after init, before confirm")

    a = TikTokAdapter(token=None, init=init, upload=boom_upload, poll=lambda p: "PUBLISH_COMPLETE")
    led = tmp_path / "v" / "posts.jsonl"
    with pytest.raises(RuntimeError):
        a.publish(video_id="v", media_path="m.mp4",
                  metadata={"title": "t", "idempotency_key": "k"},
                  visibility="SELF_ONLY", ledger_path=led)
    recs = read_records(led)
    pubs = [r for r in recs if r["state"] == "publishing"]
    assert len(pubs) == 1 and pubs[0]["remote_id"] == "pub_init_42"   # in-flight id persisted
    assert not any(r["state"] == "confirmed" for r in recs)           # never confirmed

    # recovery: a fresh attempt finds the in-flight publish_id via the injected re-poll hook (host
    # wiring reads the publishing record's publish_id) and confirms WITHOUT re-init/re-upload.
    calls = {"init": 0, "upload": 0}
    b = TikTokAdapter(
        token=None,
        init=lambda _b, _m: calls.__setitem__("init", calls["init"] + 1) or "pub_NEW",
        upload=lambda _p, _m: calls.__setitem__("upload", calls["upload"] + 1),
        poll=lambda p: "PUBLISH_COMPLETE",
        find=lambda k: ("pub_init_42", "https://tiktok.com/@me/video/pub_init_42"),
    )
    rec = b.publish(video_id="v", media_path="m.mp4",
                    metadata={"title": "t", "idempotency_key": "k"},
                    visibility="SELF_ONLY", ledger_path=led)
    assert rec == {"remote_id": "pub_init_42",
                   "url": "https://tiktok.com/@me/video/pub_init_42", "recovered": True}
    assert calls == {"init": 0, "upload": 0}                          # zero re-posts


def test_find_existing_defaults_to_none_without_injection():
    assert TikTokAdapter(token=None)._find_existing("k") is None


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
