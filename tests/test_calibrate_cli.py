"""Tests for shorts.calibrate — per-niche 05c floor re-anchoring CLI (ADR 0016 D2)."""
import json

from shorts.calibrate import (
    append_to_index,
    calibrate_records,
    main,
    scan_records,
)

# ---------------------------------------------------------------------------
# calibrate_records
# ---------------------------------------------------------------------------

def _make_record(video_id, niche, overall, approved):
    """Helper: a minimal feature_record with ramp_label."""
    return {
        "video_id": video_id,
        "niche": niche,
        "creative_qc_overall": overall,
        "ramp_label": {"approved": approved, "reason": ""},
    }


def test_calibrate_groups_by_niche_and_returns_recommendations():
    records = (
        [_make_record(f"finance-{i}", "finance", 0.80, True) for i in range(20)]
        + [_make_record(f"finance-r{i}", "finance", 0.55, False) for i in range(15)]
        + [_make_record(f"travel-{i}", "travel", 0.75, True) for i in range(20)]
        + [_make_record(f"travel-r{i}", "travel", 0.50, False) for i in range(15)]
    )
    recs, n_skipped = calibrate_records(records)
    assert n_skipped == 0
    assert "finance" in recs
    assert "travel" in recs
    # Both niches have 35 labels → data_anchored (≥ min_labels=30 default)
    assert recs["finance"]["reason"] == "data_anchored"
    assert recs["travel"]["reason"] == "data_anchored"


def test_calibrate_skips_unlabelled_records():
    unlabelled = {"video_id": "u1", "niche": "finance", "creative_qc_overall": 0.8}
    labelled = _make_record("f1", "finance", 0.8, True)
    recs, n_skipped = calibrate_records([unlabelled, labelled])
    assert n_skipped == 1


def test_calibrate_skips_records_missing_niche():
    no_niche = {"video_id": "x", "creative_qc_overall": 0.8,
                "ramp_label": {"approved": True, "reason": ""}}
    recs, n_skipped = calibrate_records([no_niche])
    assert n_skipped == 1
    assert recs == {}


def test_calibrate_skips_records_missing_creative_qc_overall():
    no_score = {"video_id": "x", "niche": "travel",
                "ramp_label": {"approved": True, "reason": ""}}
    recs, n_skipped = calibrate_records([no_score])
    assert n_skipped == 1
    assert recs == {}


def test_calibrate_mixed_two_niches_one_unlabelled_one_missing_fields():
    records = (
        # finance: 35 labelled records
        [_make_record(f"finance-{i}", "finance", 0.80, True) for i in range(20)]
        + [_make_record(f"finance-r{i}", "finance", 0.55, False) for i in range(15)]
        # travel: 35 labelled records
        + [_make_record(f"travel-{i}", "travel", 0.75, True) for i in range(20)]
        + [_make_record(f"travel-r{i}", "travel", 0.50, False) for i in range(15)]
        # unlabelled → skipped
        + [{"video_id": "u1", "niche": "finance", "creative_qc_overall": 0.9}]
        # missing niche → skipped
        + [{"video_id": "m1", "creative_qc_overall": 0.9,
            "ramp_label": {"approved": True, "reason": ""}}]
    )
    recs, n_skipped = calibrate_records(records)
    assert n_skipped == 2
    assert set(recs.keys()) == {"finance", "travel"}


# ---------------------------------------------------------------------------
# scan_records
# ---------------------------------------------------------------------------

def test_scan_records_reads_runs_glob(tmp_path):
    # Build runs/batch1/video1/feature_record.json
    fr_path = tmp_path / "runs" / "batch1" / "video1" / "feature_record.json"
    fr_path.parent.mkdir(parents=True)
    fr_path.write_text(json.dumps({"video_id": "v1", "niche": "finance"}))

    records = scan_records(tmp_path)
    assert len(records) == 1
    assert records[0]["video_id"] == "v1"


def test_scan_records_tolerates_malformed_json(tmp_path):
    fr_path = tmp_path / "runs" / "b1" / "v1" / "feature_record.json"
    fr_path.parent.mkdir(parents=True)
    fr_path.write_text("{bad json")

    records = scan_records(tmp_path)
    assert records == []


def test_scan_records_tolerates_missing_index(tmp_path):
    # No runs/ or history/ — should return empty list without error
    records = scan_records(tmp_path)
    assert records == []


def test_scan_records_index_wins_over_runs(tmp_path):
    """INDEX copy is authoritative: same video_id in both → index value kept."""
    vid = "v1"

    # runs/ copy: no ramp_label
    fr_path = tmp_path / "runs" / "b1" / vid / "feature_record.json"
    fr_path.parent.mkdir(parents=True)
    fr_path.write_text(json.dumps({"video_id": vid, "niche": "finance"}))

    # index copy: has ramp_label (the durable, authoritative version)
    index_path = tmp_path / "history" / "feature_index.jsonl"
    index_path.parent.mkdir(parents=True)
    index_path.write_text(
        json.dumps({"video_id": vid, "niche": "finance",
                    "ramp_label": {"approved": True, "reason": ""}}) + "\n"
    )

    records = scan_records(tmp_path)
    assert len(records) == 1
    assert "ramp_label" in records[0], "INDEX copy (with ramp_label) should win"


def test_scan_records_tolerates_malformed_index_line(tmp_path):
    index_path = tmp_path / "history" / "feature_index.jsonl"
    index_path.parent.mkdir(parents=True)
    good = {"video_id": "v1", "niche": "finance"}
    index_path.write_text("{bad line}\n" + json.dumps(good) + "\n")

    records = scan_records(tmp_path)
    assert len(records) == 1
    assert records[0]["video_id"] == "v1"


# ---------------------------------------------------------------------------
# append_to_index
# ---------------------------------------------------------------------------

def test_append_to_index_adds_labelled_records(tmp_path):
    records = [
        {**_make_record("v1", "finance", 0.8, True)},
        {**_make_record("v2", "finance", 0.9, True)},
    ]
    n = append_to_index(tmp_path, records)
    assert n == 2

    index_path = tmp_path / "history" / "feature_index.jsonl"
    lines = [json.loads(ln) for ln in index_path.read_text().splitlines() if ln.strip()]
    assert {r["video_id"] for r in lines} == {"v1", "v2"}


def test_append_to_index_no_duplicates(tmp_path):
    rec = _make_record("v1", "finance", 0.8, True)

    # First append
    append_to_index(tmp_path, [rec])
    # Second append of the same record
    n = append_to_index(tmp_path, [rec])
    assert n == 0

    index_path = tmp_path / "history" / "feature_index.jsonl"
    lines = [ln for ln in index_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1


def test_append_to_index_skips_unlabelled(tmp_path):
    unlabelled = {"video_id": "u1", "niche": "finance", "creative_qc_overall": 0.8}
    n = append_to_index(tmp_path, [unlabelled])
    assert n == 0

    # The file may or may not be created (implementation detail), but it must be empty of records.
    index_path = tmp_path / "history" / "feature_index.jsonl"
    if index_path.exists():
        lines = [ln for ln in index_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 0


def test_append_to_index_creates_parent_dirs(tmp_path):
    rec = _make_record("v1", "finance", 0.8, True)
    n = append_to_index(tmp_path / "deep" / "nested", [rec])
    assert n == 1


# ---------------------------------------------------------------------------
# main() smoke test
# ---------------------------------------------------------------------------

def test_main_writes_recommendation_files(tmp_path):
    """End-to-end: build enough labelled records so calibrate writes output files."""
    # finance niche: 35 records — enough for data_anchored
    records = (
        [_make_record(f"finance-{i}", "finance", 0.80, True) for i in range(20)]
        + [_make_record(f"finance-r{i}", "finance", 0.55, False) for i in range(15)]
    )

    # Write them as runs/ artifacts
    for r in records:
        vid = r["video_id"]
        p = tmp_path / "runs" / "b1" / vid / "feature_record.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r))

    out_dir = tmp_path / "out"
    rc = main(["--data-root", str(tmp_path), "--out-dir", str(out_dir)])
    assert rc == 0

    rec_file = out_dir / "floor_recommendation.finance.json"
    assert rec_file.exists()
    rec = json.loads(rec_file.read_text())
    assert rec["reason"] == "data_anchored"
    assert "floor" in rec


def test_main_no_labelled_records_returns_0(tmp_path):
    rc = main(["--data-root", str(tmp_path)])
    assert rc == 0


def test_main_live_floor_diff_display(tmp_path, capsys):
    """--live-floor affects the printed diff line."""
    records = (
        [_make_record(f"finance-{i}", "finance", 0.80, True) for i in range(20)]
        + [_make_record(f"finance-r{i}", "finance", 0.55, False) for i in range(15)]
    )
    for r in records:
        vid = r["video_id"]
        p = tmp_path / "runs" / "b1" / vid / "feature_record.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r))

    out_dir = tmp_path / "out"
    main(["--data-root", str(tmp_path), "--out-dir", str(out_dir), "--live-floor", "0.65"])
    captured = capsys.readouterr()
    assert "niche=finance" in captured.out
    assert "live=0.650" in captured.out
