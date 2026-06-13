"""Offline soak harness over the REAL batch_flow (M6 Task 12, ADR 0003).

Drives shorts.run_batch.batch_flow N times with injected collaborators and a FakeClock,
injecting faults (kill-mid-batch, stale lock, disk-low) and asserting the stability
mechanics: zero wedges/silent failures, reconcile-after-kill (real resume_plan),
stale-lock takeover (real acquire_lock semantics), systemic-halt-not-quarantine (real
PreflightFailure via the real free_space_gate), ledger monotonicity (real commit_ledgers),
and GC within retention bounds (real runs_to_delete + _rmtree_guarded). This is NOT a
re-implementation: batch_flow, build_preflight, run_preflight, execute_batch, resume_plan,
commit_ledgers and runs_to_delete are the real production functions; only the per-stage
work (run_stage) and the wall clock are fakes.
"""
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path

from shared.conductor.executor import default_stage_order, execute_batch
from shared.conductor.ledger import commit_ledgers
from shared.conductor.preflight import PreflightFailure, free_space_gate, run_preflight
from shared.conductor.reconcile import resume_plan
from shared.conductor.subproc import StageOutcome
from shared.ops.gc import runs_to_delete
from shorts.run_batch import _rmtree_guarded, batch_flow, build_preflight

TERMINAL = {"done", "failed", "quarantined", "held"}
KEEP_DAYS, KEEP_COUNT = 7, 14          # the production retention knobs (ADR 0003 D8)
DAY_S = 86400.0


class KilledMidBatch(Exception):
    """Sentinel: the conductor process died mid-execute (the SIGKILL/reboot model)."""


@dataclass
class FakeClock:
    """Offline wall clock — run-dir ages come from here, never from mtime."""
    now: float = 1_700_000_000.0

    def advance(self, days: float) -> None:
        self.now += days * DAY_S


def _dead_pid() -> int:
    """A pid that is provably not alive, so a lock written with it is STALE by the real
    acquire_lock's own test (_pid_alive)."""
    pid = 4_000_000                     # just under the Linux default pid_max (4194304)
    while pid > 1:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass                        # alive but not ours — keep looking
        pid -= 1
    raise RuntimeError("could not find a dead pid")


def _persist_to(run_dir: Path):
    """batch.json write-through, temp+rename — the shape the boot reconciler reads."""
    def persist(batch: dict) -> None:
        tmp = run_dir / "batch.json.tmp"
        tmp.write_text(json.dumps(batch))
        tmp.rename(run_dir / "batch.json")
    return persist


def _ledger_lines(ledger: Path) -> int:
    return len(ledger.read_text().splitlines()) if ledger.exists() else 0


def run_offline_soak(*, data_root: Path, batches: int, seed: int, inject: dict) -> dict:
    """Run `batches` consecutive nightly batches through the REAL batch_flow, injecting the
    faults named in `inject` ({"kill_mid_batch_on": n, "stale_lock_on": n, "disk_low_on": n})
    and checking the stability invariants after every iteration. Returns the result dict the
    soak test asserts on."""
    data_root = Path(data_root)
    runs_root = data_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    (data_root / "history").mkdir(parents=True, exist_ok=True)
    ledger = data_root / "history" / "batches.jsonl"
    lock_path = data_root / ".batch.lock"
    rng = random.Random(seed)
    clock = FakeClock()

    kill_on = inject.get("kill_mid_batch_on")
    stale_on = inject.get("stale_lock_on")
    disk_low_on = inject.get("disk_low_on")

    # FakeClock ages, not mtime: run id -> clock.now at creation. Seed three ancient runs so
    # runs_to_delete has genuine out-of-bounds candidates to reclaim during the soak.
    created_at: dict[str, float] = {}
    for age in (40, 30, 20):
        rid = f"seed-{age:02d}d"
        (runs_root / rid).mkdir()
        created_at[rid] = clock.now - age * DAY_S

    result: dict = {"wedges": 0, "silent_failures": 0,
                    "ledger_monotonic": True, "runs_within_retention": True}
    for key, n in (("batch_{}_resumed", kill_on),
                   ("batch_{}_took_over_stale_lock", stale_on),
                   ("batch_{}_halted_with_alert", disk_low_on)):
        if n is not None:
            result[key.format(n)] = False

    planned: set[str] = set()           # every video id any plan() ever emitted
    tally: dict[str, str] = {}          # video id -> last observed status
    resumed_ids: set[str] = set()       # reconciler-resumed batch ids (GC-protected)
    last_ledger = _ledger_lines(ledger)

    def run_stage(video_id: str, stage_id: str) -> StageOutcome:
        # The only fake worker: everything succeeds, except an occasional 05b safety
        # quarantine (seeded rng) so the quarantine path is a first-class terminal status.
        if stage_id == "05b" and rng.random() < 0.10:
            return StageOutcome(status="quarantined", exit_code=3, elapsed_s=0.01)
        return StageOutcome(status="done", exit_code=0, elapsed_s=0.01)

    def commit(batch: dict) -> None:    # the REAL single fan-in writer
        commit_ledgers(ledger, [
            {"video_id": v["video_id"], "niche": v["niche"], "batch_id": batch["batch_id"],
             "status": v["status"]} for v in batch["videos"]])

    normal_preflight = lambda: run_preflight(build_preflight({}))            # noqa: E731
    disk_low_preflight = lambda: run_preflight(build_preflight(             # noqa: E731
        {"free_space": lambda: free_space_gate(data_root, min_free_gb=10**9)}))

    for n in range(1, batches + 1):
        batch_id = f"b{n:02d}"
        run_dir = runs_root / batch_id
        persist = _persist_to(run_dir)

        def plan(batch_id=batch_id, run_dir=run_dir, persist=persist) -> dict:
            run_dir.mkdir()
            created_at[batch_id] = clock.now
            batch = {"batch_id": batch_id, "videos": [
                {"video_id": f"{batch_id}-v1", "niche": "finance", "status": "pending"},
                {"video_id": f"{batch_id}-v2", "niche": "business", "status": "pending"}]}
            planned.update(v["video_id"] for v in batch["videos"])
            persist(batch)
            return batch

        def execute(batch: dict, persist=persist) -> None:
            tally.update(execute_batch(batch, stage_order=default_stage_order(),
                                       run_stage=run_stage, persist=persist))

        def killing_execute(batch: dict, persist=persist) -> None:
            # Partial state exactly as the write-through executor leaves it on a kill:
            # one video already done, one still running, batch.json persisted, then death.
            batch["videos"][0]["status"] = "done"
            batch["videos"][1]["status"] = "running"
            persist(batch)
            raise KilledMidBatch(batch["batch_id"])

        preflight = disk_low_preflight if n == disk_low_on else normal_preflight
        this_execute = killing_execute if n == kill_on else execute

        stale_pid = None
        if n == stale_on:
            stale_pid = _dead_pid()
            lock_path.write_text(str(stale_pid))   # a dead holder = stale by the real lock
            observed = {}

            def this_execute(batch: dict, execute=execute, observed=observed) -> None:
                observed["lock"] = lock_path.read_text()   # who holds the lock mid-batch?
                execute(batch)

        halted = killed = completed = False
        alert = ""
        try:
            batch_flow(lock_path=lock_path, data_root=data_root, preflight=preflight,
                       plan=plan, execute=this_execute, commit=commit, backup=lambda: None)
            completed = True
        except PreflightFailure as e:   # systemic halt — recognized, NOT a wedge
            halted, alert = True, str(e)
        except KilledMidBatch:          # injected death — recognized; reconcile below
            killed = True
        except Exception:               # anything else is a wedge
            result["wedges"] += 1

        if killed:
            # Boot-time reconciliation over the persisted batch.json — the REAL resume_plan
            # decides what re-runs; the REAL executor then skips the closed (done) domain.
            persisted = json.loads((run_dir / "batch.json").read_text())
            resume_ids = resume_plan(persisted)
            batch_flow(lock_path=lock_path, data_root=data_root, preflight=normal_preflight,
                       plan=lambda p=persisted: p, execute=execute, commit=commit,
                       backup=lambda: None)
            resumed_ids.add(batch_id)
            completed = True
            result[f"batch_{n}_resumed"] = (
                resume_ids == [f"{batch_id}-v2"]            # only the unfinished video
                and all(v["status"] in TERMINAL for v in persisted["videos"]))

        if n == stale_on and completed:
            # Takeover proof: the flow ran (no LockHeld) and the lock was OURS mid-batch.
            result[f"batch_{n}_took_over_stale_lock"] = (
                observed.get("lock") == str(os.getpid()) != str(stale_pid))

        if n == disk_low_on:
            # Halt, not quarantine: alert raised, plan never ran (no run dir, no videos).
            result[f"batch_{n}_halted_with_alert"] = (
                halted and bool(alert) and not run_dir.exists()
                and not any(vid.startswith(batch_id) for vid in tally))

        if not (completed or halted):
            result["wedges"] += 1       # neither finished nor a recognized halt/resume
        if lock_path.exists():
            result["wedges"] += 1       # a leftover lock wedges every future batch

        cur_ledger = _ledger_lines(ledger)
        if cur_ledger < last_ledger:
            result["ledger_monotonic"] = False
        last_ledger = cur_ledger

        # GC invariant: the REAL runs_to_delete over the accumulated run dirs must return
        # exactly the runs outside BOTH bounds (age > keep_days AND beyond keep_count) and
        # never a protected one — then actually reclaim them via the REAL guarded rmtree.
        runs = [{"id": rid, "age_days": (clock.now - t0) / DAY_S, "path": runs_root / rid}
                for rid, t0 in sorted(created_at.items()) if (runs_root / rid).is_dir()]
        protected = {batch_id} | resumed_ids
        doomed = runs_to_delete(runs, keep_days=KEEP_DAYS, keep_count=KEEP_COUNT,
                                protected_ids=protected)
        newest = {r["id"] for r in sorted(runs, key=lambda r: r["age_days"])[:KEEP_COUNT]}
        expected = {r["id"] for r in runs if r["age_days"] > KEEP_DAYS
                    and r["id"] not in newest and r["id"] not in protected}
        if {r["id"] for r in doomed} != expected:
            result["runs_within_retention"] = False
        for r in doomed:
            _rmtree_guarded(data_root, r["path"])
            del created_at[r["id"]]

        clock.advance(1)                # one nightly batch per day

    # Silent failures: every planned video must end in a KNOWN terminal status. Videos of
    # the halted batch were never planned (preflight fires before plan), so none are owed.
    for vid in sorted(planned):
        if tally.get(vid) not in TERMINAL:
            result["silent_failures"] += 1
    return result
