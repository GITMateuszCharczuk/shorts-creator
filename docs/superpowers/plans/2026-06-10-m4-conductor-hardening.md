# M4 — Conductor Hardening + Ops (batch planner, subprocess execution, scheduling, image, throughput gate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the M0 conductor into the production orchestrator (ADR 0015 D6): the **batch planner** (`batch.json`, lane mix, format rotation, topic reservation), **subprocess-per-stage execution** with real timeouts/retries/per-video failure domains, the **lockfile + systemd-timer scheduling** with boot-time reconciliation, **`up.sh`/`down.sh`** against host services only, the **CI-built shared image**, and the **M4 gate** — the end-to-end overnight throughput reconciliation (open #9).

**Architecture:** Everything extends the M0 runner; nothing is re-expressed elsewhere (manifests stay the single orchestration truth). Stages execute as **subprocesses** (`python -m shorts.stage <id>`) — real per-stage timeouts, GIL-free fan-out, crash + untrusted-media isolation, and exact parity with the 0015a per-stage entrypoint — with an **exit-code protocol** mapping the SDK's quarantine/degrade signals. Never-co-resident is enforced by the conductor's stage ordering plus a **VRAM-free check** against the host before diffusion stages. Pure logic (lane mix, rotation, reservation, lock, retry/backoff, reconcile, throughput math) is CI-tested; systemd/Docker/host calls are `@pytest.mark.integration`.

**Tech Stack:** Python 3.12 + the M0–M3 toolchain (no new deps; `shutil.disk_usage` for free-space, `os.open(O_CREAT|O_EXCL)` for the lock); systemd unit/timer files (data); one `Dockerfile`; GitHub Actions for the image build.

**Decisions made here (spec/ADRs left open; pinned for M4):**
- **Exit-code protocol** (`shared/exitcodes.py`): `0` done · `75` degraded (EX_TEMPFAIL) · `77` quarantined (EX_NOPERM) · anything else failed. The stage CLI maps `Degraded`/`Quarantined` to these; the conductor maps them back to `job.json` statuses.
- **Concurrency primitive** (resolves the ADR 0015 open item): a **`ThreadPoolExecutor` managing stage *subprocesses*** — threads only wait on processes, so the GIL is irrelevant; no asyncio. Lane-fork = two pool lanes (visual/audio) gated by a **GPU lock** (only the visual lane's GPU stages take it — never-co-resident stays structural).
- **`batch.schema.json` is authored here** (the spec's `batch.json` never had a schema; every boundary artifact is validated — ADR 0010 D1).
- **Lane-mix rolling window = last 20 posted videos** (from the ledger), PoC default **80/20 reach/monetization** (ADR 0006 D2 as amended); both are config.
- **Lockfile** at `DATA_ROOT/.run/batch.lock` containing the holder pid; a lock whose pid is dead is **stale and taken over** (a crash must not wedge tomorrow's batch).
- **Overnight window default = 8h** (config `batch.window_hours`); the throughput gate projects against it.
- **Image base**: `python:3.12-slim` + `ffmpeg`. The Remotion/Node layer is a **separate build stage** excluded from the CI gate (the offline DAG runs with fakes; the render path is integration) — noted honestly, not hidden.
- **Batch size is the cadence-ramp knob**: config `batch.per_niche`, **default 1** (the ADR 0014 D2 low-start posture — "the phased daily batch"); raising it toward 2 is the ramp, gated on the original-insight track record.
- **Systemic-vs-per-video failure classification (ADR 0003 D4)**: ≥3 *consecutive* `failed` outcomes across videos within one stage = a host-down pattern → the batch **halts** (`SystemicFailure`) instead of quarantining N videos.

---

## File Structure

```
schemas/batch.schema.json              # NEW: batch_id, lane mix used, videos[] {video_id,niche,format,lane,topic,seed,status}
shorts/                                # NEW package: the CLIs (ADR 0015 / 0015a entrypoints)
  __init__.py
  stage.py                             # python -m shorts.stage <id> --run-dir … (per-stage subprocess entrypoint)
  run_batch.py                         # python -m shorts.run_batch (the conductor CLI: plan -> execute -> commit)
shared/exitcodes.py                    # NEW: the exit-code protocol (0/75/77)
shared/planner/
  __init__.py
  lanes.py                             # rolling-window lane-mix selection (ADR 0006 D2 amended)
  rotation.py                          # format rotation/anti-repeat + lane_support gate (uses M3 FormatRegistry)
  topics.py                            # topic reservation vs the novelty ledger (intra-batch claim, ADR 0003 D5)
  batch.py                             # plan_batch() -> validated batch.json
shared/conductor/
  __init__.py
  lock.py                              # run lockfile (atomic create, stale-pid takeover)
  subproc.py                           # run_stage_subprocess(): timeout, exit-code mapping -> StageOutcome
  retry.py                             # per-stage retry/backoff policy (pure)
  gpu.py                               # vram_free() parse of ComfyUI /system_stats + the GPU lock
  executor.py                          # the batch executor: per-video domains, lane pools, status writes
  reconcile.py                         # boot-time reconciler: resume an interrupted batch (ADR 0003 D9)
  preflight.py                         # pluggable pre-flight gates: free-space now; OAuth token-age slots in at M5
  ledger.py                            # the single fan-in ledger commit (novelty + feature_record append)
  throughput.py                        # batch projection vs the overnight window (the M4 gate math)
deploy/host/
  shorts-batch.service  shorts-batch.timer    # WSL2 systemd units (data)
  power-policy.md                      # the ADR 0015 D3 host power checklist (ops doc)
Dockerfile                             # the shared image (entrypoint selects stage/runner)
.github/workflows/image.yml            # build the image + run the offline DAG INSIDE it (ADR 0015 D2)
scripts/up.sh  scripts/down.sh         # REWRITE: host services only, health-gated, idempotent (no cluster)
Makefile                               # wire build/test/host targets; drop cluster stubs from the PoC path
tests/
  test_exitcodes.py  test_lanes.py  test_rotation.py  test_topics.py  test_batch_plan.py
  test_lock.py  test_subproc.py  test_retry.py  test_gpu.py
  test_executor.py  test_reconcile.py  test_preflight.py  test_ledger_commit.py
  test_throughput_gate.py
```

**Responsibility split:** `shared/planner/` decides *what* tonight's batch is; `shared/conductor/` decides *how* it executes; `shorts/` is the thin CLI skin over both (and the exact entrypoint 0015a's k8s profile wraps). Nothing in `stages/` changes.

---

# Part A — The batch planner (previously unowned)

### Task 1: Exit-code protocol

**Files:** Create `shared/exitcodes.py`; Test `tests/test_exitcodes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exitcodes.py
from shared.exitcodes import EXIT_OK, EXIT_DEGRADED, EXIT_QUARANTINED, status_for_exit


def test_protocol_values_are_stable():
    assert (EXIT_OK, EXIT_DEGRADED, EXIT_QUARANTINED) == (0, 75, 77)


def test_status_mapping():
    assert status_for_exit(0) == "done"
    assert status_for_exit(75) == "done"          # degraded still completes (WARN, ADR 0009 #8)
    assert status_for_exit(77) == "quarantined"
    assert status_for_exit(1) == "failed"
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implement `shared/exitcodes.py`**

```python
EXIT_OK = 0
EXIT_DEGRADED = 75      # EX_TEMPFAIL: completed with a degrade (budget trip etc.) — WARN, not fail
EXIT_QUARANTINED = 77   # EX_NOPERM: a gate parked this video


def status_for_exit(code: int) -> str:
    if code in (EXIT_OK, EXIT_DEGRADED):
        return "done"
    if code == EXIT_QUARANTINED:
        return "quarantined"
    return "failed"
```

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/exitcodes.py tests/test_exitcodes.py
git commit -m "feat(m4): stage exit-code protocol (0/75/77, ADR 0015 D6)"
```

### Task 2: Lane-mix selection (rolling window, phase default 80/20)

ADR 0006 D2 (amended): PoC default reach-heavy; the knob is config; the window is the trailing N posted videos.

**Files:** Create `shared/planner/__init__.py` (empty), `shared/planner/lanes.py`; Test `tests/test_lanes.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lanes.py
from shared.planner.lanes import next_lane


def test_under_target_monetization_share_picks_monetization():
    history = ["reach"] * 19 + ["monetization"]          # 5% < the 20% target
    assert next_lane(history, monetization_share=0.20) == "monetization"


def test_at_or_over_target_picks_reach():
    history = ["reach"] * 16 + ["monetization"] * 4      # exactly 20%
    assert next_lane(history, monetization_share=0.20) == "reach"


def test_empty_history_starts_with_reach():
    assert next_lane([], monetization_share=0.20) == "reach"   # PoC posture: reach-first
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/planner/lanes.py`**

```python
def next_lane(history: list[str], *, monetization_share: float, window: int = 20) -> str:
    """Rolling-window lane choice (ADR 0006 D2 as amended): pick `monetization` only while the
    trailing window is UNDER the configured share; default posture is reach-first."""
    recent = history[-window:]
    if not recent:
        return "reach"
    actual = sum(1 for l in recent if l == "monetization") / len(recent)
    return "monetization" if actual < monetization_share else "reach"
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/planner/ tests/test_lanes.py
git commit -m "feat(m4): rolling-window lane-mix selection, PoC default reach-heavy (ADR 0006 D2)"
```

### Task 3: Format rotation + lane gate; topic reservation

**Files:** Create `shared/planner/rotation.py`, `shared/planner/topics.py`; Test `tests/test_rotation.py`, `tests/test_topics.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rotation.py
import pytest
from shared.planner.rotation import pick_format, NoFormatError

FMTS = [{"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}},
        {"id": "ranked_list", "lane_support": {"reach": True, "monetization": True}},
        {"id": "explainer", "lane_support": {"reach": False, "monetization": True}}]


def test_picks_lane_compatible_and_seed_deterministic():
    a = pick_format(FMTS, lane="reach", recent=[], seed=7)
    assert a["lane_support"]["reach"] and a == pick_format(FMTS, lane="reach", recent=[], seed=7)


def test_anti_repeat_excludes_recent_formats():
    got = pick_format(FMTS, lane="reach", recent=["ranked_list"], seed=7)
    assert got["id"] == "surprising_stat"


def test_no_compatible_format_raises():
    with pytest.raises(NoFormatError):
        pick_format(FMTS, lane="monetization", recent=["ranked_list", "explainer"], seed=7)
```

```python
# tests/test_topics.py
import pytest
from shared.planner.topics import claim_topics, TopicStarvation


def test_claims_skip_ledger_and_intra_batch_duplicates():
    claimed = claim_topics(["cpi", "fed", "cpi", "gold"], ledger_topics={"fed"}, n=2)
    assert claimed == ["cpi", "gold"]            # ledger dedup + intra-batch dedup (ADR 0003 D5)


def test_starvation_raises_when_not_enough_topics():
    with pytest.raises(TopicStarvation):
        claim_topics(["cpi"], ledger_topics={"cpi"}, n=1)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement both**

```python
# shared/planner/rotation.py
import random


class NoFormatError(Exception):
    """No format is lane-compatible after anti-repeat exclusion (relax `recent` upstream)."""


def pick_format(formats: list[dict], *, lane: str, recent: list[str], seed: int) -> dict:
    pool = [f for f in formats
            if f["lane_support"].get(lane, False) and f["id"] not in recent]
    if not pool:
        raise NoFormatError(f"no format for lane={lane} outside recent={recent}")
    pool.sort(key=lambda f: f["id"])                  # stable order before the seeded pick
    return random.Random(seed).choice(pool)
```

```python
# shared/planner/topics.py
class TopicStarvation(Exception):
    """Fewer fresh topics than videos — the ADR 0002 starvation ladder triggers upstream."""


def claim_topics(candidates: list[str], *, ledger_topics: set[str], n: int) -> list[str]:
    """Reserve n topics: skip anything in the cross-run ledger AND anything already claimed in
    this batch (the intra-batch claim, ADR 0003 D5)."""
    claimed: list[str] = []
    for t in candidates:
        if t in ledger_topics or t in claimed:
            continue
        claimed.append(t)
        if len(claimed) == n:
            return claimed
    raise TopicStarvation(f"needed {n} fresh topics, found {len(claimed)}")
```

- [ ] **Step 4: Run** → PASS (5). **Commit.**

```bash
git add shared/planner/rotation.py shared/planner/topics.py tests/test_rotation.py tests/test_topics.py
git commit -m "feat(m4): format rotation + lane gate + topic reservation (ADR 0002/0003 D5/0008 D2)"
```

### Task 4: `batch.schema.json` + `plan_batch()`

**Files:** Create `schemas/batch.schema.json`, `shared/planner/batch.py`; Test `tests/test_batch_plan.py`

- [ ] **Step 1: Write `schemas/batch.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "batch.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "batch_id", "monetization_share", "videos"],
  "properties": {
    "schema_version": {"type": "string"},
    "batch_id": {"type": "string"},
    "monetization_share": {"type": "number"},
    "videos": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["video_id", "niche", "format", "lane", "topic", "seed", "status"],
        "properties": {
          "video_id": {"type": "string"}, "niche": {"type": "string"},
          "format": {"type": "string"}, "lane": {"enum": ["reach", "monetization"]},
          "topic": {"type": "string"}, "seed": {"type": "integer"},
          "status": {"enum": ["pending", "running", "done", "quarantined", "failed"]}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_batch_plan.py
from shared.planner.batch import plan_batch
from shared.schema import SchemaRegistry


def test_plan_batch_is_valid_seeded_and_lane_mixed():
    fmts = [{"id": "surprising_stat", "lane_support": {"reach": True, "monetization": False}},
            {"id": "explainer", "lane_support": {"reach": False, "monetization": True}}]
    b = plan_batch(batch_id="2026-06-11", niches=["finance", "business"], per_niche=1,
                   formats=fmts, lane_history=[], topic_candidates=["cpi", "fed", "gold", "oil"],
                   ledger_topics=set(), monetization_share=0.20, master_seed=42)
    SchemaRegistry().validate("batch", b)
    assert len(b["videos"]) == 2
    assert {v["niche"] for v in b["videos"]} == {"finance", "business"}
    assert all(v["status"] == "pending" and isinstance(v["seed"], int) for v in b["videos"])
    # deterministic re-plan (same master seed -> same batch)
    assert b == plan_batch(batch_id="2026-06-11", niches=["finance", "business"], per_niche=1,
                           formats=fmts, lane_history=[], topic_candidates=["cpi", "fed", "gold", "oil"],
                           ledger_topics=set(), monetization_share=0.20, master_seed=42)
```

- [ ] **Step 3: Implement `shared/planner/batch.py`**

```python
import random

from shared.planner.lanes import next_lane
from shared.planner.rotation import pick_format
from shared.planner.topics import claim_topics


def plan_batch(*, batch_id: str, niches: list[str], per_niche: int, formats: list[dict],
               lane_history: list[str], topic_candidates: list[str], ledger_topics: set[str],
               monetization_share: float, master_seed: int) -> dict:
    """The conductor's pre-fan-out brain (ADR 0015 D6): lane mix -> format rotation -> topic
    reservation -> per-video seeds. Pure + deterministic given its inputs."""
    rng = random.Random(master_seed)
    n_total = len(niches) * per_niche
    topics = claim_topics(topic_candidates, ledger_topics=ledger_topics, n=n_total)
    videos, history, recent_formats = [], list(lane_history), []
    for niche in niches:
        for k in range(per_niche):
            lane = next_lane(history, monetization_share=monetization_share)
            fmt = pick_format(formats, lane=lane, recent=recent_formats[-3:], seed=rng.randint(0, 2**31))
            videos.append({"video_id": f"{niche}-{batch_id}-{k}", "niche": niche,
                           "format": fmt["id"], "lane": lane, "topic": topics[len(videos)],
                           "seed": rng.randint(0, 2**31), "status": "pending"})
            history.append(lane)
            recent_formats.append(fmt["id"])
    return {"schema_version": "1.0.0", "batch_id": batch_id,
            "monetization_share": monetization_share, "videos": videos}
```

- [ ] **Step 4: Run** → PASS. **Commit.**

```bash
git add schemas/batch.schema.json shared/planner/batch.py tests/test_batch_plan.py
git commit -m "feat(m4): batch planner + batch.schema (lane mix, rotation, reservation, seeds)"
```

---

# Part B — Subprocess execution, retries, failure domains

### Task 5: The per-stage CLI + `run_stage_subprocess`

**Files:** Create `shorts/__init__.py` (empty), `shorts/stage.py`, `shared/conductor/__init__.py` (empty), `shared/conductor/subproc.py`; Test `tests/test_subproc.py`

- [ ] **Step 1: Write `shorts/stage.py`** (the entrypoint 0015a's k8s profile wraps verbatim)

```python
"""python -m shorts.stage <id> --run-dir <dir> --seed <n> [--config <json>]"""
import argparse
import json
import sys
from pathlib import Path

from shared.ctx import Degraded, Quarantined, StageContext
from shared.exitcodes import EXIT_DEGRADED, EXIT_OK, EXIT_QUARANTINED
from shared.stage import REGISTRY
from stages.registry import load_all


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage_id")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--config", default="{}")
    a = p.parse_args()
    load_all()
    reg = REGISTRY[a.stage_id]
    run_dir = Path(a.run_dir)
    job = json.loads((run_dir / "job.json").read_text())
    cfg = json.loads(a.config)
    for key in ("input_paths", "output_paths"):
        if key not in cfg:                       # fail loud, not KeyError-deep (the stage_cmd contract)
            p.error(f"--config JSON must contain {key!r} (shape: shared/conductor/subproc.stage_cmd)")
    ctx = StageContext(stage=a.stage_id, run_dir=run_dir, seed=a.seed, job=job,
                      config=cfg.get("stage_config", {}),
                      input_paths=cfg["input_paths"], output_paths=cfg["output_paths"],
                      backends=_build_backends(cfg))
    try:
        reg.fn(ctx)
    except Quarantined:
        return EXIT_QUARANTINED
    except Degraded:
        return EXIT_DEGRADED
    return EXIT_OK


def _build_backends(cfg: dict):
    # resolved from config: real Ollama/ComfyUI/Kokoro/QwenVL clients per capability (M1-M3),
    # or the fixture fakes when cfg["backends"] == "fake" (CI / the offline DAG).
    from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter
    if cfg.get("backends") == "fake":
        be = FixtureBackend(fixtures_dir=Path(cfg["fixtures_dir"]))
        caps = ["llm", "generate_image", "img2vid", "tts", "vlm_judge", "restore"]
        return {**{c: be for c in caps}, "distribution": FixtureDistributionAdapter()}
    # real wiring resolves per-stage via shared.config.resolve_config (ADR 0010 D5)
    raise NotImplementedError("real-backend wiring lands at host bring-up; CI uses backends=fake")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write the failing tests** (subprocess wrapper: timeout kill + exit mapping)

```python
# tests/test_subproc.py
import sys
from shared.conductor.subproc import run_stage_subprocess, StageOutcome


def test_outcome_maps_exit_codes(tmp_path):
    # use a trivial python -c as the command builder's stand-in via cmd_override
    ok = run_stage_subprocess(cmd=[sys.executable, "-c", "raise SystemExit(0)"], timeout_s=10)
    qr = run_stage_subprocess(cmd=[sys.executable, "-c", "raise SystemExit(77)"], timeout_s=10)
    assert (ok.status, qr.status) == ("done", "quarantined")


def test_timeout_kills_and_fails():
    out = run_stage_subprocess(cmd=[sys.executable, "-c", "import time; time.sleep(30)"],
                               timeout_s=1)
    assert out.status == "failed" and out.timed_out is True


def test_elapsed_recorded():
    out = run_stage_subprocess(cmd=[sys.executable, "-c", "raise SystemExit(0)"], timeout_s=10)
    assert out.elapsed_s >= 0.0
```

- [ ] **Step 3: Implement `shared/conductor/subproc.py`**

```python
import subprocess
import sys
import time
from dataclasses import dataclass

from shared.exitcodes import status_for_exit


@dataclass(frozen=True)
class StageOutcome:
    status: str          # done | quarantined | failed
    exit_code: int
    elapsed_s: float
    timed_out: bool = False


def stage_cmd(stage_id: str, *, run_dir: str, seed: int, config_json: str) -> list[str]:
    """config_json contract (enforced by shorts/stage.py): {"input_paths": {...},
    "output_paths": {...}, "stage_config": {...}, "backends": "fake"|"real",
    "fixtures_dir": "..."} — input_paths/output_paths are REQUIRED."""
    return [sys.executable, "-m", "shorts.stage", stage_id,
            "--run-dir", run_dir, "--seed", str(seed), "--config", config_json]


def run_stage_subprocess(*, cmd: list[str], timeout_s: float) -> StageOutcome:
    """Real per-stage timeout + crash isolation (ADR 0015 D6). `start_new_session` puts the
    stage in its OWN process group so a timeout kills its ffmpeg/helper grandchildren too —
    a leaked GPU helper would silently violate never-co-resident."""
    import os
    import signal
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, start_new_session=True)
    try:
        code = proc.wait(timeout=timeout_s)
        return StageOutcome(status=status_for_exit(code), exit_code=code,
                            elapsed_s=round(time.perf_counter() - t0, 3))
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)   # the whole process GROUP
        proc.wait()
        return StageOutcome(status="failed", exit_code=-1,
                            elapsed_s=round(time.perf_counter() - t0, 3), timed_out=True)
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shorts/ shared/conductor/ tests/test_subproc.py
git commit -m "feat(m4): per-stage CLI + subprocess execution with timeouts (ADR 0015 D6/0015a)"
```

### Task 6: Retry/backoff policy (pure)

**Files:** Create `shared/conductor/retry.py`; Test `tests/test_retry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_retry.py
from shared.conductor.retry import RetryPolicy, run_with_retries
from shared.conductor.subproc import StageOutcome


def _attempts(seq):
    it = iter(seq)
    return lambda: next(it)


def test_retries_failed_then_succeeds():
    seq = [StageOutcome("failed", 1, 0.1), StageOutcome("done", 0, 0.1)]
    out, attempts = run_with_retries(_attempts(seq), RetryPolicy(retries=2, backoff_s=0))
    assert out.status == "done" and attempts == 2


def test_quarantine_is_never_retried():
    seq = [StageOutcome("quarantined", 77, 0.1), StageOutcome("done", 0, 0.1)]
    out, attempts = run_with_retries(_attempts(seq), RetryPolicy(retries=3, backoff_s=0))
    assert out.status == "quarantined" and attempts == 1   # a gate verdict is final


def test_exhausted_retries_stay_failed():
    seq = [StageOutcome("failed", 1, 0.1)] * 3
    out, attempts = run_with_retries(_attempts(seq), RetryPolicy(retries=2, backoff_s=0))
    assert out.status == "failed" and attempts == 3
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/conductor/retry.py`**

```python
import time
from dataclasses import dataclass
from typing import Callable

from shared.conductor.subproc import StageOutcome


@dataclass(frozen=True)
class RetryPolicy:
    retries: int = 2          # additional attempts after the first
    backoff_s: float = 30.0   # multiplied by the attempt number (linear backoff)


def run_with_retries(attempt: Callable[[], StageOutcome],
                     policy: RetryPolicy) -> tuple[StageOutcome, int]:
    """Retries only `failed` outcomes (transient). `quarantined` is a deliberate gate verdict —
    retrying it would re-spend GPU on a parked video."""
    attempts = 0
    while True:
        attempts += 1
        out = attempt()
        if out.status != "failed" or attempts > policy.retries:
            return out, attempts
        time.sleep(policy.backoff_s * attempts)
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/conductor/retry.py tests/test_retry.py
git commit -m "feat(m4): retry/backoff policy — quarantine never retried (ADR 0003 D2)"
```

### Task 7: VRAM-free check + the GPU lock

**Files:** Create `shared/conductor/gpu.py`; Test `tests/test_gpu.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gpu.py
import threading
from shared.conductor.gpu import vram_free_mb, GPU_LOCK


def test_parses_comfyui_system_stats():
    stats = {"devices": [{"name": "cuda:0", "vram_total": 16882998016, "vram_free": 14000000000}]}
    assert vram_free_mb(stats) == 13351          # bytes -> MiB, floor


def test_no_device_returns_zero():
    assert vram_free_mb({"devices": []}) == 0


def test_gpu_lock_serializes():
    order = []
    def worker(i):
        with GPU_LOCK:
            order.append(("in", i)); order.append(("out", i))
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert order[0][0] == "in" and order[1] == ("out", order[0][1])   # no interleave
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/conductor/gpu.py`**

```python
import threading

# Never-co-resident (ADR 0001/0003), conductor-enforced (ADR 0015 D5): every GPU-touching
# stage execution holds this lock; the audio lane never takes it.
GPU_LOCK = threading.Lock()


def vram_free_mb(system_stats: dict) -> int:
    """Parse ComfyUI GET /system_stats; the confirm-evicted gate before diffusion stages."""
    devices = system_stats.get("devices") or []
    if not devices:
        return 0
    return int(devices[0].get("vram_free", 0) // (1024 * 1024))


def confirm_vram(min_free_mb: int, system_stats: dict) -> bool:
    return vram_free_mb(system_stats) >= min_free_mb
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/conductor/gpu.py tests/test_gpu.py
git commit -m "feat(m4): VRAM confirm-evicted gate + conductor GPU lock (ADR 0003/0015 D5)"
```

### Task 8: The batch executor — lane pools, per-video domains, status writes

**Files:** Create `shared/conductor/executor.py`; Test `tests/test_executor.py`

- [ ] **Step 1: Write the failing tests** (injectable stage runner; no real subprocesses)

```python
# tests/test_executor.py
from shared.conductor.executor import execute_batch
from shared.conductor.subproc import StageOutcome


def _runner(script):
    def run(video_id, stage_id):                  # (video, stage) -> StageOutcome
        return script.get((video_id, stage_id), StageOutcome("done", 0, 0.1))
    return run


def test_per_video_failure_domain_isolates(tmp_path):
    batch = {"videos": [{"video_id": "a", "status": "pending"},
                        {"video_id": "b", "status": "pending"}]}
    script = {("a", "00b"): StageOutcome("quarantined", 77, 0.1)}
    result = execute_batch(batch, stage_order=["00a", "00b", "02"],
                           run_stage=_runner(script))
    assert result["a"] == "quarantined"           # a parked at 00b — 02 never ran for a
    assert result["b"] == "done"                  # b unaffected (per-video domain, ADR 0003)


def test_failed_stage_fails_only_that_video():
    batch = {"videos": [{"video_id": "a", "status": "pending"},
                        {"video_id": "b", "status": "pending"}]}
    script = {("b", "02"): StageOutcome("failed", 1, 0.1)}
    result = execute_batch(batch, stage_order=["00a", "00b", "02"], run_stage=_runner(script))
    assert result == {"a": "done", "b": "failed"}


def test_statuses_are_written_through_and_persisted():
    # the boot reconciler reads batch.json — statuses MUST be flushed, not just returned
    batch = {"videos": [{"video_id": "a", "status": "pending"}]}
    flushes = []
    execute_batch(batch, stage_order=["00a"], run_stage=_runner({}),
                  persist=lambda b: flushes.append(True))
    assert batch["videos"][0]["status"] == "done"     # mutated in place
    assert flushes                                     # and persisted


def test_circuit_breaker_halts_on_consecutive_failures():
    import pytest
    from shared.conductor.executor import SystemicFailure
    batch = {"videos": [{"video_id": v, "status": "pending"} for v in ("a", "b", "c")]}
    script = {(v, "00a"): StageOutcome("failed", 1, 0.1) for v in ("a", "b", "c")}
    with pytest.raises(SystemicFailure):              # host-down pattern, not 3x bad luck
        execute_batch(batch, stage_order=["00a", "00b"], run_stage=_runner(script),
                      max_consecutive_failures=3)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/conductor/executor.py`**

```python
from typing import Callable

from shared.conductor.subproc import StageOutcome

# The ADR 0011 lanes; GPU members take GPU_LOCK inside run_stage (stage-batched per stage id).
VISUAL_LANE = ["01a", "01b", "01c", "01d", "01e"]
AUDIO_LANE = ["02", "03", "04"]


class SystemicFailure(Exception):
    """Consecutive failures across videos within ONE stage — the host-down pattern, not
    per-video bad luck (ADR 0003 D4): halt the batch instead of failing N videos."""


def execute_batch(batch: dict, *, stage_order: list[str],
                  run_stage: Callable[[str, str], StageOutcome],
                  persist: Callable[[dict], None] | None = None,
                  max_consecutive_failures: int = 3) -> dict[str, str]:
    """Stage-batched execution (stage-major = GPU-swap-minimizing, ADR 0011) with per-video
    failure domains. Statuses are WRITTEN THROUGH to the batch dict and flushed via `persist`
    after every change — the boot reconciler (ADR 0003 D9) reads batch.json, so an unpersisted
    status would re-run quarantined videos after a reboot."""
    videos = {v["video_id"]: v for v in batch["videos"]}
    for v in videos.values():
        if v["status"] == "pending":
            v["status"] = "running"
    if persist:
        persist(batch)
    for stage_id in stage_order:
        consecutive_failed = 0
        for vid, v in videos.items():
            if v["status"] in ("quarantined", "failed"):
                continue                            # the video's domain is closed
            out = run_stage(vid, stage_id)
            if out.status == "failed":
                consecutive_failed += 1
                if consecutive_failed >= max_consecutive_failures:
                    v["status"] = "failed"
                    if persist:
                        persist(batch)
                    raise SystemicFailure(
                        f"{consecutive_failed} consecutive failures at stage {stage_id} — "
                        f"halting the batch (host-down pattern, ADR 0003 D4)")
            else:
                consecutive_failed = 0              # interleaved success = per-video, not systemic
            if out.status != "done":
                v["status"] = out.status
                if persist:
                    persist(batch)
    for v in videos.values():
        if v["status"] == "running":
            v["status"] = "done"
    if persist:
        persist(batch)
    return {vid: v["status"] for vid, v in videos.items()}
```

> Lane-fork note (ADR 0011, behind the timing metric): when `concurrency.lanes` is enabled in
> config, the conductor runs `VISUAL_LANE` and `AUDIO_LANE` in two `ThreadPoolExecutor` workers
> per video between `00b` and `05` — each worker calling this same `run_stage` (subprocesses do
> the work; GPU stages serialize on `GPU_LOCK`). **Per-video CPU fan-out** (the spec M4 row's
> second ADR 0011 lever) uses the same pool: within a CPU stage, the inner video loop submits
> subprocesses concurrently (`concurrency.fanout: N`); GPU stages are exempt (the lock). Both
> levers default OFF until the M1 timing baseline justifies them; all paths share the
> per-video-domain + write-through rules. The conductor calls `confirm_vram` (Task 7) before
> each GPU stage's video sweep — the confirm-evicted gate (ADR 0015 D5).

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/conductor/executor.py tests/test_executor.py
git commit -m "feat(m4): batch executor — per-video failure domains + lane-fork seam (ADR 0003/0011)"
```

---

# Part C — Scheduling, lifecycle, reconciliation, pre-flight, ledger commit

### Task 9: Run lockfile (atomic, stale-pid takeover)

**Files:** Create `shared/conductor/lock.py`; Test `tests/test_lock.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lock.py
import os
import pytest
from shared.conductor.lock import acquire_lock, release_lock, LockHeld


def test_acquire_then_second_acquire_fails(tmp_path):
    lock = tmp_path / "batch.lock"
    acquire_lock(lock)
    with pytest.raises(LockHeld):
        acquire_lock(lock)
    release_lock(lock)


def test_stale_lock_is_taken_over(tmp_path):
    lock = tmp_path / "batch.lock"
    lock.write_text("999999999")                  # a pid that cannot exist
    acquire_lock(lock)                            # no raise: stale -> takeover
    assert lock.read_text() == str(os.getpid())


def test_unparseable_lock_is_treated_as_held(tmp_path):
    lock = tmp_path / "batch.lock"
    lock.write_text("")                           # a holder mid-write (TOCTOU window)
    with pytest.raises(LockHeld):
        acquire_lock(lock)                        # conservatively held, never stolen
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/conductor/lock.py`**

```python
import os
from pathlib import Path


class LockHeld(Exception):
    """Another batch run holds the lock (concurrencyPolicy: Forbid, ADR 0015 D3)."""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OverflowError):
        return False


def acquire_lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        holder = path.read_text().strip()
        # Unparseable/empty content = a holder mid-write (the create->write window) —
        # conservatively HELD, never stolen (TOCTOU guard).
        if not holder.isdigit() or _pid_alive(int(holder)):
            raise LockHeld(f"batch already running (lock holder: {holder or 'acquiring'})")
        path.unlink()                              # stale: holder pid is dead — take over
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise LockHeld("lost the stale-lock takeover race")
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)


def release_lock(path: Path) -> None:
    path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/conductor/lock.py tests/test_lock.py
git commit -m "feat(m4): run lockfile with stale-pid takeover (replaces concurrencyPolicy, ADR 0015 D3)"
```

### Task 10: Boot-time reconciler (ADR 0003 D9)

**Files:** Create `shared/conductor/reconcile.py`; Test `tests/test_reconcile.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reconcile.py
from shared.conductor.reconcile import resume_plan


def test_resumes_pending_and_running_videos_only():
    batch = {"videos": [{"video_id": "a", "status": "done"},
                        {"video_id": "b", "status": "running"},
                        {"video_id": "c", "status": "pending"},
                        {"video_id": "d", "status": "quarantined"}]}
    assert resume_plan(batch) == ["b", "c"]       # done/quarantined never re-run


def test_clean_batch_resumes_nothing():
    assert resume_plan({"videos": [{"video_id": "a", "status": "done"}]}) == []
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/conductor/reconcile.py`**

```python
def resume_plan(batch: dict) -> list[str]:
    """Boot-time reconciliation (ADR 0003 D9): a host reboot mid-batch leaves videos in
    running/pending; re-running them is SAFE because stages are seeded + idempotent and the
    content-addressed cache skips completed work (ADR 0009/0010)."""
    return [v["video_id"] for v in batch["videos"] if v["status"] in ("running", "pending")]
```

> Wiring: `shorts/run_batch.py` calls `resume_plan` on the newest `runs/<batch-id>/batch.json`
> at startup — if non-empty, it resumes that batch instead of planning a new one. The systemd
> unit (Task 12) runs at boot via the timer's `Persistent=true`, so a reboot-missed batch fires
> on the next WSL start.

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/conductor/reconcile.py tests/test_reconcile.py
git commit -m "feat(m4): boot-time batch reconciler (ADR 0003 D9)"
```

### Task 11: Pre-flight gates + the fan-in ledger commit

**Files:** Create `shared/conductor/preflight.py`, `shared/conductor/ledger.py`; Test `tests/test_preflight.py`, `tests/test_ledger_commit.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_preflight.py
import pytest
from shared.conductor.preflight import run_preflight, PreflightFailure, free_space_gate


def test_free_space_gate_fails_below_minimum(tmp_path):
    with pytest.raises(PreflightFailure):
        free_space_gate(tmp_path, min_free_gb=10**9)   # absurd requirement -> fail


def test_pluggable_checks_run_in_order(tmp_path):
    calls = []
    run_preflight([lambda: calls.append("a"), lambda: calls.append("b")])
    assert calls == ["a", "b"]                    # OAuth token-age slots in here at M5


def test_host_health_gate_fails_on_unhealthy_service():
    from shared.conductor.preflight import host_health_gate
    healthy = {"http://h:8188/system_stats": 200, "http://h:11434/api/version": 200}
    host_health_gate(comfy_url="http://h:8188", ollama_url="http://h:11434",
                     get=lambda u: healthy[u])    # no raise
    with pytest.raises(PreflightFailure):
        host_health_gate(comfy_url="http://h:8188", ollama_url="http://h:11434",
                         get=lambda u: 503)       # fail fast — no retry-storm (ADR 0003 D2)
```

```python
# tests/test_ledger_commit.py
import json
from shared.conductor.ledger import commit_ledgers


def test_single_fanin_appends_once_per_video(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    entries = [{"video_id": "a", "topic": "cpi"}, {"video_id": "b", "topic": "fed"}]
    commit_ledgers(ledger, entries)
    commit_ledgers(ledger, entries)               # idempotent: same entries not duplicated
    lines = [json.loads(l) for l in ledger.read_text().splitlines()]
    assert [l["video_id"] for l in lines] == ["a", "b"]
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement both**

```python
# shared/conductor/preflight.py
import shutil
from pathlib import Path
from typing import Callable


class PreflightFailure(Exception):
    """A pre-batch gate failed — the batch must not start (ADR 0003 D8)."""


def free_space_gate(data_root: Path, *, min_free_gb: float = 80.0) -> None:
    free_gb = shutil.disk_usage(data_root).free / 1e9
    if free_gb < min_free_gb:
        raise PreflightFailure(f"{free_gb:.0f} GB free < {min_free_gb} GB minimum "
                               f"(frames peak ~10 GB/cut — ADR re-review)")


def host_health_gate(*, comfy_url: str, ollama_url: str, get: Callable[[str], int] | None = None) -> None:
    """ADR 0003 D2 / spec Ch.8: the conductor GATES fan-out on host health — an unhealthy host
    fails the batch loudly at the start, never as N per-video retry-storms mid-run."""
    if get is None:
        import httpx
        get = lambda u: httpx.get(u, timeout=10).status_code   # noqa: E731
    for url in (f"{comfy_url}/system_stats", f"{ollama_url}/api/version"):
        if get(url) != 200:
            raise PreflightFailure(f"host service unhealthy: {url}")


def run_preflight(checks: list[Callable[[], None]]) -> None:
    for check in checks:                          # pluggable: M5 adds the OAuth token-age check
        check()
```

```python
# shared/conductor/ledger.py
import json
from pathlib import Path


def commit_ledgers(ledger_path: Path, entries: list[dict]) -> None:
    """THE single fan-in writer (ADR 0003 D6): one appender per batch, idempotent on video_id —
    a resumed batch must not double-append."""
    existing = set()
    if ledger_path.exists():
        existing = {json.loads(l)["video_id"] for l in ledger_path.read_text().splitlines() if l}
    with ledger_path.open("a") as f:
        for e in entries:
            if e["video_id"] not in existing:
                f.write(json.dumps(e) + "\n")
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/conductor/preflight.py shared/conductor/ledger.py tests/test_preflight.py tests/test_ledger_commit.py
git commit -m "feat(m4): pre-flight gates + idempotent fan-in ledger commit (ADR 0003 D6/D8)"
```

### Task 12: systemd units, power-policy doc, `up.sh`/`down.sh` rewrite

**Files:** Create `deploy/host/shorts-batch.service`, `deploy/host/shorts-batch.timer`, `deploy/host/power-policy.md`; Rewrite `scripts/up.sh`, `scripts/down.sh`; Modify `Makefile`

- [ ] **Step 1: Write the systemd units**

```ini
# deploy/host/shorts-batch.service
[Unit]
Description=shorts-creator nightly batch (the conductor, ADR 0015)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
Environment=DATA_ROOT=/srv/shorts-data
WorkingDirectory=/srv/shorts-creator
ExecStart=/srv/shorts-creator/.venv/bin/python -m shorts.run_batch
TimeoutStartSec=10h
```

```ini
# deploy/host/shorts-batch.timer
[Unit]
Description=nightly batch trigger

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 2: Write `deploy/host/power-policy.md`** — the ADR 0015 D3 checklist as a numbered ops doc: (1) `powercfg /change standby-timeout-ac 0` (sleep off on AC); (2) Windows Update active hours set to cover 01:00–06:00 *exclusion*; (3) the Task Scheduler `wsl`-at-logon keep-alive (ADR 0013); (4) verify `systemctl is-enabled shorts-batch.timer` inside the distro; (5) `TimeoutStartSec=10h` is the batch watchdog — a hung conductor is killed, the lockfile goes stale, the next run takes over.

- [ ] **Step 3: Rewrite `scripts/up.sh`** — host services only, health-gated, idempotent: start ComfyUI (pidfile) → `curl :8188/system_stats` until healthy → start Ollama → `curl :11434/api/version` → model present (`ollama list`) → run `python -m shorts.run_batch --preflight-only` as the wire check. `down.sh`: stop by pidfile (unchanged pattern), no cluster branch. **Rewrite `scripts/trigger.sh`** (the spec's manual entry point — same conductor as the timer):

```bash
#!/usr/bin/env bash
# manual batch trigger — byte-identical to the timer's path (ADR 0015 D3)
set -euo pipefail
exec "${VENV:-/srv/shorts-creator/.venv}/bin/python" -m shorts.run_batch "$@"
```

`Makefile`: `wire:` body becomes the two curls; `trigger:` keeps calling `scripts/trigger.sh`; `test:` stays `uv run pytest -q -m "not integration"`.

- [ ] **Step 4: Validate** — `systemd-analyze verify deploy/host/shorts-batch.service` (integration, on the distro); `bash -n scripts/up.sh scripts/down.sh` in CI.

- [ ] **Step 5: Commit.**

```bash
git add deploy/host/ scripts/up.sh scripts/down.sh Makefile
git commit -m "feat(m4): systemd timer + power-policy ops doc + cluster-free up/down (ADR 0015 D3)"
```

---

# Part D — The shared image (the production-deployable artifact)

### Task 13: Dockerfile + the image CI gate

**Files:** Create `Dockerfile`, `.github/workflows/image.yml`; Modify `Makefile` (`build:` body)

- [ ] **Step 1: Write the `Dockerfile`**

```dockerfile
# The ONE shared image (ADR 0015 D2): entrypoint selects a stage or the conductor.
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml
COPY shared/ shared/
COPY stages/ stages/
COPY shorts/ shorts/
COPY schemas/ schemas/
COPY formats/ formats/
COPY profiles/ profiles/
ENTRYPOINT ["python", "-m"]
CMD ["shorts.run_batch"]
# NOTE (honest scope): the Remotion/Node render layer is NOT in this image — the CI gate runs
# the offline DAG with fakes (render is integration). A `render` build stage is added when the
# k8s profile (0015a M7) needs in-cluster rendering.

# The CI-proof stage (ADR 0015 D2): dev deps + tests, used by `make build` and the workflow.
FROM base AS ci
RUN uv pip install --system pytest jsonschema numpy pillow soundfile
COPY tests/ tests/
```

- [ ] **Step 2: Write `.github/workflows/image.yml`**

```yaml
name: image
on:
  push:
    branches: [main]
  workflow_dispatch:
jobs:
  build-and-prove:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build the shared image (ci stage = base + dev deps + tests)
        run: docker build --target ci -t shorts-creator:ci .
      - name: Prove it — run the offline DAG inside the image (ADR 0015 D2)
        run: |
          docker run --rm --entrypoint python shorts-creator:ci \
            -m pytest tests/test_full_dag_offline.py -q
```

- [ ] **Step 3: Wire `make build`** → `docker build --target ci -t shorts-creator:ci .`
- [ ] **Step 4: Run locally** → `make build && docker run --rm --entrypoint python shorts-creator:ci -m pytest tests/test_full_dag_offline.py -q` → PASS.
- [ ] **Step 5: Commit.**

```bash
git add Dockerfile .github/workflows/image.yml Makefile
git commit -m "feat(m4): the shared image + CI proof (offline DAG runs inside it, ADR 0015 D2)"
```

---

# Part E — The conductor CLI + the M4 throughput gate

### Task 14: `shorts/run_batch.py` — plan → preflight → execute → commit → backup

**Files:** Create `shorts/run_batch.py`; Test `tests/test_run_batch_flow.py`

- [ ] **Step 1: Write the failing test** (the flow ordering with injected collaborators)

```python
# tests/test_run_batch_flow.py
from shorts.run_batch import batch_flow


def test_flow_order_and_lock_released_on_failure(tmp_path):
    calls = []
    def boom():
        calls.append("execute"); raise RuntimeError("stage blew up")
    try:
        batch_flow(lock_path=tmp_path / "l", data_root=tmp_path,
                   preflight=lambda: calls.append("preflight"),
                   plan=lambda: calls.append("plan") or {"videos": []},
                   execute=lambda b: boom(),
                   commit=lambda b: calls.append("commit"),
                   backup=lambda: calls.append("backup"))
    except RuntimeError:
        pass
    assert calls == ["preflight", "plan", "execute"]   # commit/backup only after success
    assert not (tmp_path / "l").exists()               # lock ALWAYS released
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shorts/run_batch.py`**

```python
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
```

- [ ] **Step 4: Run** → PASS. **Commit.**

```bash
git add shorts/run_batch.py tests/test_run_batch_flow.py
git commit -m "feat(m4): conductor CLI flow — lock/preflight/plan/execute/commit/backup"
```

### Task 15: The M4 gate — end-to-end throughput reconciliation (open #9)

**Files:** Create `shared/conductor/throughput.py`; Test `tests/test_throughput_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_throughput_gate.py
import pytest
from shared.conductor.throughput import project_batch, ThroughputBust


def test_projection_sums_stage_means_times_videos():
    timings = [{"stage": "00b", "elapsed_s": 300.0}, {"stage": "00b", "elapsed_s": 500.0},
               {"stage": "05", "elapsed_s": 600.0}]
    p = project_batch(timings, n_videos=4, window_hours=8.0)
    assert p["per_video_s"] == 1000.0             # mean(00b)=400 + mean(05)=600
    assert p["batch_s"] == 4000.0 and p["fits"] is True


def test_bust_raises_with_the_breakdown():
    timings = [{"stage": "05", "elapsed_s": 14400.0}]
    with pytest.raises(ThroughputBust):
        project_batch(timings, n_videos=4, window_hours=8.0, raise_on_bust=True)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/conductor/throughput.py`**

```python
from collections import defaultdict


class ThroughputBust(Exception):
    """The projected batch exceeds the overnight window — the unattended DoD rests on this
    number (spec Ch.10 open #9; deferred across ADRs 0005-0008, settled HERE)."""


def project_batch(timings: list[dict], *, n_videos: int, window_hours: float,
                  raise_on_bust: bool = False) -> dict:
    """Roll per-stage means (from timing.jsonl, M1 StageTimer + M2 compositor_mspf) into a
    serial per-video cost and project the batch against the window. Lane-fork overlap (ADR
    0011) only IMPROVES on this serial projection — so a serial fit is a sufficient gate."""
    by_stage: dict[str, list[float]] = defaultdict(list)
    for t in timings:
        by_stage[t["stage"]].append(t["elapsed_s"])
    per_video = sum(sum(v) / len(v) for v in by_stage.values())
    batch_s = per_video * n_videos
    fits = batch_s <= window_hours * 3600
    report = {"per_video_s": round(per_video, 1), "batch_s": round(batch_s, 1),
              "window_s": window_hours * 3600, "fits": fits,
              "by_stage": {k: round(sum(v) / len(v), 1) for k, v in by_stage.items()}}
    if raise_on_bust and not fits:
        raise ThroughputBust(str(report))
    return report
```

- [ ] **Step 4: Add the on-box gate** — an `@pytest.mark.integration` test that loads the real `timing.jsonl` from a full real-backend batch run, calls `project_batch(..., raise_on_bust=True)`, and writes `runs/.metrics/throughput_report.json`. **M4 is not done until this passes on the box** (spec Ch.10 M4 gate).

```python
@pytest.mark.integration
def test_overnight_window_gate_on_the_box():
    import json
    from pathlib import Path
    timings = [json.loads(l) for l in Path("runs/.metrics/timing.jsonl").read_text().splitlines()]
    report = project_batch(timings, n_videos=4, window_hours=8.0, raise_on_bust=True)
    Path("runs/.metrics/throughput_report.json").write_text(json.dumps(report))
```

- [ ] **Step 5: Run** the pure tests → PASS (2). **Commit.**

```bash
git add shared/conductor/throughput.py tests/test_throughput_gate.py
git commit -m "feat(m4): the M4 gate — overnight throughput reconciliation (open #9)"
```

---

## M4 Acceptance Checklist (the testable "done")

- [ ] `plan_batch` produces a schema-valid, **seed-deterministic** `batch.json` honoring the lane mix (PoC default 80/20), format lane-compat + anti-repeat, and topic reservation → Tasks 2–4.
- [ ] Stages run as **subprocesses in their own process group** (timeout kills grandchildren); exit codes map to statuses; **quarantine is never retried**; a failing video closes only **its own domain**; statuses are **written through + persisted**; **≥3 consecutive failures in one stage halt the batch** (the ADR 0003 D4 systemic classification); the **host-health gate** runs before fan-out → Tasks 1, 5, 6, 8, 11.
- [ ] **Never-co-resident** is conductor-enforced (GPU lock + the VRAM confirm-evicted gate) → Task 7.
- [ ] A second trigger is rejected by the **lockfile** (stale locks taken over); a reboot **resumes** the interrupted batch; pre-flight gates run before fan-out; the **fan-in ledger commit is idempotent** → Tasks 9–11, 14.
- [ ] The **systemd timer** fires the batch in WSL2 (`Persistent=true`) and **`scripts/trigger.sh`** is the byte-identical manual entry point; the **power-policy doc** exists; `up.sh`/`down.sh` are cluster-free and health-gated; **`batch.per_niche` (default 1) is the cadence-ramp knob** (ADR 0014 D2, "the phased daily batch") → Task 12 + the decisions header.
- [ ] The **shared image builds in CI and the offline DAG passes inside it** → Task 13.
- [ ] **The M4 gate:** `project_batch` over a real on-box batch fits the overnight window, report persisted → Task 15.

---

## Self-Review

**Spec coverage (ADR 0015 D6 + spec Ch.10 M4 row):** batch planner + lane mix + rotation + topic reservation → A (T2–T4, ADR 0006 D2/0002/0003 D5); subprocess-per-stage (process-group kill) + timeouts + exit protocol → B (T1, T5); retries (quarantine-final) + per-video domains + **status write-through** + the **systemic circuit breaker** (ADR 0003 D4) → T6/T8; never-co-resident + VRAM gate → T7 (ADR 0015 D5); lane-fork **and per-video CPU fan-out** seams behind the timing metric → T8 note (ADR 0011); lockfile + systemd timer + **`trigger.sh`** + boot reconciler + power policy + **the `per_niche` ramp knob** (ADR 0014 D2) → C (T9/T10/T12, ADR 0015 D3 / 0003 D9); pre-flight (**free-space + host-health gate**, ADR 0003 D2/D8) + fan-in ledger commit + backups → T11/T14 (ADR 0003 D6, spec Ch.8); the shared image CI-proven → D (T13, ADR 0015 D2); the throughput gate → E (T15, open #9). OAuth token-age pre-flight is **M5** (the check framework is here, T11; noted). The 0015a k8s profile is **M7** (T5's CLI is its entrypoint; noted).

**Placeholder scan:** the two `raise NotImplementedError`/stub bodies (`_build_backends` real wiring, `run_batch.main` production wiring) are documented bring-up seams whose tested pure collaborators are all implemented here (`batch_flow`, the planner, the executor) — consistent with the M1–M3 seam discipline. No "TBD"/"add error handling".

**Type consistency vs M0–M3:** `StageContext(stage, run_dir, seed, job, config, input_paths, output_paths, backends)` matches M0; `Quarantined`/`Degraded` from `shared.ctx`; `REGISTRY`/`load_all` from M0; `FixtureBackend(fixtures_dir=)` + capability names incl. `restore` match M0; `StageOutcome` is defined in T5 and consumed in T6/T8; `status_for_exit` (T1) is the single exit↔status mapping; statuses reuse the ADR 0012 §4 enum (`pending/running/done/quarantined/failed`). `FormatRegistry` (M3) supplies `formats` to `pick_format` via `.all()`.

**Scope:** one milestone, one gate, produces working testable software (a plannable, schedulable, crash-isolated nightly batch + the proven image + the throughput verdict). Parts A–E are separable for review; C/D are independent of A/B.
