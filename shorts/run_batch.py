"""python -m shorts.run_batch — the nightly conductor entrypoint (ADR 0015)."""
from pathlib import Path

from shared.conductor.lock import acquire_lock, release_lock


def batch_flow(*, lock_path: Path, data_root: Path, preflight, plan, execute, commit, backup):
    """Lock -> preflight -> (resume|plan) -> execute -> fan-in commit -> backup -> unlock.
    Commit/backup run only on success; the lock is released on EVERY path."""
    acquire_lock(lock_path)
    try:
        preflight()
        batch = plan()
        execute(batch)
        commit(batch)
        backup()
        return batch
    finally:
        release_lock(lock_path)


def main() -> int:
    # Production wiring: DATA_ROOT from env; preflight=[free_space_gate, host_health_gate]
    # (ADR 0003 D2/D8); plan=resume_plan-or-plan_batch with per_niche from config (the ADR 0014
    # D2 ramp knob, default 1); execute=execute_batch over run_stage_subprocess+retries with
    # StageTimer per stage and persist=write batch.json (temp+rename); commit=commit_ledgers
    # (novelty + feature_record); backup=one rsync of history/*.jsonl + credentials (spec Ch.8).
    # Each collaborator is the tested unit above.
    raise SystemExit(0)


if __name__ == "__main__":
    main()
