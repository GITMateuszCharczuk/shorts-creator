import pytest

from shared.adapters.base import DistributionAdapter
from shared.adapters.youtube import YouTubeAdapter


def test_protocol_and_NO_invented_synthetic_field():
    a = YouTubeAdapter(creds=None)
    assert isinstance(a, DistributionAdapter) and a.platform == "youtube"
    assert a.allowed_visibility({}) == {"private", "unlisted", "public"}
    body = a._insert_body({"title": "t", "description": "d\nAI-generated."}, visibility="private")
    assert body["status"]["privacyStatus"] == "private"
    # the altered-content flag has NO Data API field — disclosure rides in the description
    assert "containsSyntheticMedia" not in body["status"]
    assert "AI-generated" in body["snippet"]["description"]


@pytest.mark.integration
def test_youtube_retry_uses_uploads_playlist_not_search(tmp_path):
    # Crash-recovery must resolve the prior upload via the uploads playlist (near-real-time),
    # NEVER search.list (lagging index → blind double-post). We inject both API surfaces and
    # assert _find_existing hit the playlist and the publish recovered without a re-insert.
    calls = {"list_uploads": 0, "search": 0, "insert": 0}

    def search_list(_key):           # the WRONG surface — must never be touched
        calls["search"] += 1
        return None

    def list_uploads(key):           # playlistItems.list on the uploads playlist
        calls["list_uploads"] += 1
        return {"id": "vid_prior"} if key == "k" else None

    def insert(_body, _media):
        calls["insert"] += 1
        return {"id": "vid_new"}

    a = YouTubeAdapter(creds=None, insert=insert, list_uploads=list_uploads)
    a._search_list = search_list     # present but must stay unused
    led = tmp_path / "v" / "posts.jsonl"
    from shared.distribution.posts_ledger import write_intent
    write_intent(led, video_id="v", platform="youtube")   # prior intent; the post actually landed
    rec = a.publish(video_id="v", media_path="m.mp4",
                    metadata={"title": "t", "description": "d", "idempotency_key": "k"},
                    visibility="private", ledger_path=led)
    assert rec["recovered"] is True and rec["remote_id"] == "vid_prior"
    assert calls["list_uploads"] == 1 and calls["search"] == 0 and calls["insert"] == 0
