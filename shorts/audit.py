"""python -m shorts.audit — weekly spot-audit report vs the live floor (DoD clause 2).

Reads posts from history/posts.jsonl (trailing N days), quarantine dirs, and feature records
(via shared.calibrate.scan_records), then builds a per-niche report and writes it to
<out-dir>/audit_<date>.<niche>.json.

The live floor is INJECTED via --floor niche=value pairs — never hardcoded — so a promoted
floor is audited against the current value, not a stale default.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared.audit.report import build_report
from shorts.calibrate import scan_records

# ---------------------------------------------------------------------------
# Gather helpers (read-only)
# ---------------------------------------------------------------------------

_DEFAULT_FLOOR = 0.70


def gather_posts(data_root: Path, *, days: int = 7) -> list[dict]:
    """Load posts from history/posts.jsonl, keeping only those within the trailing `days` window.

    - Malformed JSON lines are silently skipped.
    - Records without a parseable 'ts' field are EXCLUDED from the window (not counted as recent).
    """
    posts_file = data_root / "history" / "posts.jsonl"
    if not posts_file.exists():
        return []

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    results: list[dict] = []
    skipped = 0

    for line in posts_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue

        ts_raw = record.get("ts")
        if not ts_raw:
            # No timestamp — excluded from the week window
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
            # Ensure tz-aware for comparison
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            # Unparseable timestamp — excluded from the week window
            continue

        if ts >= cutoff:
            results.append(record)

    if skipped:
        print(f"audit: skipped {skipped} malformed line(s) in {posts_file}")

    return results


def gather_quarantines(data_root: Path) -> list[dict]:
    """Scan quarantine/<video_id>/qc.json files; map to {video_id, failed_checks}.

    Schema: {"schema_version": ..., "passed": bool, "checks": [{"name": str, "ok": bool, ...}]}

    Tolerates:
    - Missing quarantine directory (returns [])
    - Missing qc.json within a subdir (subdir is skipped)
    - Malformed qc.json (subdir is skipped)
    """
    q_root = data_root / "quarantine"
    if not q_root.exists():
        return []

    results: list[dict] = []
    for subdir in sorted(q_root.iterdir()):
        if not subdir.is_dir():
            continue
        video_id = subdir.name
        qc_path = subdir / "qc.json"
        if not qc_path.exists():
            continue
        try:
            qc = json.loads(qc_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        checks = qc.get("checks", [])
        failed = [c["name"] for c in checks if isinstance(c, dict) and not c.get("ok", True)
                  and "name" in c]
        results.append({"video_id": video_id, "failed_checks": failed})

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Weekly spot-audit report vs the live floor (DoD clause 2).",
    )
    parser.add_argument("--data-root", required=True, type=Path, metavar="DIR",
                        help="Root of the data directory (contains history/ and quarantine/).")
    parser.add_argument("--out-dir", type=Path, default=None, metavar="DIR",
                        help="Output directory for audit JSON files "
                             "(default: <data-root>/.metrics).")
    parser.add_argument("--days", type=int, default=7, metavar="N",
                        help="Trailing day window for posts (default: 7).")
    parser.add_argument("--floor", action="append", default=[], metavar="NICHE=VALUE",
                        help="Per-niche live floor, e.g. --floor finance=0.70 "
                             "--floor business=0.72. Can be repeated.")
    args = parser.parse_args(argv)

    data_root: Path = args.data_root
    out_dir: Path = args.out_dir if args.out_dir is not None else data_root / ".metrics"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Parse --floor niche=value pairs
    floors: dict[str, float] = {}
    for pair in args.floor:
        try:
            niche, val = pair.split("=", 1)
            floors[niche.strip()] = float(val.strip())
        except (ValueError, TypeError):
            print(f"audit: WARNING — ignoring malformed --floor argument: {pair!r}")

    if not floors:
        print(
            f"audit: WARNING — no --floor arguments supplied; "
            f"using default {_DEFAULT_FLOOR} for all niches. "
            "Pass --floor niche=value from live config to avoid auditing stale."
        )

    # Gather data
    posts = gather_posts(data_root, days=args.days)
    quarantines = gather_quarantines(data_root)
    feature_records = scan_records(data_root)

    # Group feature records by niche
    by_niche: dict[str, list[dict]] = {}
    for rec in feature_records:
        niche = rec.get("niche") or "unknown"
        by_niche.setdefault(niche, []).append(rec)

    if not by_niche:
        print("audit: no feature records found — nothing to report")
        return 0

    today = datetime.now(tz=timezone.utc).date().isoformat()

    for niche, records in sorted(by_niche.items()):
        floor = floors.get(niche, _DEFAULT_FLOOR)
        if niche not in floors:
            print(
                f"audit: WARNING — no floor configured for niche={niche!r}; "
                f"using default {_DEFAULT_FLOOR}"
            )
        report = build_report(
            posts=posts,
            quarantines=quarantines,
            feature_records=records,
            floor=floor,
        )
        report["niche"] = niche
        report["floor_used"] = floor
        report["days_window"] = args.days
        report["generated_at"] = datetime.now(tz=timezone.utc).isoformat()

        out_path = out_dir / f"audit_{today}.{niche}.json"
        out_path.write_text(json.dumps(report, indent=2))

        n_disagree = len(report["label_score_disagreement"])
        reasons_str = ", ".join(
            f"{k}:{v}" for k, v in sorted(report["quarantine_reasons"].items())
        ) or "(none)"
        print(
            f"audit: niche={niche}  posted={report['posted_count']}  "
            f"quarantined={report['quarantined_count']}  "
            f"disagreements={n_disagree}  "
            f"floor={floor}  "
            f"quarantine_reasons=[{reasons_str}]  "
            f"→ {out_path}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
