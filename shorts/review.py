"""python -m shorts.review — the temporary human-at-publish ramp CLI (ADR 0014 D2).
list pending -> play the YouTube cut -> approve/reject; each decision is a 05c calibration label
(ADR 0016 D2) and releases/holds the video for 06. Read-only on renders; append-only on labels."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from shared.ramp.labels import record_label
from shared.ramp.queue import pending_review
from shared.ramp.state import load_state, record_decision, record_strike


def review_one(*, video_id, render, feature_record: Path, state_path: Path, play, prompt) -> bool:
    play(render)
    action, reason = prompt()
    approved = action == "approve"
    record_label(feature_record, approved=approved, reason=reason)
    record_decision(state_path, video_id=video_id, approved=approved)
    return approved


def _discover(data_root: Path, batch_filter: str | None) -> list[dict]:
    """Scan runs/<batch>/<video> for the render + QC verdicts. Deterministic order (batch, vid)."""
    videos: list[dict] = []
    runs = data_root / "runs"
    if not runs.exists():
        return videos
    for batch_dir in sorted(p for p in runs.iterdir() if p.is_dir()):
        if batch_filter is not None and batch_dir.name != batch_filter:
            continue
        for vdir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
            render = vdir / "renders" / "youtube.mp4"
            qc = vdir / "qc.json"
            creative = vdir / "creative_qc.json"
            if not (render.exists() and qc.exists() and creative.exists()):
                continue
            cq = json.loads(creative.read_text())
            videos.append({
                "batch": batch_dir.name,
                "video_id": vdir.name,
                "render": render,
                "feature_record": vdir / "feature_record.json",
                "qc_pass": bool(json.loads(qc.read_text()).get("passed")),
                "creative_pass": bool(cq.get("pass")),
                "overall": cq.get("overall"),
            })
    return videos


def main(argv: list[str], *, input_fn=input, open_fn=None) -> int:
    ap = argparse.ArgumentParser(prog="shorts.review")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--batch")
    ap.add_argument("--open-cmd")
    ap.add_argument("--record-strike")
    args = ap.parse_args(argv)

    data_root = Path(args.data_root)
    state_path = data_root / "ramp.json"

    if args.record_strike is not None:
        record_strike(state_path, note=args.record_strike)
        print(f"strike recorded: {args.record_strike}")
        return 0

    # open: --open-cmd wins (subprocess), else the injected open_fn, else a no-op.
    if args.open_cmd:
        def opener(render: Path) -> None:
            subprocess.run([args.open_cmd, str(render)])
    elif open_fn is not None:
        opener = open_fn
    else:
        def opener(render: Path) -> None:
            return None

    videos = _discover(data_root, args.batch)
    by_id = {v["video_id"]: v for v in videos}
    decided = load_state(state_path)["approved_videos"]
    queue = pending_review(videos, decided)

    approved = rejected = skipped = 0
    for vid in queue:
        v = by_id[vid]
        opener(v["render"])
        overall = "" if v["overall"] is None else f"  creative={v['overall']:.2f}"
        print(f"{v['video_id']}  {v['render']}{overall}")
        action = input_fn(f"[{v['video_id']}] approve/reject/skip/quit (a/r/s/q)? ").strip()
        if action == "a":
            record_label(v["feature_record"], approved=True, reason="")
            record_decision(state_path, video_id=vid, approved=True)
            approved += 1
        elif action == "r":
            reason = input_fn("reason? ")
            record_label(v["feature_record"], approved=False, reason=reason)
            record_decision(state_path, video_id=vid, approved=False)
            rejected += 1
        elif action == "s":
            skipped += 1
        elif action == "q":
            break
        else:
            print("unknown key — use a/r/s/q; skipping.")
            skipped += 1

    print(f"{approved} approved, {rejected} rejected, {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
