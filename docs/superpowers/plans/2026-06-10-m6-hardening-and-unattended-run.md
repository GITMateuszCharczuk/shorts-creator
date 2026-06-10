# M6 — Hardening, Observability, the Calibration Loop + the Unattended Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pipeline *survive two weeks alone*, then prove it does. Stand up the **observability backend** (Prometheus + node/DCGM/queue exporters + per-stage duration/heartbeat metrics, ADR 0003 D7), the **alerting** (host-down / disk>80% / batch-failed / quarantine-spike / stage-stuck) with a **slow-vs-stuck** classifier, the **retention/GC** sweep + **cache eviction** (ADR 0003 D8 / 0010), and **wire the M5 credential + quota pre-flight** into the actual run flow. Close the one analytical loop the design has been deferring: **re-anchor the 05c quality floor on the ramp's approve/reject labels** (ADR 0016 D2) and ship the **weekly spot-audit**. Then run the **~1–2 week unattended batch** that satisfies the Chapter 1 Definition of Done — with an offline **soak harness** as the CI-able proxy for the stability mechanics.

**Architecture:** No new stages — M6 hardens the M4 conductor and the M5 gates and adds **out-of-band tooling** (CLIs + ops config). All the *logic* is pure and CI-tested behind thin modules: metrics emission to a **Prometheus textfile collector** (`shared/obs/`), the GC retention policy + cache LRU (`shared/ops/`), the floor calibration math (`shared/calibration/`), and the audit report (`shared/audit/`). The deployment surface (Prometheus/Alertmanager/Grafana/exporters) is **data files under `deploy/obs/`** — no code. The unattended run is driven by the existing M4 `systemd` timer; M6 adds the **GC + metrics emission to the post-batch step** and the **full pre-flight list** to `run_batch`. CI stays GPU-free and network-free; the real run is the on-box gate.

**Tech Stack:** Python 3.12 + the M0–M5 toolchain (no new runtime deps for the pure layer); Prometheus + node-exporter + **DCGM-exporter** + Alertmanager + Grafana (host services, deployed by config); the metrics path uses the **node-exporter textfile collector** (a directory of `*.prom` files) so the conductor needs no metrics server. CI runs only pure/fake tests (`-m "not integration"`); `make soak` runs the offline DAG repeatedly with fakes.

**Decisions made here (spec/ADRs left open; pinned for M6 — resolving open-items #3/#10/#11):**
- **05c floor re-anchoring method (ADR 0016 D2; open #10):** from the `feature_record.ramp_label` set (M5) + each video's `creative_qc.overall`, pick the floor that **maximizes F1 against the human labels with a precision-on-"keep" ≥ 0.85 constraint** (we would rather hold a good video than post a bad one). A **minimum-label guard** (`min_labels = 20`, config) keeps the **provisional 0.70** until enough labels exist. The output is a **recommendation written to config + a calibration report** — never an automatic silent change to the live floor; an operator promotes it. The judge *model/prompt* pick stays as decided at M3 bring-up; M6 only moves the *threshold* from guess to data.
- **Slow-vs-stuck (ADR 0003 D7; the 3am-stall problem):** per-stage **expected-duration baselines** = `p95` of the trailing `timing.jsonl` window (M1's `StageTimer`). A running stage is **slow** when `elapsed > p95 × slow_factor` (default 1.5) and **stuck** when `elapsed > hard_deadline` (the M4 per-stage timeout) **or** no **heartbeat** for `> heartbeat_timeout` (default 180 s). Slow → warn; stuck → the M4 timeout already kills it, and the alert distinguishes the two so a human isn't paged for a merely-slow FLUX run.
- **Quarantine-rate spike (alert):** fire when the **trailing-window** (last `N=20` videos) quarantine rate exceeds **max(2× the trailing-batch baseline, 0.30 absolute)** — a content-quality or host regression, distinct from a single bad video. Config.
- **Retention/GC (ADR 0003 D8):** keep `runs/<batch>/` for **last 7 days OR last 14 batches** (whichever is larger), `quarantine/` for **30 days** (longer — the spot-audit needs it), and the content-addressed cache under a **size cap (50 GB, LRU by atime)**. **`history/*.jsonl` and `models/` are NEVER GC'd** (the only unrecoverable state + the weight cache). All numbers config; the sweep runs in the post-batch step after `backup()`.
- **Cache substrate (open #11):** the M0 content-addressed cache is **file-based** under `DATA_ROOT/.cache/<stage>/<input_hash>-<seed>/` (no sqlite for the PoC — simplest, ADR 0010); eviction is the GC's LRU-by-size pass. The feature record stays a **per-video JSON artifact** consumed by the fan-in (not a separate metrics store) — resolving the open #11 "ledger vs metrics store" call toward the simplest path.
- **Per-API budgets (open #10):** daily budgets live in config (`budgets.youtube_units: 10000`, `budgets.alpha_vantage_calls: 25`, etc.); the M5 `youtube_quota_gate` reads them; **FRED/stooq are keyless/free** (no budget needed), **Alpha Vantage is quotes-only with a low cap** (ADR 0009 #8). The data-API budget gate joins the pre-flight list.
- **The pre-flight list is wired, in order:** `free_space_gate` → `host_health_gate` → `oauth_token_age_gate(mode)` → `youtube_quota_gate` → `data_api_budget_gate`. A systemic failure (any gate) **halts the batch with an alert** (ADR 0003 D2/D8), never a per-video quarantine.
- **The soak harness is the CI proxy, not the DoD:** `make soak N=14` runs N offline batches with fakes against a **simulated clock**, asserting the *stability mechanics* — lock stale-takeover, reconcile-after-kill, GC sweep bounds, ledger monotonic growth, **zero wedges, zero silent failures**. The **real ~1–2 week on-box run** (the DoD gate) is recorded in `deploy/host/soak-runbook.md` with a **daily acceptance log**; soak green is necessary, not sufficient.
- **The weekly spot-audit (DoD clause 2):** `make audit` produces a report — the week's posts (with URLs), quarantine reasons by check, the `creative_qc` score distribution, and **label↔score agreement drift** — the artifact the human spot-check reads. It reads ledgers + feature records read-only; it posts nothing and changes nothing.

---

## File Structure

```
shared/obs/                                 # NEW: observability (pure emission + classification)
  __init__.py
  metrics.py                                # write per-stage duration/heartbeat/counters as Prometheus .prom (textfile collector)
  baselines.py                              # p95 expected-duration baselines + slow/stuck classifier (from timing.jsonl)
  quarantine_rate.py                        # trailing-window quarantine rate for the spike alert
shared/ops/                                 # NEW: lifecycle hygiene (pure policy)
  __init__.py
  gc.py                                     # retention sweep: which runs/ + quarantine/ dirs to delete (never history/models)
  cache_evict.py                            # content-addressed cache LRU eviction by size cap (open #11)
  budgets.py                                # data_api_budget_gate (open #10); reads ctx.config["budgets"]
shared/calibration/                         # NEW: the 05c floor re-anchoring (ADR 0016 D2)
  __init__.py
  anchor.py                                 # labels + creative_qc scores -> recommended floor + calibration report
shared/audit/                               # NEW: the weekly spot-audit
  __init__.py
  report.py                                 # assemble posts + quarantines + scores + label drift (read-only)
shared/conductor/run_batch.py               # MODIFY: wire the full preflight list + post-batch GC + metrics emission
shared/conductor/preflight.py               # MODIFY: data_api_budget_gate joins the framework
shorts/audit.py                             # NEW: python -m shorts.audit (make audit): the weekly report
shorts/calibrate.py                         # NEW: python -m shorts.calibrate (make calibrate): the recommended floor
deploy/obs/
  prometheus.yml                            # scrape: node-exporter, DCGM-exporter, comfyui-queue, textfile collector
  alerts.yml                                # host-down / disk>80% / batch-failed / quarantine-spike / stage-stuck
  alertmanager.yml                          # the notification route (a single low-friction channel)
  grafana-dashboard.json                    # per-stage duration + GPU/VRAM + ComfyUI queue depth
  comfyui-queue-exporter.md                 # the small queue-depth exporter (script + scrape note)
deploy/host/
  soak-runbook.md                           # the ~1-2 week run procedure + the daily acceptance-log template
Makefile                                    # add audit / calibrate / soak / obs-up targets
tests/
  test_metrics.py  test_baselines.py  test_quarantine_rate.py
  test_gc.py  test_cache_evict.py  test_budgets.py
  test_calibration_anchor.py  test_audit_report.py
  test_preflight_wiring.py  test_soak_offline.py
```

**Responsibility split:** `shared/obs/` = what to emit + how to read it back for slow/stuck; `shared/ops/` = what to delete + what to never touch; `shared/calibration/` = turn labels into a threshold recommendation; `shared/audit/` = the human-readable weekly view; `deploy/obs/` = the monitoring stack as config. The only conductor change is additive wiring in `run_batch` (the seams M4/M5 left). No stage changes.

---

# Part A — Observability backend

### Task 1: Per-stage metrics emission (Prometheus textfile collector)

The conductor needs no metrics server: it writes `*.prom` files into the node-exporter **textfile-collector** dir, which Prometheus scrapes via node-exporter. Pure formatting + an atomic file write.

**Files:** Create `shared/obs/__init__.py` (empty), `shared/obs/metrics.py`; Test `tests/test_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_metrics.py
from shared.obs.metrics import render_stage_metrics, write_metrics


def test_renders_prometheus_text_with_labels_and_heartbeat():
    text = render_stage_metrics(batch_id="2026-06-11", stage="05b", video_id="v1",
                                duration_s=12.5, status="done", heartbeat_ts=1718000000)
    assert 'shorts_stage_duration_seconds{batch="2026-06-11",stage="05b",video="v1"} 12.5' in text
    assert 'shorts_stage_status{batch="2026-06-11",stage="05b",video="v1",status="done"} 1' in text
    assert "shorts_stage_heartbeat_timestamp" in text and "1718000000" in text


def test_write_is_atomic(tmp_path):
    out = tmp_path / "stage.prom"
    write_metrics(out, "shorts_test 1\n")
    assert out.read_text() == "shorts_test 1\n"
    assert not list(tmp_path.glob("*.tmp"))           # temp file renamed away
```

- [ ] **Step 2: Implement `shared/obs/metrics.py`**

```python
import os
from pathlib import Path


def render_stage_metrics(*, batch_id, stage, video_id, duration_s, status, heartbeat_ts) -> str:
    lbl = f'batch="{batch_id}",stage="{stage}",video="{video_id}"'
    return (f"shorts_stage_duration_seconds{{{lbl}}} {duration_s}\n"
            f'shorts_stage_status{{{lbl},status="{status}"}} 1\n'
            f"shorts_stage_heartbeat_timestamp{{{lbl}}} {heartbeat_ts}\n")


def write_metrics(path: Path, text: str) -> None:
    """Atomic write into the node-exporter textfile-collector dir (Prometheus scrapes it).
    Temp+rename so a scrape never reads a half-written file (ADR 0003 D7)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"{path}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
```

- [ ] **Step 3: Wire emission into the M4 executor** — after each stage outcome (M4 `execute_batch`), the conductor calls `write_metrics(DATA_ROOT/.metrics/textfile/<video>-<stage>.prom, render_stage_metrics(...))` using the M1 `StageTimer` duration + the heartbeat the subprocess updates. Batch-level counters (`shorts_batch_videos_total`, `shorts_quarantine_total`) are emitted at the fan-in step. (Integration: the textfile dir is the node-exporter `--collector.textfile.directory`.)
- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/obs/__init__.py shared/obs/metrics.py tests/test_metrics.py
git commit -m "feat(m6): per-stage Prometheus metrics via the textfile collector (ADR 0003 D7)"
```

### Task 2: The monitoring stack as config (Prometheus + exporters + Grafana)

**Files:** Create `deploy/obs/prometheus.yml`, `deploy/obs/grafana-dashboard.json`, `deploy/obs/comfyui-queue-exporter.md`; Modify `Makefile` (`obs-up`)

- [ ] **Step 1: Write `deploy/obs/prometheus.yml`** — scrape jobs for **node-exporter** (host + `--collector.textfile.directory=DATA_ROOT/.metrics/textfile`), **DCGM-exporter** (GPU/VRAM, ADR 0003 D7), and the **ComfyUI queue-depth** exporter (`:8188/prompt` queue length). 15s interval; `rule_files: [alerts.yml]`.
- [ ] **Step 2: Write `deploy/obs/comfyui-queue-exporter.md`** — the small sidecar: a 20-line script polling ComfyUI's `/queue` (or `/prompt`) and writing `comfyui_queue_depth` to a `.prom` file in the textfile dir (no new service — reuses node-exporter), with the scrape note. This keeps the GPU plane's backpressure visible (a deep queue = the visual lane falling behind, the unattended-stall precursor).
- [ ] **Step 3: Write `deploy/obs/grafana-dashboard.json`** — panels: per-stage `p50/p95` duration (from `shorts_stage_duration_seconds`), GPU util + VRAM free (DCGM), ComfyUI queue depth, batch videos done/quarantined/held, disk free %. The 3am-stall dashboard.
- [ ] **Step 4: Wire `make obs-up`** → start node-exporter (with the textfile dir), DCGM-exporter, Prometheus (this config), Alertmanager (Task 5), Grafana (import the dashboard) — host services, idempotent, health-gated (mirrors `up.sh`). Persisted logs: point each service's stdout to `DATA_ROOT/.logs/` (not just journald) per spec Ch.8. **Commit.**

```bash
git add deploy/obs/prometheus.yml deploy/obs/grafana-dashboard.json deploy/obs/comfyui-queue-exporter.md Makefile
git commit -m "feat(m6): monitoring stack as config — Prometheus + DCGM + ComfyUI-queue + Grafana (ADR 0003 D7)"
```

---

# Part B — Alerting + slow-vs-stuck

### Task 3: Expected-duration baselines + the slow/stuck classifier

**Files:** Create `shared/obs/baselines.py`; Test `tests/test_baselines.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_baselines.py
from shared.obs.baselines import stage_baselines, classify


def test_p95_baseline_per_stage():
    timings = [{"stage": "05", "elapsed_s": s} for s in (100, 110, 120, 130, 900)]
    base = stage_baselines(timings)
    assert 130 <= base["05"] <= 900           # p95 sits at the high end, not the mean


def test_classify_running_slow_vs_stuck():
    base = {"05": 120.0}
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600, last_heartbeat_age_s=5) == "ok"
    assert classify("05", elapsed_s=250, base=base, hard_deadline_s=600, last_heartbeat_age_s=5) == "slow"
    assert classify("05", elapsed_s=700, base=base, hard_deadline_s=600, last_heartbeat_age_s=5) == "stuck"
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600, last_heartbeat_age_s=300) == "stuck"


def test_unknown_stage_is_never_falsely_slow():
    assert classify("99", elapsed_s=10, base={}, hard_deadline_s=600, last_heartbeat_age_s=1) == "ok"
```

- [ ] **Step 2: Implement `shared/obs/baselines.py`**

```python
from collections import defaultdict


def _p95(xs: list[float]) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(0.95 * len(s)))] if s else 0.0


def stage_baselines(timings: list[dict]) -> dict[str, float]:
    by: dict[str, list[float]] = defaultdict(list)
    for t in timings:
        by[t["stage"]].append(t["elapsed_s"])
    return {stage: _p95(v) for stage, v in by.items()}


def classify(stage: str, *, elapsed_s: float, base: dict[str, float], hard_deadline_s: float,
             last_heartbeat_age_s: float, slow_factor: float = 1.5,
             heartbeat_timeout_s: float = 180.0) -> str:
    """ok | slow | stuck. STUCK (page a human / the M4 timeout fires) = past the hard deadline OR a
    dead heartbeat. SLOW (warn only) = past p95*slow_factor but still progressing. Unknown stage with
    no baseline can only be stuck (deadline/heartbeat), never 'slow' — no false 3am pages."""
    if elapsed_s > hard_deadline_s or last_heartbeat_age_s > heartbeat_timeout_s:
        return "stuck"
    b = base.get(stage)
    if b and elapsed_s > b * slow_factor:
        return "slow"
    return "ok"
```

- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/obs/baselines.py tests/test_baselines.py
git commit -m "feat(m6): expected-duration baselines + slow-vs-stuck classifier (ADR 0003 D7)"
```

### Task 4: Quarantine-rate spike detector

**Files:** Create `shared/obs/quarantine_rate.py`; Test `tests/test_quarantine_rate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quarantine_rate.py
from shared.obs.quarantine_rate import trailing_rate, is_spike


def test_trailing_rate_over_window():
    outcomes = ["done"] * 16 + ["quarantined"] * 4         # 20% over 20
    assert abs(trailing_rate(outcomes, window=20) - 0.20) < 1e-9


def test_spike_vs_absolute_floor_and_baseline_multiple():
    # absolute floor 0.30 trips regardless of baseline
    assert is_spike(rate=0.35, baseline=0.30, abs_floor=0.30, mult=2.0) is True
    # 2x baseline trips even under the absolute floor
    assert is_spike(rate=0.25, baseline=0.10, abs_floor=0.30, mult=2.0) is True
    assert is_spike(rate=0.12, baseline=0.10, abs_floor=0.30, mult=2.0) is False
```

- [ ] **Step 2: Implement `shared/obs/quarantine_rate.py`**

```python
def trailing_rate(outcomes: list[str], *, window: int = 20) -> float:
    recent = outcomes[-window:]
    if not recent:
        return 0.0
    return sum(1 for o in recent if o == "quarantined") / len(recent)


def is_spike(*, rate: float, baseline: float, abs_floor: float = 0.30, mult: float = 2.0) -> bool:
    """A spike = a content-quality or host regression, not one bad video: trip on the higher of an
    absolute floor or a multiple of the trailing baseline (emitted as shorts_quarantine_rate)."""
    return rate >= abs_floor or rate >= baseline * mult
```

- [ ] **Step 3: Run** → PASS (2). **Commit.**

```bash
git add shared/obs/quarantine_rate.py tests/test_quarantine_rate.py
git commit -m "feat(m6): quarantine-rate spike detector (trailing window, ADR 0003 D7)"
```

### Task 5: Alert rules + Alertmanager route

**Files:** Create `deploy/obs/alerts.yml`, `deploy/obs/alertmanager.yml`

- [ ] **Step 1: Write `deploy/obs/alerts.yml`** — Prometheus rules (the conductor/exporters emit the series these read):
  - `HostDown` — `up{job="node"} == 0` for 2m.
  - `DiskAlmostFull` — `node_filesystem_avail / size < 0.20` (disk > 80%, the disk-full SPOF, ADR 0003 D8).
  - `BatchFailed` — `shorts_batch_failed_total` increased in the last run window (the systemic-halt signal).
  - `QuarantineSpike` — `shorts_quarantine_rate > 0.30` (Task 4's series).
  - `StageStuck` — `time() - shorts_stage_heartbeat_timestamp > 180` while a stage is running (Task 3's stuck condition; `StageSlow` as a separate warn-severity rule).
  - `GPUUnhealthy` — DCGM `DCGM_FI_DEV_XID_ERRORS > 0` or VRAM-free below the diffusion floor for 5m.
- [ ] **Step 2: Write `deploy/obs/alertmanager.yml`** — one low-friction route (email/webhook; the operator picks the receiver at bring-up). Group by `alertname`; `repeat_interval: 4h` so a 3am stall pages once, not every scrape.
- [ ] **Step 3: Validate** (integration, on the box): `promtool check rules deploy/obs/alerts.yml`; `amtool check-config deploy/obs/alertmanager.yml`. **Commit.**

```bash
git add deploy/obs/alerts.yml deploy/obs/alertmanager.yml
git commit -m "feat(m6): alert rules + route — host-down/disk/batch-failed/quarantine-spike/stage-stuck (ADR 0003 D7)"
```

---

# Part C — Retention/GC, cache eviction, pre-flight wiring

### Task 6: Retention/GC sweep (never `history/` or `models/`)

**Files:** Create `shared/ops/__init__.py` (empty), `shared/ops/gc.py`; Test `tests/test_gc.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gc.py
from shared.ops.gc import runs_to_delete, quarantine_to_delete, PROTECTED


def test_keeps_recent_runs_by_count_and_age():
    runs = [{"id": f"b{i}", "age_days": i, "kind": "batch"} for i in range(20)]
    keep_min = runs_to_delete(runs, keep_days=7, keep_count=14)
    # nothing within 7 days OR within the newest 14 is deleted
    deleted = {r["id"] for r in keep_min}
    assert "b0" not in deleted and "b5" not in deleted        # recent / within count
    assert "b19" in deleted                                   # old AND beyond the count


def test_quarantine_kept_longer():
    q = [{"id": "q1", "age_days": 10}, {"id": "q2", "age_days": 40}]
    assert [r["id"] for r in quarantine_to_delete(q, keep_days=30)] == ["q2"]


def test_history_and_models_are_never_candidates():
    assert "history" in PROTECTED and "models" in PROTECTED
```

- [ ] **Step 2: Implement `shared/ops/gc.py`**

```python
PROTECTED = {"history", "models"}        # the only unrecoverable state + the weight cache — NEVER GC'd


def runs_to_delete(runs: list[dict], *, keep_days: int = 7, keep_count: int = 14) -> list[dict]:
    """Delete a run only if it is BOTH older than keep_days AND outside the newest keep_count
    (ADR 0003 D8). The OR-keep means a quiet week never deletes the only recent batches."""
    by_age = sorted(runs, key=lambda r: r["age_days"])
    kept_by_count = {r["id"] for r in by_age[:keep_count]}
    return [r for r in runs if r["age_days"] > keep_days and r["id"] not in kept_by_count]


def quarantine_to_delete(quarantines: list[dict], *, keep_days: int = 30) -> list[dict]:
    """Quarantine lives longer than runs — the weekly spot-audit reads it (DoD clause 2)."""
    return [q for q in quarantines if q["age_days"] > keep_days]
```

- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/ops/__init__.py shared/ops/gc.py tests/test_gc.py
git commit -m "feat(m6): retention/GC sweep — runs/quarantine policy, history/models protected (ADR 0003 D8)"
```

### Task 7: Content-addressed cache LRU eviction by size cap

**Files:** Create `shared/ops/cache_evict.py`; Test `tests/test_cache_evict.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cache_evict.py
from shared.ops.cache_evict import evict_to_cap


def test_evicts_least_recently_used_until_under_cap():
    entries = [{"key": "a", "size_gb": 30, "atime": 1}, {"key": "b", "size_gb": 30, "atime": 2},
               {"key": "c", "size_gb": 30, "atime": 3}]               # 90 GB, cap 50
    evicted = evict_to_cap(entries, cap_gb=50)
    assert [e["key"] for e in evicted] == ["a", "b"]                  # oldest atime first; c (30) fits
    assert sum(e["size_gb"] for e in entries if e["key"] not in {x["key"] for x in evicted}) <= 50


def test_under_cap_evicts_nothing():
    assert evict_to_cap([{"key": "a", "size_gb": 10, "atime": 1}], cap_gb=50) == []
```

- [ ] **Step 2: Implement `shared/ops/cache_evict.py`**

```python
def evict_to_cap(entries: list[dict], *, cap_gb: float = 50.0) -> list[dict]:
    """LRU by atime until total <= cap (open #11: file-based cache, swept by the GC step). Returns
    the entries to delete; the caller unlinks their dirs under DATA_ROOT/.cache/."""
    total = sum(e["size_gb"] for e in entries)
    if total <= cap_gb:
        return []
    evicted = []
    for e in sorted(entries, key=lambda x: x["atime"]):      # oldest access first
        if total <= cap_gb:
            break
        evicted.append(e)
        total -= e["size_gb"]
    return evicted
```

- [ ] **Step 3: Run** → PASS (2). **Commit.**

```bash
git add shared/ops/cache_evict.py tests/test_cache_evict.py
git commit -m "feat(m6): content-addressed cache LRU eviction by size cap (open #11, ADR 0010)"
```

### Task 8: Data-API budget gate + wire the full pre-flight list + post-batch GC/metrics

**Files:** Create `shared/ops/budgets.py`; Modify `shared/conductor/preflight.py`, `shared/conductor/run_batch.py`; Test `tests/test_budgets.py`, `tests/test_preflight_wiring.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_budgets.py
import pytest
from shared.ops.budgets import data_api_budget_gate
from shared.conductor.preflight import PreflightFailure


def test_keyless_sources_never_block():
    data_api_budget_gate(used={"alpha_vantage": 0}, planned={"fred": 10, "stooq": 10}, budgets={})


def test_capped_source_blocks_over_budget():
    with pytest.raises(PreflightFailure):
        data_api_budget_gate(used={"alpha_vantage": 24}, planned={"alpha_vantage": 5},
                             budgets={"alpha_vantage": 25})
```

```python
# tests/test_preflight_wiring.py
from shared.conductor.run_batch import build_preflight


def test_preflight_runs_all_gates_in_order():
    calls = []
    gates = build_preflight(hooks={
        "free_space": lambda: calls.append("free_space"),
        "host_health": lambda: calls.append("host_health"),
        "oauth": lambda: calls.append("oauth"),
        "youtube_quota": lambda: calls.append("youtube_quota"),
        "data_budget": lambda: calls.append("data_budget")})
    for g in gates:
        g()
    assert calls == ["free_space", "host_health", "oauth", "youtube_quota", "data_budget"]
```

- [ ] **Step 2: Implement `shared/ops/budgets.py`**

```python
from shared.conductor.preflight import PreflightFailure


def data_api_budget_gate(*, used: dict, planned: dict, budgets: dict) -> None:
    """Open #10. A source with NO budget entry is keyless/free (FRED/stooq) — never blocks. A
    capped source (Alpha Vantage quotes-only) fails the batch BEFORE fan-out if it would overrun
    the day's cap (ADR 0009 #8) — a systemic halt, not a per-video quarantine."""
    for src, cap in budgets.items():
        if used.get(src, 0) + planned.get(src, 0) > cap:
            raise PreflightFailure(f"{src} budget: used {used.get(src,0)} + planned "
                                   f"{planned.get(src,0)} > {cap}")
```

- [ ] **Step 3: Wire `shared/conductor/run_batch.py`** — add `build_preflight(hooks)` returning the ordered list `[free_space, host_health, oauth, youtube_quota, data_budget]` (each a closure over the resolved config/credentials), passed to the M4 `batch_flow(preflight=...)`. Production `main()` resolves: `free_space_gate(DATA_ROOT)`, `host_health_gate(comfy,ollama)`, `oauth_token_age_gate(mode=config.oauth_mode, ...)`, `youtube_quota_gate(used, planned_inserts, ...)`, `data_api_budget_gate(...)`. Add the **post-batch hygiene** after `backup()`: run `runs_to_delete`/`quarantine_to_delete`/`evict_to_cap` (unlinking the returned dirs) and emit the batch-level metrics (`shorts_batch_*`, `shorts_quarantine_rate`). The real model-backend wiring (`_build_backends`, the M4/M5 seam) is completed here for the on-box run, with `--dry-run` staging metadata and posting nothing (spec Ch.8).
- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/ops/budgets.py shared/conductor/preflight.py shared/conductor/run_batch.py tests/test_budgets.py tests/test_preflight_wiring.py
git commit -m "feat(m6): data-API budget gate + full pre-flight list + post-batch GC/metrics wiring (ADR 0003 D2/D8/0009 #8/#10)"
```

---

# Part D — The calibration loop + the weekly spot-audit

### Task 9: Re-anchor the 05c quality floor from the ramp labels (ADR 0016 D2)

The M5 ramp captured `feature_record.ramp_label` (approve/reject) alongside `creative_qc.overall`. M6 turns that into a **data-anchored floor recommendation** — closing the design's longest-standing "the floor is a guess" caveat.

**Files:** Create `shared/calibration/__init__.py` (empty), `shared/calibration/anchor.py`, `shorts/calibrate.py`; Modify `Makefile`; Test `tests/test_calibration_anchor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_calibration_anchor.py
from shared.calibration.anchor import recommend_floor, PROVISIONAL


def test_holds_provisional_until_enough_labels():
    few = [{"overall": 0.8, "approved": True}] * 5
    rec = recommend_floor(few, min_labels=20)
    assert rec["floor"] == PROVISIONAL and rec["reason"] == "insufficient_labels"


def test_picks_a_separating_floor_with_keep_precision_constraint():
    # approved cluster high, rejected cluster low -> the floor lands between them
    labels = ([{"overall": o, "approved": True} for o in (0.74, 0.78, 0.82, 0.9, 0.95)] +
              [{"overall": o, "approved": False} for o in (0.40, 0.52, 0.60, 0.66, 0.69)]) * 3
    rec = recommend_floor(labels, min_labels=20, min_keep_precision=0.85)
    assert 0.69 <= rec["floor"] <= 0.74           # separates the clusters
    assert rec["keep_precision"] >= 0.85 and 0.0 <= rec["f1"] <= 1.0
    assert rec["n_labels"] == 30


def test_never_recommends_below_a_safety_minimum():
    labels = [{"overall": 0.1, "approved": True}] * 25    # operator approved junk -> don't drop the floor to 0
    rec = recommend_floor(labels, min_labels=20, floor_min=0.50)
    assert rec["floor"] >= 0.50
```

- [ ] **Step 2: Implement `shared/calibration/anchor.py`**

```python
PROVISIONAL = 0.70                # the ADR 0005/0016 provisional floor, held until data earns a change


def _metrics_at(labels, thr):
    keep = [l for l in labels if l["overall"] >= thr]
    tp = sum(1 for l in keep if l["approved"])
    fp = len(keep) - tp
    fn = sum(1 for l in labels if l["overall"] < thr and l["approved"])
    keep_precision = tp / len(keep) if keep else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * keep_precision * recall / (keep_precision + recall)
          if (keep_precision + recall) else 0.0)
    return keep_precision, recall, f1


def recommend_floor(labels: list[dict], *, min_labels: int = 20, min_keep_precision: float = 0.85,
                    floor_min: float = 0.50, floor_max: float = 0.90) -> dict:
    """ADR 0016 D2: choose the floor that MAXIMIZES F1 subject to keep-precision >= the constraint
    (we'd rather hold a good video than post a bad one). Below min_labels -> keep PROVISIONAL. The
    result is a RECOMMENDATION + report; an operator promotes it to the live config (never silent)."""
    if len(labels) < min_labels:
        return {"floor": PROVISIONAL, "reason": "insufficient_labels", "n_labels": len(labels)}
    best = None
    thr = floor_min
    while thr <= floor_max + 1e-9:
        kp, recall, f1 = _metrics_at(labels, round(thr, 3))
        if kp >= min_keep_precision and (best is None or f1 > best["f1"]):
            best = {"floor": round(thr, 3), "f1": round(f1, 3), "keep_precision": round(kp, 3),
                    "recall": round(recall, 3)}
        thr += 0.01
    if best is None:                                  # constraint unmet anywhere -> stay safe-high
        return {"floor": floor_max, "reason": "precision_constraint_unmet", "n_labels": len(labels)}
    return {**best, "reason": "data_anchored", "n_labels": len(labels)}
```

- [ ] **Step 3: Implement `shorts/calibrate.py`** (`make calibrate`) — read every `feature_record.json` with a `ramp_label` across `history/` + recent runs, build `labels`, call `recommend_floor`, print the report + write `runs/.metrics/floor_recommendation.json`. It **does not** edit the live floor; it prints the diff vs the current config and the promote instruction.
- [ ] **Step 4: Wire `make calibrate`** → `uv run python -m shorts.calibrate`. **Run** the unit tests → PASS (3). **Commit.**

```bash
git add shared/calibration/ shorts/calibrate.py Makefile tests/test_calibration_anchor.py
git commit -m "feat(m6): re-anchor the 05c floor from ramp labels (F1 w/ keep-precision constraint, ADR 0016 D2)"
```

### Task 10: The weekly spot-audit report

**Files:** Create `shared/audit/__init__.py` (empty), `shared/audit/report.py`, `shorts/audit.py`; Modify `Makefile`; Test `tests/test_audit_report.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audit_report.py
from shared.audit.report import build_report


def test_report_summarizes_posts_quarantines_and_label_drift():
    posts = [{"video_id": "a", "platform": "youtube", "url": "u1"},
             {"video_id": "b", "platform": "tiktok", "url": "u2"}]
    quarantines = [{"video_id": "c", "failed_checks": ["prohibited_claims"]},
                   {"video_id": "d", "failed_checks": ["loudness", "black_run"]}]
    feature_records = [{"video_id": "a", "creative_qc": 0.82, "ramp_label": {"approved": True}},
                       {"video_id": "e", "creative_qc": 0.55, "ramp_label": {"approved": True}}]
    r = build_report(posts=posts, quarantines=quarantines, feature_records=feature_records)
    assert r["posted_count"] == 2 and r["quarantined_count"] == 2
    assert r["quarantine_reasons"]["prohibited_claims"] == 1 and r["quarantine_reasons"]["loudness"] == 1
    # label drift: the gate would have HELD 'e' (0.55 < 0.70) but the human APPROVED it -> flagged
    assert any(d["video_id"] == "e" for d in r["label_score_disagreement"])
```

- [ ] **Step 2: Implement `shared/audit/report.py`**

```python
from collections import Counter


def build_report(*, posts: list[dict], quarantines: list[dict], feature_records: list[dict],
                 floor: float = 0.70) -> dict:
    """The DoD clause-2 spot-audit view (read-only). Surfaces the week's posts, why videos were
    quarantined (by check), and where the human label disagreed with what the floor would have done
    — the signal that the floor needs re-anchoring (Task 9)."""
    reasons = Counter(c for q in quarantines for c in q.get("failed_checks", []))
    disagree = [{"video_id": fr["video_id"], "score": fr["creative_qc"],
                 "human_approved": fr["ramp_label"]["approved"]}
                for fr in feature_records if "ramp_label" in fr
                and (fr["creative_qc"] >= floor) != fr["ramp_label"]["approved"]]
    return {"posted_count": len(posts), "quarantined_count": len(quarantines),
            "posts": posts, "quarantine_reasons": dict(reasons),
            "label_score_disagreement": disagree}
```

- [ ] **Step 3: Implement `shorts/audit.py`** (`make audit`) — gather the trailing-7-day `posts.jsonl` records, the `quarantine/` `qc.json` failures, and the labeled `feature_record`s; call `build_report`; render a readable summary (counts, the post URLs to eyeball, the top quarantine reasons, the disagreement list) to stdout + `runs/.metrics/audit_<date>.json`.
- [ ] **Step 4: Wire `make audit`** → `uv run python -m shorts.audit`. **Run** → PASS. **Commit.**

```bash
git add shared/audit/ shorts/audit.py Makefile tests/test_audit_report.py
git commit -m "feat(m6): the weekly spot-audit report (posts/quarantines/label drift, DoD clause 2)"
```

---

# Part E — Stability hardening + the soak harness + the unattended-run gate

### Task 11: The offline soak harness (the CI-able stability proxy)

Prove the *mechanics* that must survive two weeks — without a GPU, network, or two weeks — by running N offline batches against a simulated clock and asserting nothing wedges.

**Files:** Create `tests/test_soak_offline.py`; Modify `Makefile` (`soak`)

- [ ] **Step 1: Write the failing test** (the M4 conductor over the fake backend, N iterations)

```python
# tests/test_soak_offline.py
import pytest
from tests.helpers.soak import run_offline_soak


@pytest.mark.integration   # heavier; runs under `make soak`, not the default CI sweep
def test_soak_survives_n_batches_without_wedging(tmp_path):
    result = run_offline_soak(data_root=tmp_path, batches=14, seed=1,
                              inject={"kill_mid_batch_on": 3, "stale_lock_on": 5, "disk_low_on": 8})
    assert result["wedges"] == 0                       # never stuck; lock always recovered
    assert result["silent_failures"] == 0              # every failure is logged + classified
    assert result["batch_3_resumed"] is True           # boot reconciler re-ran the killed batch
    assert result["batch_5_took_over_stale_lock"] is True
    assert result["batch_8_halted_with_alert"] is True # disk-low pre-flight halted, not quarantined
    assert result["ledger_monotonic"] is True          # posts/novelty ledgers only grew
    assert result["runs_within_retention"] is True     # GC kept the bound (Task 6)
```

- [ ] **Step 2: Implement `tests/helpers/soak.py`** — drives `batch_flow` (M4) over the fixture backend with a `FakeClock`, injecting the fault scenarios (SIGKILL mid-batch then re-invoke → exercises `resume_plan`; pre-write a stale lock → exercises takeover; force `free_space_gate` low → exercises the systemic halt). It tallies wedges (any batch that neither completes nor cleanly halts), silent failures (a non-`done` video with no logged reason), and checks the GC + ledger invariants after each batch. Reuses the M0 fake harness — no real models.
- [ ] **Step 3: Wire `make soak`** → `N=${N:-14} uv run pytest tests/test_soak_offline.py -m integration -q`. **Run** → PASS. **Commit.**

```bash
git add tests/test_soak_offline.py tests/helpers/soak.py Makefile
git commit -m "test(m6): offline soak harness — lock/reconcile/GC/no-wedge mechanics (ADR 0003)"
```

### Task 12: The unattended-run runbook + the DoD acceptance gate

This is the milestone's terminal gate: the **real ~1–2 week run** on the box, post-ramp, that satisfies Chapter 1. It is an **ops procedure + a recorded acceptance log**, not code — but it is the point of the whole project.

**Files:** Create `deploy/host/soak-runbook.md`

- [ ] **Step 1: Write `deploy/host/soak-runbook.md`** — the procedure:
  1. **Pre-conditions:** `make soak` green; `make obs-up` healthy (Prometheus targets up, Grafana dashboard live, Alertmanager route tested with a synthetic alert); the OAuth app in **Production** (`oauth-production.md`); the ramp gate **lifted** for at least one niche (M5 `gate_active == False` — the human-at-publish phase is *over*, the DoD clause-1 precondition); ≥1 **public** account live (YouTube-led; TikTok audit status recorded).
  2. **Start:** enable the M4 `shorts-batch.timer`; record the start date.
  3. **Daily acceptance log** (the template — one row/day): batch produced? videos posted (count + URLs)? any quarantine (reason)? any alert fired (which)? disk/VRAM/queue nominal? **any manual intervention** (if yes, the clock resets — DoD clause 4 is *unattended*).
  4. **Weekly:** run `make audit`; run `make calibrate` and record the floor recommendation (promote if it has earned it).
  5. **Exit:** ~1–2 weeks of daily batches with **zero manual interventions, clean logs, no silent failures**, gates enforced, real posts landing.
- [ ] **Step 2: Commit.**

```bash
git add deploy/host/soak-runbook.md
git commit -m "docs(m6): the unattended-run runbook + daily acceptance log (the Chapter 1 DoD gate)"
```

---

## M6 Acceptance Checklist (the testable "done" — = the Chapter 1 Definition of Done, made concrete)

- [ ] **Observability:** per-stage duration + heartbeat + batch counters land in Prometheus via the textfile collector; DCGM (GPU/VRAM) + ComfyUI queue-depth scrape; the Grafana dashboard renders; logs are persisted under `DATA_ROOT/.logs/` → Tasks 1–2.
- [ ] **Alerting that distinguishes slow from stuck:** rules fire for host-down, disk>80%, batch-failed, quarantine-spike, and **stage-stuck** (heartbeat/deadline) — but a merely **slow** stage only warns (no 3am false page) → Tasks 3–5.
- [ ] **Lifecycle hygiene:** the post-batch sweep GCs `runs/` (7d/14-batch) + `quarantine/` (30d) + the cache (50 GB LRU) and **never touches `history/` or `models/`**; the full **pre-flight list** (free-space → host-health → OAuth(mode) → YouTube-quota → data-budget) halts the batch with an alert on any systemic failure → Tasks 6–8.
- [ ] **The calibration loop is closed (ADR 0016 D2):** `make calibrate` turns the ramp's approve/reject labels into a **data-anchored floor recommendation** (F1 with a keep-precision ≥0.85 constraint, provisional held until ≥20 labels) — the floor is no longer a guess; `make audit` produces the weekly spot-audit (posts/quarantine-reasons/label drift) for DoD clause 2 → Tasks 9–10.
- [ ] **Stability mechanics proven offline:** `make soak` runs 14 batches with injected kills/stale-locks/disk-low and asserts **zero wedges, zero silent failures**, reconcile-after-kill, stale-lock takeover, systemic-halt-not-quarantine, monotonic ledgers, GC within bounds → Task 11.
- [ ] **DoD clause 1 — unattended:** the scheduled timer produces a daily batch **post-ramp** (gate lifted), the 05b safety gate is the durable human replacement, a failed stage retries/quarantines/halts rather than wedging → Task 12 + M4/M5.
- [ ] **DoD clause 2 — quality owned + enforced:** every posted video passed **05b AND 05c**; the weekly spot-audit confirms a human would call them "genuinely good, not slop," incl. the original-insight criterion → Tasks 9–10 + M3/M5.
- [ ] **DoD clause 3 — real posting:** videos upload through the **real** YouTube Data API v3 + TikTok Content Posting API to **live, new accounts**, private-first with **≥1 public** (YouTube-led) → M5 + Task 12.
- [ ] **DoD clause 4 — stability:** **~1–2 weeks** of daily batches with **no manual intervention**, clean logs, provenance intact, no silent failures, recorded in the daily acceptance log → Task 12.

---

## Self-Review

**Spec coverage (Ch.10 M6 row + Ch.8 + the Ch.1 DoD):** hardening + **alerts/GC/credential pre-flight wired** → A/B/C (the observability backend ADR 0003 D7, the alert set + slow-vs-stuck, the retention/GC + cache + the wired pre-flight list ADR 0003 D2/D8); the **1–2 week unattended run** that satisfies the DoD → E (the soak proxy + the on-box runbook/acceptance gate). The M6 row's "credential pre-flight wired" is Task 8 (the M5 gates wired into `run_batch` + the new budget gate). The **05c floor re-anchoring** (ADR 0016 D2, explicitly an M6 item — "re-anchored from the labels") → D, closing open #10's floor-values question with a stated method, not a guess. The **weekly spot-audit** (Ch.2 mode + DoD clause 2) → Task 10. Open #11 (cache substrate file-vs-sqlite + eviction; feature-record location) is resolved in the decisions header + Task 7. Open #3's residual numeric tuning (alert thresholds, GC retention, budgets) is pinned as config here.

**Placeholder scan:** no "TBD"/"add error handling". The integration seams (the exporter/Prometheus/Alertmanager/Grafana deployment, the real `_build_backends` model wiring completed in Task 8, the `make audit`/`calibrate` filesystem scans, the soak helper's process-kill injection) are documented ops/integration steps whose pure logic — metrics rendering, the slow/stuck classifier, spike detection, the GC + LRU policies, the budget gate, the floor-recommendation math, the report builder — is fully implemented + unit-tested. The real run is honestly the on-box gate (Task 12), not a CI assertion; `make soak` is named as a *proxy*, not a substitute.

**Type consistency vs M0–M5:** reuses the M1 `StageTimer`/`timing.jsonl` (Tasks 1/3), the M4 `batch_flow`/`execute_batch`/`resume_plan`/lock/`backup()` and the M4–M5 pre-flight framework + `PreflightFailure` (Tasks 8/11), the M5 `feature_record.ramp_label` + `creative_qc.overall` (Task 9) and `posts.jsonl`/`qc.json` (Task 10), and the M0 fake-backend harness (Task 11). No schema changes are required (M6 reads existing artifacts and writes ops-side files); the metrics are emitted out-of-band as `.prom` text, not a new stage output. `make {obs-up,audit,calibrate,soak}` join the existing Makefile target convention.

**Scope:** five parts, one terminal gate (the DoD). A–D are independent and CI-testable; E depends on all of them plus M5's lifted ramp. This is the last milestone before the PoC's stated done — after it, M7 (the optional k8s profile) is the only remaining plan. The deliverable is not more software for its own sake: it is the *evidence* — green soak, live dashboards, a quiet pager, and two weeks of clean daily batches — that the produce-and-post loop runs reliably, unattended, at a quality bar we are not embarrassed by.
