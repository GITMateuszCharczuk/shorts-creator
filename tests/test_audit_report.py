"""Tests for the weekly spot-audit report (DoD clause 2).

Covers:
  - build_report core logic (plan-verbatim test)
  - missing creative_qc_overall guard (pre-M6 records skipped, not KeyError)
  - gather_posts week-window / malformed-line tolerance
  - gather_quarantines mapping from a tmp quarantine tree
  - main() smoke test: tmp data_root → audit_<date>.<niche>.json + stdout niche summary
"""
import json
from datetime import datetime, timedelta, timezone

from shared.audit.report import build_report

# ---------------------------------------------------------------------------
# Plan-verbatim test
# ---------------------------------------------------------------------------

def test_report_summarizes_posts_quarantines_and_drift_vs_LIVE_floor():
    posts = [{"video_id": "a", "platform": "youtube", "url": "u1"}]
    quarantines = [{"video_id": "c", "failed_checks": ["prohibited_claims"]},
                   {"video_id": "d", "failed_checks": ["loudness", "black_run"]}]
    feature_records = [{"video_id": "a", "creative_qc_overall": 0.82,
                        "ramp_label": {"approved": True}},
                       {"video_id": "e", "creative_qc_overall": 0.55,
                        "ramp_label": {"approved": True}}]
    r = build_report(posts=posts, quarantines=quarantines, feature_records=feature_records,
                     floor=0.70)
    assert r["posted_count"] == 1 and r["quarantined_count"] == 2
    assert (r["quarantine_reasons"]["prohibited_claims"] == 1
            and r["quarantine_reasons"]["black_run"] == 1)
    # 'e' (0.55 < 0.70) the gate would HOLD, but the human APPROVED -> drift flagged
    assert any(d["video_id"] == "e" for d in r["label_score_disagreement"])
    assert all(d["video_id"] != "a" for d in r["label_score_disagreement"])      # 'a' agrees


# ---------------------------------------------------------------------------
# Robustness: missing creative_qc_overall must be SKIPPED (not KeyError)
# ---------------------------------------------------------------------------

def test_missing_creative_qc_overall_is_skipped_not_keyerror():
    """A feature_record WITH ramp_label but MISSING creative_qc_overall (pre-M6 record) must
    be silently skipped in the disagreement scan, not raise KeyError."""
    feature_records = [
        {"video_id": "old", "ramp_label": {"approved": True}},          # no creative_qc_overall
        {"video_id": "new", "creative_qc_overall": 0.80,
         "ramp_label": {"approved": True}},
    ]
    r = build_report(posts=[], quarantines=[], feature_records=feature_records, floor=0.70)
    # 'old' must be absent (skipped), 'new' agrees (0.80 >= 0.70 and approved=True) so also absent
    assert r["label_score_disagreement"] == []


# ---------------------------------------------------------------------------
# gather_posts: week-window filter + malformed-line tolerance
# ---------------------------------------------------------------------------

def test_gather_posts_filters_to_trailing_days_window(tmp_path):
    from shorts.audit import gather_posts

    now = datetime.now(tz=timezone.utc)
    old_ts = (now - timedelta(days=10)).isoformat()
    recent_ts = (now - timedelta(days=3)).isoformat()

    posts_dir = tmp_path / "history"
    posts_dir.mkdir(parents=True)
    posts_file = posts_dir / "posts.jsonl"
    lines = [
        json.dumps({"video_id": "old", "ts": old_ts}),
        json.dumps({"video_id": "recent", "ts": recent_ts}),
        "not-valid-json",                             # malformed line — must be tolerated
        json.dumps({"video_id": "no-ts"}),            # no parseable ts — excluded from window
    ]
    posts_file.write_text("\n".join(lines) + "\n")

    result = gather_posts(tmp_path, days=7)
    ids = [p["video_id"] for p in result]
    assert "recent" in ids
    assert "old" not in ids
    assert "no-ts" not in ids       # records without parseable ts excluded from week window


def test_gather_posts_tolerates_missing_file(tmp_path):
    from shorts.audit import gather_posts

    result = gather_posts(tmp_path, days=7)
    assert result == []


# ---------------------------------------------------------------------------
# gather_quarantines: mapping from a tmp quarantine tree
# ---------------------------------------------------------------------------

def test_gather_quarantines_maps_failed_checks_from_qc_json(tmp_path):
    from shorts.audit import gather_quarantines

    # Build quarantine/<video_id>/qc.json for two videos
    for vid, fails in [("v1", ["prohibited_claims"]), ("v2", ["loudness", "black_run"])]:
        q_dir = tmp_path / "quarantine" / vid
        q_dir.mkdir(parents=True)
        checks = [{"name": f, "ok": False} for f in fails]
        checks.append({"name": "sources_cited", "ok": True})
        qc = {"schema_version": "1.0.0", "passed": False, "checks": checks}
        (q_dir / "qc.json").write_text(json.dumps(qc))

    result = gather_quarantines(tmp_path)
    by_id = {r["video_id"]: r for r in result}

    assert set(by_id["v1"]["failed_checks"]) == {"prohibited_claims"}
    assert set(by_id["v2"]["failed_checks"]) == {"loudness", "black_run"}


def test_gather_quarantines_tolerates_missing_or_malformed_qc_json(tmp_path):
    from shorts.audit import gather_quarantines

    # A quarantine dir with no qc.json at all
    no_qc = tmp_path / "quarantine" / "no-qc"
    no_qc.mkdir(parents=True)

    # A quarantine dir with malformed qc.json
    bad_qc = tmp_path / "quarantine" / "bad-qc"
    bad_qc.mkdir(parents=True)
    (bad_qc / "qc.json").write_text("NOT JSON")

    result = gather_quarantines(tmp_path)
    # Both dirs should be represented (with empty failed_checks for missing/malformed)
    # OR gracefully skipped — the key requirement is no crash
    assert isinstance(result, list)


def test_gather_quarantines_tolerates_missing_quarantine_dir(tmp_path):
    from shorts.audit import gather_quarantines

    result = gather_quarantines(tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# main() smoke test
# ---------------------------------------------------------------------------

def test_main_writes_audit_json_and_prints_niche_summary(tmp_path, capsys):
    from shorts.audit import main

    # --- posts.jsonl ---
    now = datetime.now(tz=timezone.utc)
    recent_ts = (now - timedelta(days=2)).isoformat()
    posts_dir = tmp_path / "history"
    posts_dir.mkdir(parents=True)
    (posts_dir / "posts.jsonl").write_text(
        json.dumps({"video_id": "v1", "platform": "youtube", "url": "u1", "ts": recent_ts}) + "\n"
    )

    # --- quarantine dir ---
    q_dir = tmp_path / "quarantine" / "v2"
    q_dir.mkdir(parents=True)
    qc = {"schema_version": "1.0.0", "passed": False,
          "checks": [{"name": "prohibited_claims", "ok": False}]}
    (q_dir / "qc.json").write_text(json.dumps(qc))

    # --- feature_index.jsonl (labelled records) ---
    records = [
        {"video_id": "v1", "niche": "finance", "creative_qc_overall": 0.80,
         "ramp_label": {"approved": True}},
        {"video_id": "v3", "niche": "finance", "creative_qc_overall": 0.55,
         "ramp_label": {"approved": True}},    # drift: score < floor but human approved
    ]
    (posts_dir / "feature_index.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )

    out_dir = tmp_path / ".metrics"
    rc = main(["--data-root", str(tmp_path), "--out-dir", str(out_dir),
               "--floor", "finance=0.70"])
    assert rc == 0

    # The audit file must exist
    today = datetime.now(tz=timezone.utc).date().isoformat()
    audit_file = out_dir / f"audit_{today}.finance.json"
    assert audit_file.exists(), f"Expected {audit_file} but not found in {list(out_dir.iterdir())}"

    report = json.loads(audit_file.read_text())
    assert report["posted_count"] >= 1
    assert report["quarantined_count"] >= 1

    # stdout must mention the niche
    captured = capsys.readouterr()
    assert "finance" in captured.out
