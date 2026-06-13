import json
import os
from datetime import datetime, timezone
from pathlib import Path


def record_label(feature_record_path: Path, *, approved: bool, reason: str = "") -> None:
    """Capture the operator verdict into feature_record as the 05c calibration label
    (ADR 0016 D2)."""
    rec = json.loads(Path(feature_record_path).read_text())
    rec["ramp_label"] = {"approved": approved, "reason": reason,
                         "ts": datetime.now(timezone.utc).isoformat()}
    # Atomic write: a crash mid-write must not corrupt feature_record (same pattern as state._save).
    tmp = Path(f"{feature_record_path}.tmp")
    tmp.write_text(json.dumps(rec))
    os.replace(tmp, feature_record_path)
