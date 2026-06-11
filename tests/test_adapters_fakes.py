from pathlib import Path

from shared.adapters import DistributionAdapter, ModelBackend, PostMeta, Visibility
from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter


def test_fake_backend_satisfies_protocol(tmp_path):
    be = FixtureBackend(fixtures_dir=tmp_path)
    assert isinstance(be, ModelBackend)


def test_fake_distribution_satisfies_protocol():
    assert isinstance(FixtureDistributionAdapter(), DistributionAdapter)


def test_llm_replays_fixture_by_capability_and_hash(tmp_path):
    (tmp_path / "llm").mkdir()
    # fixture filename is the input_hash of the prompt payload
    from shared.hashing import input_hash, sha256_bytes
    h = input_hash(declared_input_digests={"prompt": sha256_bytes(b"hi")},
                   resolved_config={}, stage_version="fake")
    (tmp_path / "llm" / f"{h}.txt").write_text("canned response")
    be = FixtureBackend(fixtures_dir=tmp_path)
    assert be.llm("hi") == "canned response"


def test_publish_confirm_roundtrip():
    ad = FixtureDistributionAdapter()
    meta = PostMeta(title="t", description="d", hashtags=(), visibility=Visibility.PUBLIC)
    rec = ad.publish(Path("/tmp/x.mp4"), meta)
    assert ad.confirm_posted(rec.video_id, rec.platform) == rec


def test_allowed_visibility_degrades_when_unaudited():
    ad = FixtureDistributionAdapter()
    assert Visibility.PUBLIC not in ad.allowed_visibility("unaudited")
    assert Visibility.PUBLIC in ad.allowed_visibility("audited")
