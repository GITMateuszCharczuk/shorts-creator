import json

import pytest

from shared.ctx import StageContext
from stages.s06_distribute.stage import HeldForReview, distribute, run


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


# ---------------------------------------------------------------------------
# run() integration: feature_record must carry creative_qc_overall + niche
# ---------------------------------------------------------------------------

def _make_run_ctx(tmp_path):
    """Build a minimal StageContext that can drive run() in unit-test mode.

    Mirrors the seeding pattern used by the offline DAG (test_full_dag_offline.py):
    - ramp gate INACTIVE (lift bars zeroed) so distribute() succeeds without HeldForReview
    - render stub written as the platform mp4 path the stage resolves
    - script, qc, creative_qc inputs seeded as JSON files
    - job.json pre-written so set_status() can do an atomic overwrite
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # ramp state: gate inactive (no provisioning → approved=True path)
    ramp_path = tmp_path / "ramp.json"
    ramp_path.write_text(json.dumps({}))

    # Minimal script required by run() — platform_meta must include primary_keyword
    # so that build_caption() doesn't raise (it expects the field the 01-series stages write)
    script = {
        "schema_version": "1.0.0",
        "format": "ranked_list",
        "affiliate": None,
        "platform_meta": {
            "youtube": {
                "title": "Test",
                "description": "desc",
                "hashtags": [],
                "primary_keyword": "test",
            }
        },
    }
    (run_dir / "script.json").write_text(json.dumps(script))

    # qc input (not consumed by the C2 fix, but declared)
    qc = {"schema_version": "1.0.0", "passed": True, "checks": []}
    (run_dir / "qc.json").write_text(json.dumps(qc))

    # creative_qc input — this is what run() must now read
    creative_qc = {
        "schema_version": "1.0.0",
        "scores": {"hook": 0.8, "original_insight": 0.7},
        "overall": 0.76,
        "floor": 0.70,
        "pass": True,
    }
    (run_dir / "creative_qc.json").write_text(json.dumps(creative_qc))

    # stub render bytes so distribute() can reference the path (FixtureDistributionAdapter
    # doesn't actually open the file, so an empty file is sufficient)
    renders_dir = run_dir / "renders"
    renders_dir.mkdir()
    (renders_dir / "youtube.mp4").write_bytes(b"\x00fake")

    # job.json (set_status needs this)
    job = {
        "schema_version": "1.0.0",
        "batch_id": "b",
        "video_id": "fin-0001",
        "niche": "finance",
        "platform_targets": ["youtube"],
        "seed": 7,
        "stages": {},
        "paths": {},
    }
    (run_dir / "job.json").write_text(json.dumps(job))

    from shared.adapters.fakes import FixtureDistributionAdapter

    ctx = StageContext(
        stage="06",
        run_dir=run_dir,
        seed=7,
        job=job,
        config={
            "ramp_state_path": str(ramp_path),
            "ramp": {"lift": {"min_approved": 0, "min_days": 0,
                              "max_rejected": 999, "max_strikes": 999}},
            "disclosure_line": "AI-generated. Educational only.",
            "visibility": {"youtube": {"public_after_warming": True}},
        },
        input_paths={
            "render": "renders/youtube.mp4",
            "script": "script.json",
            "qc": "qc.json",
            "creative_qc": "creative_qc.json",
        },
        output_paths={
            "posts": "posts.json",
            "feature_record": "feature_record.json",
        },
        backends={
            "distribution": {"youtube": FixtureDistributionAdapter("youtube")},
        },
    )
    return ctx, run_dir, creative_qc


def test_run_writes_creative_qc_overall_into_feature_record(tmp_path):
    """C2 fix: run() must copy creative_qc.overall into feature_record.creative_qc_overall.
    Before the fix this key is absent — calibrate_records() silently skips those records
    and the M6 floor re-anchoring has no data.
    """
    ctx, run_dir, creative_qc = _make_run_ctx(tmp_path)
    run(ctx)
    fr = json.loads((run_dir / "feature_record.json").read_text())
    assert "creative_qc_overall" in fr, (
        "feature_record must contain 'creative_qc_overall' so the M6 calibration loop "
        "has data; run() currently omits it (C2 bug)"
    )
    assert fr["creative_qc_overall"] == pytest.approx(creative_qc["overall"])


def test_run_writes_niche_into_feature_record(tmp_path):
    """C2 fix: run() must include 'niche' in feature_record so calibrate_records() can
    group by niche; without it every record is silently skipped."""
    ctx, run_dir, _ = _make_run_ctx(tmp_path)
    run(ctx)
    fr = json.loads((run_dir / "feature_record.json").read_text())
    assert "niche" in fr, (
        "feature_record must contain 'niche' so calibrate_records() can group by niche; "
        "run() currently omits it (C2 bug)"
    )
    assert fr["niche"] == "finance"


def test_feature_record_validates_against_schema(tmp_path):
    """After the fix, the feature_record written by run() must pass schema validation.
    Before the schema is updated this test would FAIL because additionalProperties:false
    rejects the new creative_qc_overall / niche fields.
    """
    from shared.schema import SchemaRegistry

    ctx, run_dir, _ = _make_run_ctx(tmp_path)
    run(ctx)
    fr = json.loads((run_dir / "feature_record.json").read_text())
    reg = SchemaRegistry()
    # validate() raises jsonschema.ValidationError on failure
    reg.validate("feature_record", fr)


def test_truthy_non_bool_approval_does_not_bypass_hold(tmp_path):
    """approved_videos value must be exactly True (is True), not merely truthy.

    A corrupt state entry like "yes" or 1 must NOT grant approval — only an explicit
    True written by the review CLI counts (fixes the truthy-vs-is-True guard).
    """
    ramp_path = tmp_path / "ramp.json"
    # Gate active (min_approved=1 not met), but approved_videos has a truthy non-bool value.
    ramp_path.write_text(json.dumps({
        "provisioned": True,
        "warming_until": "2099-01-01T00:00:00+00:00",
        "approved_videos": {"fin-0001": "yes"},   # truthy string, NOT bool True
        "rejected_videos": {},
        "strikes": 0,
    }))

    from shared.ramp.policy import gate_active
    from shared.ramp.state import load_state

    state = load_state(str(ramp_path))
    ramp_cfg = {"lift": {"min_approved": 1, "min_days": 0, "max_rejected": 999,
                         "max_strikes": 999}}
    active = gate_active(state, ramp_cfg)
    approved = (not active) or (state.get("approved_videos", {}).get("fin-0001") is True)
    assert active, "gate should be active with provisioned=True and not enough approvals"
    assert not approved, (
        "a truthy non-bool value in approved_videos must NOT grant approval — "
        "only explicit True counts (is-True guard)"
    )
