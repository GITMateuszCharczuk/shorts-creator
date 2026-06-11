import json
from datetime import datetime, timezone
from pathlib import Path


def record_label(feature_record_path: Path, *, approved: bool, reason: str = "") -> None:
    """Capture the operator verdict into feature_record as the 05c calibration label
    (ADR 0016 D2)."""
    rec = json.loads(Path(feature_record_path).read_text())
    rec["ramp_label"] = {"approved": approved, "reason": reason,
                         "ts": datetime.now(timezone.utc).isoformat()}
    Path(feature_record_path).write_text(json.dumps(rec))
