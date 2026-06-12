"""python -m shorts.calibrate — per-niche 05c floor re-anchoring (ADR 0016 D2).

Reads feature_record artifacts that have a ramp_label, groups by niche, and calls
recommend_floor per niche.  Results are written to <out-dir>/floor_recommendation.<niche>.json.

Field contract (pinned by M6 plan):
  feature_record.creative_qc_overall  — scalar copied from creative_qc.overall at fan-in
  feature_record.niche                — niche string (e.g. "finance")
  feature_record.ramp_label.approved  — bool set by shared.ramp.labels.record_label

Pre-M6 records that lack creative_qc_overall or niche are SKIPPED (counted, never crash).

scan_records deduplication: INDEX wins over runs/ — history/feature_index.jsonl is the durable
labelled copy; per-run copies may be overwritten or partially written, so the index is
authoritative.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.calibration.anchor import PROVISIONAL, recommend_floor

# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------

def calibrate_records(records: list[dict]) -> tuple[dict[str, dict], int]:
    """Group labelled records by niche, call recommend_floor per niche.

    Returns (recommendations, n_skipped).

    Skipped = record has no ramp_label, no niche, or no creative_qc_overall.
    The '_skipped' count is also embedded in the returned dict under the key '_skipped'
    for convenience when serialising, but the caller receives it as a second return value too.
    """
    by_niche: dict[str, list[dict]] = {}
    n_skipped = 0
    for r in records:
        if "ramp_label" not in r:
            n_skipped += 1
            continue
        niche = r.get("niche")
        overall = r.get("creative_qc_overall")
        if niche is None or overall is None:
            n_skipped += 1
            continue
        label = {"overall": float(overall), "approved": bool(r["ramp_label"]["approved"])}
        by_niche.setdefault(niche, []).append(label)

    recommendations: dict[str, dict] = {}
    for niche, labels in by_niche.items():
        recommendations[niche] = recommend_floor(labels)

    return recommendations, n_skipped


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def scan_records(data_root: Path) -> list[dict]:
    """Load feature_records from two locations; deduplicate by video_id (INDEX wins).

    Sources (in priority order, lowest first — later wins in the dict):
      1. runs/*/*/feature_record.json  — per-run copies (may be incomplete / pre-label)
      2. history/feature_index.jsonl   — durable labelled index (authoritative)

    Malformed JSON files/lines are silently skipped (never crash).
    """
    by_id: dict[str, dict] = {}

    # 1. Per-run copies (lower priority)
    for path in sorted((data_root / "runs").glob("*/*/feature_record.json")):
        try:
            rec = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        vid = rec.get("video_id")
        if vid:
            by_id[vid] = rec

    # 2. Durable index (higher priority — overwrites runs/ copy for the same video_id)
    index_path = data_root / "history" / "feature_index.jsonl"
    if index_path.exists():
        for line in index_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = rec.get("video_id")
            if vid:
                by_id[vid] = rec

    return list(by_id.values())


def append_to_index(data_root: Path, records: list[dict]) -> int:
    """Append labelled records (those WITH ramp_label) to history/feature_index.jsonl,
    skipping any video_id already present.  Returns the count of newly appended records."""
    index_path = data_root / "history" / "feature_index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect existing video_ids from the index
    existing: set[str] = set()
    if index_path.exists():
        for line in index_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = rec.get("video_id")
            if vid:
                existing.add(vid)

    appended = 0
    with index_path.open("a") as fh:
        for r in records:
            if "ramp_label" not in r:
                continue
            vid = r.get("video_id")
            if not vid or vid in existing:
                continue
            fh.write(json.dumps(r) + "\n")
            existing.add(vid)
            appended += 1

    return appended


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-niche 05c floor re-anchoring from ramp labels (ADR 0016 D2).",
    )
    parser.add_argument("--data-root", required=True, type=Path, metavar="DIR",
                        help="Root of the data directory (contains runs/ and history/).")
    parser.add_argument("--out-dir", type=Path, default=None, metavar="DIR",
                        help="Output directory for recommendation JSON files "
                             "(default: <data-root>/.metrics).")
    parser.add_argument("--live-floor", type=float, default=PROVISIONAL, metavar="FLOAT",
                        help=f"Current live floor for diff display (default: {PROVISIONAL}).")
    args = parser.parse_args(argv)

    data_root: Path = args.data_root
    out_dir: Path = args.out_dir if args.out_dir is not None else data_root / ".metrics"
    out_dir.mkdir(parents=True, exist_ok=True)

    records = scan_records(data_root)
    recommendations, n_skipped = calibrate_records(records)

    if n_skipped:
        print(f"calibrate: skipped {n_skipped} record(s) "
              "missing niche/creative_qc_overall/ramp_label")

    if not recommendations:
        print("calibrate: no labelled records found — nothing to recommend")
        return 0

    for niche, rec in recommendations.items():
        out_path = out_dir / f"floor_recommendation.{niche}.json"
        out_path.write_text(json.dumps(rec, indent=2))

        recommended = rec["floor"]
        live = args.live_floor
        delta = recommended - live
        diff_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
        print(
            f"calibrate: niche={niche}  recommended={recommended:.3f}  live={live:.3f}  "
            f"diff={diff_str}  reason={rec['reason']}"
            + (f"  [promote by setting config quality.floor.{niche}={recommended:.3f}]"
               if recommended != live else "")
        )

    appended = append_to_index(data_root, records)
    if appended:
        print(f"calibrate: appended {appended} labelled record(s) to history/feature_index.jsonl")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
