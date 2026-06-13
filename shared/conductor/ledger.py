import json
from pathlib import Path


def commit_ledgers(ledger_path: Path, entries: list[dict]) -> None:
    """THE single fan-in writer (ADR 0003 D6): one appender per batch, idempotent on video_id —
    a resumed batch must not double-append.

    Corrupt/unparseable lines are SKIPPED when building the existing-id set (self-healing read)
    but are NEVER removed from the file — the raw bytes are preserved for forensic inspection.
    """
    existing: set[str] = set()
    if ledger_path.exists():
        for line in ledger_path.read_text().splitlines():
            if not line:
                continue
            try:
                existing.add(json.loads(line)["video_id"])
            except (json.JSONDecodeError, KeyError):
                pass  # malformed line: skip for dedup, leave in file
    # validate BEFORE opening: an entry without video_id mid-loop would leave a PARTIAL
    # append — the worst failure for the single fan-in writer. Fail whole and loud instead.
    bad = [e for e in entries if "video_id" not in e]
    if bad:
        raise ValueError(f"ledger entries missing video_id: {bad}")
    with ledger_path.open("a") as f:
        for e in entries:
            if e["video_id"] not in existing:
                f.write(json.dumps(e) + "\n")
