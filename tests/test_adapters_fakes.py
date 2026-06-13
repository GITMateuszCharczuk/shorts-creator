from shared.adapters import ModelBackend
from shared.adapters.base import DistributionAdapter
from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter
from shared.distribution.posts_ledger import idempotency_key, write_intent


def test_fake_backend_satisfies_protocol(tmp_path):
    be = FixtureBackend(fixtures_dir=tmp_path)
    assert isinstance(be, ModelBackend)


def test_fake_distribution_is_a_distribution_adapter():
    ad = FixtureDistributionAdapter("tiktok")
    assert isinstance(ad, DistributionAdapter) and ad.platform == "tiktok"
    assert FixtureDistributionAdapter().platform == "youtube"
    assert ad.allowed_visibility({}) == {"private", "public"}
    assert ad.public_label() == "public" and ad.private_label() == "private"


def test_llm_replays_fixture_by_capability_and_hash(tmp_path):
    (tmp_path / "llm").mkdir()
    # fixture filename is the input_hash of the prompt payload
    from shared.hashing import input_hash, sha256_bytes
    h = input_hash(declared_input_digests={"prompt": sha256_bytes(b"hi")},
                   resolved_config={}, stage_version="fake")
    (tmp_path / "llm" / f"{h}.txt").write_text("canned response")
    be = FixtureBackend(fixtures_dir=tmp_path)
    assert be.llm("hi") == "canned response"


def test_publish_is_exactly_once_via_the_ledger(tmp_path):
    led = tmp_path / "posts.jsonl"
    ad = FixtureDistributionAdapter()
    md = {"title": "t", "idempotency_key": "k"}
    rec = ad.publish(video_id="v", media_path="m.mp4", metadata=md,
                     visibility="private", ledger_path=led)
    assert rec == {"remote_id": "fake_1", "url": "https://fake/1", "recovered": False}
    again = ad.publish(video_id="v", media_path="m.mp4", metadata=md,
                       visibility="private", ledger_path=led)
    assert again is None                                    # confirmed -> never re-posted


def test_retry_after_crash_recovers_via_the_searchable_store(tmp_path):
    led = tmp_path / "posts.jsonl"
    ad = FixtureDistributionAdapter()
    write_intent(led, video_id="v", platform="youtube")     # pending from a crashed attempt
    # ...but the post actually landed — keyed under the INTERNALLY-derived key (C1), not metadata
    ad.searchable[idempotency_key("v", "youtube")] = ("fake_9", "https://fake/9")
    rec = ad.publish(video_id="v", media_path="m.mp4",
                     metadata={"title": "t", "idempotency_key": "k"},
                     visibility="private", ledger_path=led)
    assert rec == {"remote_id": "fake_9", "url": "https://fake/9", "recovered": True}
