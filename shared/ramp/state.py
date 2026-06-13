import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DEFAULT = {"provisioned": False, "warming_until": None, "approved": 0, "rejected": 0,
            "first_approval_ts": None, "approved_videos": {}, "strikes": 0, "strike_log": []}


def load_state(path: Path) -> dict:
    loaded = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    s = {**_DEFAULT, **loaded}
    # _DEFAULT's mutable fields are module-shared; return FRESH copies so callers that
    # append/assign (record_strike, record_decision) never mutate the global default.
    s["approved_videos"] = dict(loaded.get("approved_videos", {}))
    s["strike_log"] = list(loaded.get("strike_log", []))
    return s


def _save(path: Path, state: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"{path}.tmp")
    tmp.write_text(json.dumps(state))
    os.replace(tmp, path)


def mark_provisioned(path: Path, *, warming_days: int) -> None:
    s = load_state(path)
    s["provisioned"] = True
    s["warming_until"] = (datetime.now(timezone.utc) + timedelta(days=warming_days)).isoformat()
    _save(path, s)


def record_decision(path: Path, *, video_id: str, approved: bool) -> None:
    s = load_state(path)
    s["approved" if approved else "rejected"] += 1
    s["approved_videos"][video_id] = approved
    if approved and s["first_approval_ts"] is None:
        s["first_approval_ts"] = datetime.now(timezone.utc).isoformat()
    _save(path, s)


def record_strike(path: Path, *, note: str = "") -> dict:
    """Operator-logged platform strike (copyright/community-guideline). Feeds the ramp gate's
    max_strikes bar (shared/ramp/policy.py): strikes > 0 keeps the human-at-publish gate ACTIVE."""
    s = load_state(path)
    s["strikes"] += 1
    s["strike_log"].append({"ts": datetime.now(timezone.utc).isoformat(), "note": note})
    _save(path, s)
    return s


def is_warmed(state: dict) -> bool:
    """Calendar predicate ONLY — independent of the approval track record (ADR 0009)."""
    wu = state.get("warming_until")
    return wu is not None and datetime.now(timezone.utc) >= datetime.fromisoformat(wu)


def approved_days(state: dict) -> int:
    ts = state.get("first_approval_ts")
    if not ts:
        return 0
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).days
