"""python -m shorts.review — the temporary human-at-publish ramp CLI (ADR 0014 D2).
list pending -> play the YouTube cut -> approve/reject; each decision is a 05c calibration label
(ADR 0016 D2) and releases/holds the video for 06. Read-only on renders; append-only on labels."""
from pathlib import Path

from shared.ramp.labels import record_label
from shared.ramp.state import record_decision


def review_one(*, video_id, render, feature_record: Path, state_path: Path, play, prompt) -> bool:
    play(render)
    action, reason = prompt()
    approved = action == "approve"
    record_label(feature_record, approved=approved, reason=reason)
    record_decision(state_path, video_id=video_id, approved=approved)
    return approved


def main() -> int:
    # Production wiring: scan runs/<batch>/<video> for qc.json.passed && creative_qc.json.pass,
    # filter via shared.ramp.queue.pending_review against the ramp state, then review_one each with
    # play=_open_player (xdg-open/ffplay) and prompt=_tty_prompt. Held videos re-run 06 next batch.
    raise SystemExit(0)


if __name__ == "__main__":
    main()
