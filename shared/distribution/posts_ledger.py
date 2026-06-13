import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class LedgerCorruption(Exception):
    """A posts.jsonl line failed to parse. For an exactly-once ledger, silently skipping it could
    drop a 'confirmed' record and cause a double-post — so we fail loud (spec Ch.8)."""


def idempotency_key(video_id: str, platform: str) -> str:
    return hashlib.sha256(f"{video_id}:{platform}".encode()).hexdigest()[:16]


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise LedgerCorruption(f"{path}:{i} unparseable — {e}") from e
    return out


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now(timezone.utc).isoformat()
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")
        # Durability (H2): an exactly-once ledger must survive an OS crash. Without fsync a
        # buffered intent/publishing/confirmed record can be lost, and a retry would then
        # blind re-post. Force the bytes to disk before returning.
        f.flush()
        os.fsync(f.fileno())


def _states(path, video_id, platform) -> set[str]:
    return {r["state"] for r in read_records(path)
            if r["video_id"] == video_id and r["platform"] == platform}


def already_confirmed(path: Path, video_id: str, platform: str) -> bool:
    return "confirmed" in _states(path, video_id, platform)


def pending_post(path: Path, video_id: str, platform: str) -> bool:
    s = _states(path, video_id, platform)
    return bool(s & {"intent", "publishing"}) and "confirmed" not in s


def _rec(video_id, platform, state, **extra) -> dict:
    return {"schema_version": "1.0.0", "video_id": video_id, "platform": platform, "state": state,
            "idempotency_key": idempotency_key(video_id, platform), **extra}


def write_intent(path, *, video_id, platform): _append(path, _rec(video_id, platform, "intent"))


def write_publishing(path, *, video_id, platform, remote_id):
    _append(path, _rec(video_id, platform, "publishing", remote_id=remote_id))


def write_confirmed(path, *, video_id, platform, remote_id, url):
    _append(path, _rec(video_id, platform, "confirmed", remote_id=remote_id, url=url))
