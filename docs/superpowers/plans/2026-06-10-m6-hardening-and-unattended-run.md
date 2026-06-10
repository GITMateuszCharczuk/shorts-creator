# M6 — Hardening, Observability, the Calibration Loop + the Unattended Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pipeline *survive two weeks alone*, then prove it does. Stand up the **observability backend** (Prometheus + node-exporter + **nvidia-smi GPU metrics** + ComfyUI-queue + per-stage duration/heartbeat, ADR 0003 D7), the **alerting** (host-down / disk>80% / batch-failed / quarantine-spike / stage-stuck / gpu-unhealthy) with a **slow-vs-stuck** classifier, the **retention/GC** sweep + **cache eviction** (ADR 0003 D8 / 0010), and **wire the M5 credential + quota pre-flight** into the actual run flow. Close the one analytical loop the design has been deferring: **re-anchor the 05c quality floor per niche from the ramp's approve/reject labels** (ADR 0016 D2) and ship the **weekly spot-audit**. Then run the **~1–2 week unattended batch** that satisfies the Chapter 1 Definition of Done — with an offline **soak harness** as the proxy for the stability mechanics.

**Architecture:** No new stages — M6 hardens the M4 conductor + the M5 gates and adds **out-of-band tooling** (CLIs + ops config). All *logic* is pure and CI-tested behind thin modules: metrics rendering (`shared/obs/`), the GC + cache policies (`shared/ops/`), the floor calibration math (`shared/calibration/`), the audit report (`shared/audit/`). The deployment surface (Prometheus/Alertmanager/Grafana/exporters) is **data files under `deploy/obs/`**. The unattended run is driven by the existing M4 `systemd` timer; M6 adds the **post-batch GC + metrics emission** and the **full pre-flight list** to the M4 `shorts/run_batch.py`. **Metrics emission never touches the pure M4 `execute_batch`** — it is an **injected `run_stage` wrapper** in `run_batch.py` (so `execute_batch` stays the pure, injectable function M4 tested). CI stays GPU-free and network-free; the real run is the on-box gate.

**Tech Stack:** Python 3.12 + the M0–M5 toolchain (no new runtime deps for the pure layer); Prometheus + node-exporter + Alertmanager + Grafana (host services, by config). **GPU metrics come from an `nvidia-smi` polling script → the node-exporter textfile collector** — **NOT DCGM-exporter, which does not work under WSL2** (DCGM needs NVML/fabric features the WSL2 GPU paravirtualization layer doesn't expose; ADR 0013). The whole metrics path is the **textfile collector** (a dir of `*.prom` files) so the conductor needs no metrics server. CI runs only pure/fake tests (`-m "not integration"`); `make soak` runs the offline DAG repeatedly with fakes (`-m soak`).

**Decisions made here (spec/ADRs left open; pinned for M6 — resolving open-items #3/#10/#11):**
- **GPU metrics via `nvidia-smi`, not DCGM (ADR 0013 reality):** a ~30-line poller writes `nvidia_gpu_util` / `nvidia_gpu_mem_free_mib` / `nvidia_gpu_mem_total_mib` to a `.prom` file every 15 s. **XID hardware-error detection is lost** under WSL2 (the paravirt layer doesn't surface it) — recorded honestly; the GPU alert is a **VRAM-free floor**, not XID.
- **The heartbeat model is explicit (resolves the subprocess-liveness gap):** the M4 per-stage subprocess (`shorts/stage.py`) starts a **daemon thread that rewrites `runs/<batch>/<video>/.heartbeat/<stage>.json` (a timestamp) every 30 s** while the stage runs; the conductor's metered wrapper reads its age. A **`shorts_stage_running{...}` gauge** (1 in-flight, 0 done) is emitted alongside the heartbeat so the `StageStuck` alert is gated `running == 1 AND now - heartbeat > heartbeat_timeout` — no false page on a completed stage's stale `.prom`. Emission is the injected wrapper's job, leaving `execute_batch` pure.
- **05c floor re-anchoring is PER NICHE (ADR 0016 D2; open #10):** `recommend_floor` takes a single niche's labels; `shorts/calibrate.py` **groups `feature_record`s by `niche`** and emits one `floor_recommendation.<niche>.json`. Method: pick the floor that **maximizes F1 against the human labels with keep-precision ≥ 0.85** (we'd rather hold a good video than post a bad one). A **`min_labels = 30` guard** holds the **provisional 0.70** until enough labels exist, and the report carries a **`low_confidence` flag when `n < 50`** (a 1–2 week ramp yields few labels — the recommendation is *directional*, promoted by an operator, never auto-applied). The 00b best-of-N floor is **out of M6 scope** (stays at its M3 provisional value; noted).
- **The `quality.floor` config block is defined here (the M0 living-contracts rule):** `make audit`/`make calibrate` read `config["quality"]["floor"][<niche>]` (a `number` per niche, default **0.70**), so M6 adds a **`quality` section to the config schema** at the **global layer with per-niche override** (the ADR 0010 D5 precedence) and updates the M0 config fixture. The live floor is what 05c enforces and what the audit's drift check compares against.
- **Honest DoD timeline — the unattended run is wall-clock-gated, not code-gated:** the DoD (clause 1) is satisfied *after the ramp ends*, and the ramp + warming + the TikTok audit are **calendar** dependencies, not software. Realistically: M5 deploy + provisioning/**warming** (~7 days) → the **ramp track-record** (gate-lift ≥10 approvals/≥7 days; cadence-widen ≥20/≥14 days) → the **~1–2 week unattended soak**. So the DoD cannot be *demonstrated* until **roughly 5–7 weeks after M5 ships on a real box**, independent of code quality. The runbook (Task 13) makes this the headline expectation; "M6 code-complete" ≠ "DoD met."
- **The 05c floor is provisional for the PoC run (named, not hidden):** at ~1 video/day/niche, a 1–2 week ramp yields ~7–14 labels/niche — below `min_labels=30`. So the floor 05c enforces **during the DoD soak is the provisional 0.70, operator-confirmed, not empirically anchored**. The calibration *machinery* ships and runs (flagging `low_confidence`); a genuinely data-anchored floor is a **post-PoC** outcome. This is a spec-window tension (DoD clause 2), surfaced in the runbook + the calibration report, not papered over.
- **The TikTok public audit has a named owner + tracking (DoD clause 3):** the "≥1 public per platform" clause leans on YouTube (immediate post-warming); **TikTok public is external-audit-gated** and may not land in the PoC (the spec's own caveat). M6 adds an explicit ops task: **submit the TikTok app for review at M5 go-live, track its state in the runbook, and flip `tiktok.audit_cleared` when it clears** — so the dependency has an owner and a tracking mechanism instead of being implicit (it is *not* a code gate the arc can force).
- **Slow-vs-stuck (ADR 0003 D7; the 3am-stall):** per-stage baselines = **`p95` (nearest-rank, `ceil(0.95·n)−1`)** of the trailing `timing.jsonl` window (M1's `StageTimer`). **slow** = `elapsed > p95 × slow_factor` (1.5) and still progressing; **stuck** = `elapsed > hard_deadline` (the M4 timeout) **or** heartbeat age > `heartbeat_timeout` (180 s) while `running == 1`. Slow → warn-severity; stuck → page-severity (the M4 timeout already kills it). All knobs config.
- **Alert severity + inhibition:** rules carry a `severity` label — **page** (host-down, disk>80%, batch-failed, stage-stuck, gpu-vram) vs **warn** (stage-slow, quarantine-approaching). `warn` routes to a quieter channel/longer interval; an **inhibit rule suppresses `StageSlow` while `StageStuck` fires for the same stage**. No alert-fatigue from a slow FLUX run.
- **Quarantine-rate spike:** the conductor emits both `shorts_quarantine_rate` and `shorts_quarantine_baseline` (per niche, labelled); the alert fires on **`rate > 0.30 OR rate > 2 × baseline`** — the *same* two-part condition as the in-code `is_spike` (no silent divergence between the Python edge-detector and the Prometheus rule).
- **Retention/GC (ADR 0003 D8):** keep `runs/<batch>/` for **last 7 days OR last 14 batches** (larger), `quarantine/` **30 days**, the cache under a **50 GB LRU-by-atime** cap. **`history/*.jsonl` + `models/` are NEVER GC'd.** GC **never deletes the active or just-resumed batch** — `runs_to_delete` takes `protected_ids` (the current + any reconciler-resumed batch IDs) and excludes them regardless of age. All numbers config; the sweep runs after `backup()`.
- **Cache substrate (open #11):** file-based under `DATA_ROOT/.cache/<stage>/<input_hash>-<seed>/` (no sqlite — simplest, ADR 0010); eviction is the GC's LRU pass. The feature record stays a **per-video JSON artifact**; `shorts/calibrate.py` also appends each labelled record to **`history/feature_index.jsonl`** — the durable accumulation substrate the deferred analytics loop (ADR 0002/0005) will consume.
- **Per-API budgets (open #10):** daily budgets in config (`budgets.youtube_units: 10000`, `budgets.alpha_vantage_calls: 25`); the M5 `youtube_quota_gate` reads them; **FRED/stooq keyless/free**; **Alpha Vantage quotes-only, low cap** (ADR 0009 #8). The data-API budget gate joins the pre-flight list.
- **The pre-flight list is wired, in order:** `free_space_gate` → `host_health_gate` → `oauth_token_age_gate(mode)` → `youtube_quota_gate` → `data_api_budget_gate`, all reading the resolved config; any failure **halts the batch with an alert** (ADR 0003 D2/D8), never a per-video quarantine. The wiring lives in **`shorts/run_batch.py`** (the M4 module).
- **All numeric knobs are config-loaded at the call site:** every threshold (`slow_factor`, `heartbeat_timeout`, GC `keep_days`/`keep_count`, `cap_gb`, spike `abs_floor`/`mult`, `min_labels`) is a parameter the production wiring passes from `ctx.config["obs"|"gc"|"ramp"]` — the function defaults are documentation, not the override path.
- **Durable tool output:** `make calibrate`/`make audit` write under **`DATA_ROOT/.metrics/`** (the textfile-collector sibling, outside GC scope) and `history/` — never `runs/` (which GC reclaims).
- **The soak harness drives the REAL `batch_flow`:** `make soak N=14` calls the M4 `batch_flow` (the function `test_run_batch_flow` covers) with **injected collaborators + a `FakeClock`**, asserting the *stability mechanics* (lock takeover, reconcile-after-kill, GC bounds, ledger monotonicity, zero wedges, zero silent failures). It is **not** a re-implementation of the flow. The **real ~1–2 week on-box run** (the DoD gate) is the runbook; soak green is necessary, not sufficient.
- **The weekly spot-audit (DoD clause 2):** `make audit` reports the week's posts (URLs), quarantine reasons by check, the `creative_qc` score distribution, and **label↔score agreement drift vs the LIVE floor** — read-only.

---

## File Structure

```
shared/obs/                                 # NEW: observability (pure rendering + classification)
  __init__.py
  metrics.py                                # render per-stage + per-batch Prometheus .prom text (textfile collector)
  baselines.py                              # p95 (nearest-rank) baselines + slow/stuck classifier (gated by running)
  quarantine_rate.py                        # trailing rate + baseline + is_spike (matches the alert rule)
shared/ops/
  __init__.py
  gc.py                                     # retention sweep w/ protected_ids (never history/models/active batch)
  cache_evict.py                            # content-addressed cache LRU eviction by size cap (open #11)
  budgets.py                                # data_api_budget_gate (open #10)
shared/calibration/
  __init__.py
  anchor.py                                 # PER-NICHE recommend_floor: labels -> floor + report (+ low_confidence)
shared/audit/
  __init__.py
  report.py                                 # weekly spot-audit assembly (read-only; live floor injected)
shorts/stage.py                             # MODIFY: heartbeat daemon thread (.heartbeat/<stage>.json every 30s)
shorts/run_batch.py                         # MODIFY (the M4 module): build_preflight + metered run_stage wrapper + post-batch GC
shared/conductor/preflight.py               # MODIFY: data_api_budget_gate joins the framework
shared/conductor/reconcile.py               # (M5 already re-queues 'held'); M6 surfaces resumed id to GC
shorts/audit.py                             # NEW: python -m shorts.audit (make audit): the weekly report
shorts/calibrate.py                         # NEW: python -m shorts.calibrate (make calibrate): per-niche floor recs
deploy/obs/
  prometheus.yml                            # scrape: node-exporter (+ textfile), nvidia-smi .prom, comfyui-queue
  alerts.yml                                # host-down/disk/batch-failed/quarantine-spike/stage-stuck/stage-slow/gpu-vram (+ severity)
  alertmanager.yml                          # page vs warn routes + the StageSlow<-StageStuck inhibit rule
  grafana-dashboard.json                    # per-stage duration + GPU util/VRAM (nvidia-smi) + ComfyUI queue
  nvidia-smi-exporter.md                    # the ~30-line GPU poller -> textfile collector (replaces DCGM)
  comfyui-queue-exporter.md                 # the queue-depth poller -> textfile collector
deploy/host/
  soak-runbook.md                           # the ~1-2 week run procedure + the daily acceptance-log template
Makefile                                    # add audit / calibrate / soak / obs-up / obs-lint targets
tests/
  test_metrics.py  test_baselines.py  test_quarantine_rate.py
  test_gc.py  test_cache_evict.py  test_budgets.py
  test_calibration_anchor.py  test_audit_report.py
  test_preflight_wiring.py  test_heartbeat.py  test_soak_offline.py
```

**Responsibility split:** `shared/obs/` renders/classifies (pure); `shared/ops/` decides what to delete (pure); `shared/calibration/` turns labels into a per-niche threshold recommendation; `shared/audit/` is the human view; `deploy/obs/` is the stack as config. Conductor changes are the additive seams M4/M5 left (`shorts/run_batch.py` wiring, `shorts/stage.py` heartbeat). No stage-logic, schema, planner, or gate changes.

---

# Part A — Observability backend

### Task 1: Per-stage AND per-batch metrics rendering (+ the `running` gauge)

**Files:** Create `shared/obs/__init__.py` (empty), `shared/obs/metrics.py`; Test `tests/test_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_metrics.py
from shared.obs.metrics import render_stage_metrics, render_batch_metrics, write_metrics


def test_stage_metrics_carry_running_gauge_and_heartbeat():
    text = render_stage_metrics(batch_id="b1", stage="05b", video_id="v1", duration_s=12.5,
                                status="done", running=0, heartbeat_ts=1718000000)
    assert 'shorts_stage_duration_seconds{batch="b1",stage="05b",video="v1"} 12.5' in text
    assert 'shorts_stage_running{batch="b1",stage="05b",video="v1"} 0' in text
    assert "shorts_stage_heartbeat_timestamp" in text and "1718000000" in text


def test_batch_metrics_emit_the_series_the_alerts_read():
    text = render_batch_metrics(batch_id="b1", niche="finance", videos_total=4, quarantined=1,
                                failed=0, quarantine_rate=0.25, quarantine_baseline=0.10)
    assert 'shorts_batch_videos_total{batch="b1",niche="finance"} 4' in text
    assert 'shorts_batch_failed_total{batch="b1",niche="finance"} 0' in text
    assert 'shorts_quarantine_rate{batch="b1",niche="finance"} 0.25' in text
    assert 'shorts_quarantine_baseline{batch="b1",niche="finance"} 0.1' in text


def test_write_is_atomic(tmp_path):
    out = tmp_path / "m.prom"
    write_metrics(out, "shorts_test 1\n")
    assert out.read_text() == "shorts_test 1\n" and not list(tmp_path.glob("*.tmp"))
```

- [ ] **Step 2: Implement `shared/obs/metrics.py`**

```python
import os
from pathlib import Path


def render_stage_metrics(*, batch_id, stage, video_id, duration_s, status, running, heartbeat_ts) -> str:
    lbl = f'batch="{batch_id}",stage="{stage}",video="{video_id}"'
    return (f"shorts_stage_duration_seconds{{{lbl}}} {duration_s}\n"
            f'shorts_stage_status{{{lbl},status="{status}"}} 1\n'
            f"shorts_stage_running{{{lbl}}} {running}\n"
            f"shorts_stage_heartbeat_timestamp{{{lbl}}} {heartbeat_ts}\n")


def render_batch_metrics(*, batch_id, niche, videos_total, quarantined, failed,
                         quarantine_rate, quarantine_baseline) -> str:
    lbl = f'batch="{batch_id}",niche="{niche}"'
    return (f"shorts_batch_videos_total{{{lbl}}} {videos_total}\n"
            f"shorts_batch_quarantined_total{{{lbl}}} {quarantined}\n"
            f"shorts_batch_failed_total{{{lbl}}} {failed}\n"
            f"shorts_quarantine_rate{{{lbl}}} {quarantine_rate}\n"
            f"shorts_quarantine_baseline{{{lbl}}} {quarantine_baseline}\n")


def write_metrics(path: Path, text: str) -> None:
    """Atomic write into the node-exporter textfile-collector dir (temp+rename so a scrape never
    reads a half-written file, ADR 0003 D7)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"{path}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
```

- [ ] **Step 3: Wire emission via an INJECTED wrapper in `shorts/run_batch.py` (keeping `execute_batch` pure).** The M4 `execute_batch` takes `run_stage` as a parameter; M6 wraps it:

```python
def metered(run_stage, *, batch_id, niche, textfile_dir):
    def wrapped(video_id, stage_id):
        out = run_stage(video_id, stage_id)          # the M4 run_stage_subprocess+retries
        write_metrics(textfile_dir / f"{video_id}-{stage_id}.prom",
                      render_stage_metrics(batch_id=batch_id, stage=stage_id, video_id=video_id,
                                           duration_s=out.elapsed_s, status=out.status, running=0,
                                           heartbeat_ts=int(time.time())))
        return out
    return wrapped
```

`execute_batch(batch, stage_order=..., run_stage=metered(real_run_stage, ...))`. Batch-level metrics (`render_batch_metrics`) are emitted at the fan-in step using the M4 outcome tally + `quarantine_rate.trailing_rate`. **No change to `execute_batch`'s signature or purity.**
- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/obs/__init__.py shared/obs/metrics.py tests/test_metrics.py
git commit -m "feat(m6): per-stage + per-batch Prometheus metrics via the textfile collector (ADR 0003 D7)"
```

### Task 2: The heartbeat daemon in the stage subprocess

The conductor can't observe a running subprocess's liveness; the subprocess must publish it.

**Files:** Modify `shorts/stage.py`; Test `tests/test_heartbeat.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_heartbeat.py
import time
from shorts.stage import Heartbeat


def test_heartbeat_file_advances_while_running(tmp_path):
    hb = Heartbeat(tmp_path / ".heartbeat" / "05.json", interval_s=0.05)
    hb.start()
    time.sleep(0.16)
    first = hb.read_ts()
    time.sleep(0.16)
    assert hb.read_ts() > first        # advancing while the stage runs
    hb.stop()
    stopped = hb.read_ts()
    time.sleep(0.16)
    assert hb.read_ts() == stopped     # frozen after stop (the conductor sees the age grow -> stuck)
```

- [ ] **Step 2: Implement `Heartbeat` in `shorts/stage.py`** — a daemon thread that rewrites `<run_dir>/.heartbeat/<stage>.json` (`{"ts": <epoch>}`) every `interval_s` (default 30) until `stop()`. `main()` starts it before `reg.fn(ctx)` and stops it in a `finally`. The conductor's monitor reads `now - ts` as `last_heartbeat_age_s`; a crashed subprocess stops advancing it → the file ages → `classify` returns `stuck` (which the M4 timeout independently enforces).
- [ ] **Step 3: Run** → PASS. **Commit.**

```bash
git add shorts/stage.py tests/test_heartbeat.py
git commit -m "feat(m6): stage heartbeat daemon — subprocess liveness for the stuck detector (ADR 0003 D7)"
```

### Task 3: The monitoring stack as config (Prometheus + nvidia-smi + queue + Grafana)

**Files:** Create `deploy/obs/prometheus.yml`, `deploy/obs/nvidia-smi-exporter.md`, `deploy/obs/comfyui-queue-exporter.md`, `deploy/obs/grafana-dashboard.json`; Modify `Makefile` (`obs-up`, `obs-lint`)

- [ ] **Step 1: `prometheus.yml`** — scrape **node-exporter** (host + `--collector.textfile.directory=DATA_ROOT/.metrics/textfile`) only; **all custom series (stage/batch/GPU/queue) arrive via the textfile collector**, so there is one scrape target. `rule_files: [alerts.yml]`, 15 s interval.
- [ ] **Step 2: `nvidia-smi-exporter.md`** — the ~30-line poller (replaces DCGM, which is dead under WSL2): `nvidia-smi --query-gpu=utilization.gpu,memory.free,memory.total --format=csv,noheader,nounits` every 15 s → `nvidia_gpu_util` / `nvidia_gpu_mem_free_mib` / `nvidia_gpu_mem_total_mib` in a `.prom` file in the textfile dir. Note explicitly: **XID hardware-error detection is unavailable under WSL2**; the GPU alert is a VRAM-free floor.
- [ ] **Step 3: `comfyui-queue-exporter.md`** — the queue poller (`:8188/queue` length → `comfyui_queue_depth` `.prom`); the GPU-plane backpressure signal.
- [ ] **Step 4: `grafana-dashboard.json`** — panels: per-stage `p50/p95` duration, GPU util + VRAM free (nvidia-smi series), ComfyUI queue depth, batch done/quarantined/held, disk free %.
- [ ] **Step 5: `make obs-up`** (start node-exporter w/ textfile dir, the two pollers, Prometheus, Alertmanager, Grafana — idempotent, health-gated; persisted logs to `DATA_ROOT/.logs/`) and **`make obs-lint`** → `promtool check config deploy/obs/prometheus.yml && promtool check rules deploy/obs/alerts.yml && amtool check-config deploy/obs/alertmanager.yml` (a **CI-runnable** gate; no cluster needed). **Commit.**

```bash
git add deploy/obs/prometheus.yml deploy/obs/nvidia-smi-exporter.md deploy/obs/comfyui-queue-exporter.md deploy/obs/grafana-dashboard.json Makefile
git commit -m "feat(m6): monitoring stack as config — nvidia-smi (not DCGM, WSL2) + queue + Grafana + obs-lint (ADR 0003 D7/0013)"
```

---

# Part B — Alerting + slow-vs-stuck

### Task 4: Baselines (nearest-rank p95) + the slow/stuck classifier

**Files:** Create `shared/obs/baselines.py`; Test `tests/test_baselines.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_baselines.py
from shared.obs.baselines import stage_baselines, classify


def test_nearest_rank_p95_is_exact():
    timings = [{"stage": "05", "elapsed_s": s} for s in (100, 110, 120, 130, 900)]
    assert stage_baselines(timings)["05"] == 900        # nearest-rank p95 of 5 = the top sample


def test_classify_running_slow_vs_stuck_only_when_running():
    base = {"05": 120.0}
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600, last_heartbeat_age_s=5, running=1) == "ok"
    assert classify("05", elapsed_s=250, base=base, hard_deadline_s=600, last_heartbeat_age_s=5, running=1) == "slow"
    assert classify("05", elapsed_s=700, base=base, hard_deadline_s=600, last_heartbeat_age_s=5, running=1) == "stuck"
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600, last_heartbeat_age_s=300, running=1) == "stuck"
    # a COMPLETED stage (running=0) is never slow/stuck regardless of a stale heartbeat file
    assert classify("05", elapsed_s=100, base=base, hard_deadline_s=600, last_heartbeat_age_s=99999, running=0) == "ok"


def test_unknown_stage_never_falsely_slow():
    assert classify("99", elapsed_s=10, base={}, hard_deadline_s=600, last_heartbeat_age_s=1, running=1) == "ok"
```

- [ ] **Step 2: Implement `shared/obs/baselines.py`**

```python
import math
from collections import defaultdict


def _p95(xs: list[float]) -> float:
    s = sorted(xs)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)] if s else 0.0   # nearest-rank


def stage_baselines(timings: list[dict]) -> dict[str, float]:
    by: dict[str, list[float]] = defaultdict(list)
    for t in timings:
        by[t["stage"]].append(t["elapsed_s"])
    return {stage: _p95(v) for stage, v in by.items()}


def classify(stage: str, *, elapsed_s: float, base: dict[str, float], hard_deadline_s: float,
             last_heartbeat_age_s: float, running: int, slow_factor: float = 1.5,
             heartbeat_timeout_s: float = 180.0) -> str:
    """ok | slow | stuck. Only a RUNNING stage can be slow/stuck — a completed stage's stale .prom
    never false-pages. STUCK = past the hard deadline OR a dead heartbeat. SLOW (warn) = past
    p95*slow_factor. Unknown stage (no baseline) can only be stuck via deadline/heartbeat."""
    if running != 1:
        return "ok"
    if elapsed_s > hard_deadline_s or last_heartbeat_age_s > heartbeat_timeout_s:
        return "stuck"
    b = base.get(stage)
    return "slow" if (b and elapsed_s > b * slow_factor) else "ok"
```

- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/obs/baselines.py tests/test_baselines.py
git commit -m "feat(m6): nearest-rank p95 baselines + running-gated slow/stuck classifier (ADR 0003 D7)"
```

### Task 5: Quarantine-rate spike (rate + baseline, matching the alert)

**Files:** Create `shared/obs/quarantine_rate.py`; Test `tests/test_quarantine_rate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quarantine_rate.py
from shared.obs.quarantine_rate import trailing_rate, is_spike


def test_trailing_rate_over_window():
    assert abs(trailing_rate(["done"] * 16 + ["quarantined"] * 4, window=20) - 0.20) < 1e-9


def test_spike_matches_the_alert_two_part_condition():
    assert is_spike(rate=0.35, baseline=0.30, abs_floor=0.30, mult=2.0) is True   # absolute path
    assert is_spike(rate=0.25, baseline=0.10, abs_floor=0.30, mult=2.0) is True   # 2x baseline path
    assert is_spike(rate=0.12, baseline=0.10, abs_floor=0.30, mult=2.0) is False
```

- [ ] **Step 2: Implement `shared/obs/quarantine_rate.py`**

```python
def trailing_rate(outcomes: list[str], *, window: int = 20) -> float:
    recent = outcomes[-window:]
    return sum(1 for o in recent if o == "quarantined") / len(recent) if recent else 0.0


def is_spike(*, rate: float, baseline: float, abs_floor: float = 0.30, mult: float = 2.0) -> bool:
    """The SAME two-part condition the alert rule uses (no divergence): trip on the absolute floor
    OR a multiple of the trailing baseline."""
    return rate >= abs_floor or rate >= baseline * mult
```

- [ ] **Step 3: Run** → PASS (2). **Commit.**

```bash
git add shared/obs/quarantine_rate.py tests/test_quarantine_rate.py
git commit -m "feat(m6): quarantine-rate spike (rate+baseline, matches the alert rule)"
```

### Task 6: Alert rules (with severity + inhibition) + Alertmanager routes

**Files:** Create `deploy/obs/alerts.yml`, `deploy/obs/alertmanager.yml`

- [ ] **Step 1: `alerts.yml`** — each rule carries a `severity` label:
  - `HostDown` (**page**) — `up{job="node"} == 0` for 2m.
  - `DiskAlmostFull` (**page**) — `node_filesystem_avail / size < 0.20`.
  - `BatchFailed` (**page**) — `increase(shorts_batch_failed_total[1h]) > 0`.
  - `QuarantineSpike` (**warn**) — `shorts_quarantine_rate > 0.30 or shorts_quarantine_rate > 2 * shorts_quarantine_baseline` (the exact `is_spike` condition; per-niche via the labels).
  - `StageStuck` (**page**) — `shorts_stage_running == 1 and time() - shorts_stage_heartbeat_timestamp > 180`.
  - `StageSlow` (**warn**) — the slow condition (the conductor can also emit a `shorts_stage_slow` gauge from `classify`).
  - `GPUVramLow` (**page**) — `nvidia_gpu_mem_free_mib < <diffusion floor>` for 5m (nvidia-smi; **no XID** under WSL2).
- [ ] **Step 2: `alertmanager.yml`** — two routes: **page** (immediate, `repeat_interval: 4h`) and **warn** (quieter channel / longer interval); group by `alertname` + `niche`; an **inhibit_rule** suppressing `StageSlow` when `StageStuck` is firing for the same `stage`.
- [ ] **Step 3: `make obs-lint` covers these** (Task 3). **Commit.**

```bash
git add deploy/obs/alerts.yml deploy/obs/alertmanager.yml
git commit -m "feat(m6): alert rules + severity routes + inhibition (host/disk/batch/quarantine/stuck/slow/gpu-vram)"
```

---

# Part C — Retention/GC, cache, pre-flight wiring

### Task 7: Retention/GC sweep (protected_ids; never history/models/active)

**Files:** Create `shared/ops/__init__.py` (empty), `shared/ops/gc.py`; Test `tests/test_gc.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gc.py
from shared.ops.gc import runs_to_delete, quarantine_to_delete, PROTECTED


def test_keeps_recent_runs_by_count_and_age_and_deletes_the_rest():
    runs = [{"id": f"b{i}", "age_days": i} for i in range(20)]
    deleted = {r["id"] for r in runs_to_delete(runs, keep_days=7, keep_count=14)}
    assert deleted == {f"b{i}" for i in range(14, 20)}        # b14..b19 (old AND beyond newest 14)
    assert "b0" not in deleted and "b13" not in deleted


def test_active_or_resumed_batch_is_never_deleted_regardless_of_age():
    runs = [{"id": "old-resumed", "age_days": 99}, {"id": "b1", "age_days": 99}]
    deleted = {r["id"] for r in runs_to_delete(runs, keep_days=7, keep_count=1,
                                               protected_ids={"old-resumed"})}
    assert "old-resumed" not in deleted                      # the reconciler just re-ran it


def test_quarantine_kept_longer():
    q = [{"id": "q1", "age_days": 10}, {"id": "q2", "age_days": 40}]
    assert [r["id"] for r in quarantine_to_delete(q, keep_days=30)] == ["q2"]


def test_history_and_models_protected():
    assert "history" in PROTECTED and "models" in PROTECTED
```

- [ ] **Step 2: Implement `shared/ops/gc.py`**

```python
PROTECTED = {"history", "models"}        # never GC'd: the only unrecoverable state + the weight cache


def runs_to_delete(runs: list[dict], *, keep_days: int = 7, keep_count: int = 14,
                   protected_ids: set[str] | None = None) -> list[dict]:
    """Delete a run only if older than keep_days AND outside the newest keep_count AND not in
    protected_ids (the current batch + any reconciler-resumed batch — ADR 0003 D9: GC must never
    reclaim a run the boot reconciler just re-ran)."""
    protected = protected_ids or set()
    kept_by_count = {r["id"] for r in sorted(runs, key=lambda r: r["age_days"])[:keep_count]}
    return [r for r in runs if r["age_days"] > keep_days
            and r["id"] not in kept_by_count and r["id"] not in protected]


def quarantine_to_delete(quarantines: list[dict], *, keep_days: int = 30) -> list[dict]:
    return [q for q in quarantines if q["age_days"] > keep_days]
```

- [ ] **Step 3: Run** → PASS (4). **Commit.**

```bash
git add shared/ops/__init__.py shared/ops/gc.py tests/test_gc.py
git commit -m "feat(m6): retention/GC w/ protected_ids — never history/models/active batch (ADR 0003 D8/D9)"
```

### Task 8: Cache LRU eviction by size cap

**Files:** Create `shared/ops/cache_evict.py`; Test `tests/test_cache_evict.py`

- [ ] **Step 1: Write the failing tests** (assert against the SURVIVING set, not the unmutated input)

```python
# tests/test_cache_evict.py
from shared.ops.cache_evict import evict_to_cap


def test_evicts_least_recently_used_until_under_cap():
    entries = [{"key": "a", "size_gb": 30, "atime": 1}, {"key": "b", "size_gb": 30, "atime": 2},
               {"key": "c", "size_gb": 30, "atime": 3}]                  # 90 GB, cap 50
    evicted = evict_to_cap(entries, cap_gb=50)
    survivors = {e["key"] for e in entries} - {e["key"] for e in evicted}
    assert [e["key"] for e in evicted] == ["a", "b"]                     # oldest atime first
    assert survivors == {"c"} and sum(e["size_gb"] for e in entries if e["key"] in survivors) <= 50


def test_under_cap_evicts_nothing():
    assert evict_to_cap([{"key": "a", "size_gb": 10, "atime": 1}], cap_gb=50) == []
```

- [ ] **Step 2: Implement `shared/ops/cache_evict.py`**

```python
def evict_to_cap(entries: list[dict], *, cap_gb: float = 50.0) -> list[dict]:
    """LRU by atime until total <= cap (file-based cache, open #11). Returns entries to delete;
    the caller unlinks their dirs under DATA_ROOT/.cache/."""
    total = sum(e["size_gb"] for e in entries)
    evicted = []
    for e in sorted(entries, key=lambda x: x["atime"]):
        if total <= cap_gb:
            break
        evicted.append(e); total -= e["size_gb"]
    return evicted
```

- [ ] **Step 3: Run** → PASS (2). **Commit.**

```bash
git add shared/ops/cache_evict.py tests/test_cache_evict.py
git commit -m "feat(m6): content-addressed cache LRU eviction by size cap (open #11)"
```

### Task 9: Data-API budget gate + wire the full pre-flight + post-batch GC/metrics (config-driven)

**Files:** Create `shared/ops/budgets.py`; Modify `shared/conductor/preflight.py`, `shorts/run_batch.py`; Test `tests/test_budgets.py`, `tests/test_preflight_wiring.py`

- [ ] **Step 1: Write the failing tests** (incl. a REAL-gate wiring test, not just ordering)

```python
# tests/test_budgets.py
import pytest
from shared.ops.budgets import data_api_budget_gate
from shared.conductor.preflight import PreflightFailure


def test_keyless_sources_never_block():
    data_api_budget_gate(used={}, planned={"fred": 10, "stooq": 10}, budgets={})


def test_capped_source_blocks_over_budget():
    with pytest.raises(PreflightFailure):
        data_api_budget_gate(used={"alpha_vantage": 24}, planned={"alpha_vantage": 5},
                             budgets={"alpha_vantage": 25})
```

```python
# tests/test_preflight_wiring.py
import pytest
from shorts.run_batch import build_preflight                 # the M4 module (shorts/run_batch.py)
from shared.conductor.preflight import oauth_token_age_gate, PreflightFailure


def test_preflight_runs_all_gates_in_order():
    calls = []
    for g in build_preflight(hooks={k: (lambda k=k: calls.append(k)) for k in
                                   ["free_space", "host_health", "oauth", "youtube_quota", "data_budget"]}):
        g()
    assert calls == ["free_space", "host_health", "oauth", "youtube_quota", "data_budget"]


def test_wiring_invokes_the_REAL_oauth_gate_not_a_stub():
    # the seam must call the actual M5 gate with the resolved mode/age, not a no-op
    gates = build_preflight(hooks={"oauth": lambda: oauth_token_age_gate(token_age_days=8.0, mode="testing")})
    with pytest.raises(PreflightFailure):
        for g in gates:
            g()
```

- [ ] **Step 2: Implement `shared/ops/budgets.py`**

```python
from shared.conductor.preflight import PreflightFailure


def data_api_budget_gate(*, used: dict, planned: dict, budgets: dict) -> None:
    """Open #10. A source with no budget entry is keyless/free (FRED/stooq) — never blocks. A
    capped source (Alpha Vantage) fails the batch BEFORE fan-out if it would overrun the day's cap."""
    for src, cap in budgets.items():
        if used.get(src, 0) + planned.get(src, 0) > cap:
            raise PreflightFailure(f"{src} budget: {used.get(src,0)}+{planned.get(src,0)} > {cap}")
```

- [ ] **Step 3: Wire `shorts/run_batch.py`** — add `build_preflight(hooks)` returning the ordered closures `[free_space, host_health, oauth, youtube_quota, data_budget]`, passed to the M4 `batch_flow(preflight=...)`. Production `main()` builds each closure reading the resolved config: `free_space_gate(DATA_ROOT, min_free_gb=cfg["gc"]["min_free_gb"])`, `host_health_gate(...)`, `oauth_token_age_gate(mode=cfg["oauth_mode"], ...)`, `youtube_quota_gate(used, planned_inserts, daily_quota=cfg["budgets"]["youtube_units"])`, `data_api_budget_gate(used, planned, budgets=cfg["budgets"])`. **Post-batch (after `backup()`):** call `runs_to_delete(..., protected_ids={batch_id} | resumed_ids)` / `quarantine_to_delete` / `evict_to_cap` (unlinking returned dirs) with **all knobs from `cfg["gc"]`**, and emit `render_batch_metrics(...)`. The real model-backend wiring (`_build_backends`) is **explicitly deferred to the on-box bring-up runbook** (Task 12) exactly as M4 left it (`raise NotImplementedError` until host bring-up) — M6 adds the **`--dry-run` smoke** as its acceptance (stages metadata, posts nothing).
- [ ] **Step 4: Run** → PASS (4). **Commit.**

```bash
git add shared/ops/budgets.py shared/conductor/preflight.py shorts/run_batch.py tests/test_budgets.py tests/test_preflight_wiring.py
git commit -m "feat(m6): data-API budget gate + config-driven pre-flight wiring + post-batch GC/metrics (ADR 0003 D2/D8/0009 #8/#10)"
```

---

# Part D — The calibration loop + the weekly spot-audit

### Task 10: Per-niche 05c floor re-anchoring (ADR 0016 D2)

**Files:** Create `shared/calibration/__init__.py` (empty), `shared/calibration/anchor.py`, `shorts/calibrate.py`; Modify `Makefile`; Test `tests/test_calibration_anchor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_calibration_anchor.py
from shared.calibration.anchor import recommend_floor, PROVISIONAL


def test_holds_provisional_until_enough_labels():
    rec = recommend_floor([{"overall": 0.8, "approved": True}] * 5, min_labels=30)
    assert rec["floor"] == PROVISIONAL and rec["reason"] == "insufficient_labels"


def test_low_confidence_flag_below_50():
    labels = ([{"overall": o, "approved": True} for o in (0.74, 0.82, 0.95)] +
              [{"overall": o, "approved": False} for o in (0.40, 0.55, 0.69)]) * 6   # 36 labels
    rec = recommend_floor(labels, min_labels=30)
    assert rec["reason"] == "data_anchored" and rec["low_confidence"] is True        # 36 < 50


def test_picks_a_separating_floor_with_keep_precision_constraint():
    labels = ([{"overall": o, "approved": True} for o in (0.74, 0.78, 0.82, 0.9, 0.95)] +
              [{"overall": o, "approved": False} for o in (0.40, 0.52, 0.60, 0.66, 0.69)]) * 6  # 60
    rec = recommend_floor(labels, min_labels=30, min_keep_precision=0.85)
    assert 0.69 < rec["floor"] <= 0.74 and rec["keep_precision"] >= 0.85
    assert rec["low_confidence"] is False and rec["n_labels"] == 60


def test_never_below_a_safety_minimum():
    rec = recommend_floor([{"overall": 0.1, "approved": True}] * 35, min_labels=30, floor_min=0.50)
    assert rec["floor"] >= 0.50
```

- [ ] **Step 2: Implement `shared/calibration/anchor.py`** (per-niche caller groups; this fn sees ONE niche)

```python
PROVISIONAL = 0.70                # the ADR 0016 D2 provisional floor, held until data earns a change


def _metrics_at(labels, thr):
    keep = [l for l in labels if l["overall"] >= thr]
    tp = sum(1 for l in keep if l["approved"])
    fn = sum(1 for l in labels if l["overall"] < thr and l["approved"])
    kp = tp / len(keep) if keep else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * kp * recall / (kp + recall)) if (kp + recall) else 0.0
    return kp, recall, f1


def recommend_floor(labels: list[dict], *, min_labels: int = 30, min_keep_precision: float = 0.85,
                    floor_min: float = 0.50, floor_max: float = 0.90, low_conf_below: int = 50) -> dict:
    """ADR 0016 D2, PER NICHE (the caller groups by niche). Maximize F1 s.t. keep-precision >=
    constraint. Below min_labels -> hold PROVISIONAL. n < low_conf_below -> data_anchored but flagged
    low_confidence (a 1-2 week ramp yields few labels: directional, operator-promoted, never auto-applied)."""
    if len(labels) < min_labels:
        return {"floor": PROVISIONAL, "reason": "insufficient_labels", "n_labels": len(labels)}
    best, thr = None, floor_min
    while thr <= floor_max + 1e-9:
        kp, recall, f1 = _metrics_at(labels, round(thr, 3))
        if kp >= min_keep_precision and (best is None or f1 > best["f1"]):
            best = {"floor": round(thr, 3), "f1": round(f1, 3),
                    "keep_precision": round(kp, 3), "recall": round(recall, 3)}
        thr += 0.01
    if best is None:
        return {"floor": floor_max, "reason": "precision_constraint_unmet", "n_labels": len(labels)}
    return {**best, "reason": "data_anchored", "n_labels": len(labels),
            "low_confidence": len(labels) < low_conf_below}
```

- [ ] **Step 3: Implement `shorts/calibrate.py`** (`make calibrate`) — scan `history/feature_index.jsonl` + recent `runs/*/*/feature_record.json` for records with a `ramp_label`; **group by `niche`**; for each, map `{"overall": fr["creative_qc_overall"], "approved": fr["ramp_label"]["approved"]}` and call `recommend_floor`; write **`DATA_ROOT/.metrics/floor_recommendation.<niche>.json`** (durable, outside GC) + print the per-niche diff vs the live `config.quality.floor.<niche>` and the promote instruction. It also **appends each labelled record to `history/feature_index.jsonl`** (the analytics accumulation seam). **Field contract pinned:** `feature_record.creative_qc_overall` (a scalar copied from `creative_qc.overall` at fan-in) + `feature_record.ramp_label.approved` + `feature_record.niche`.
- [ ] **Step 4: Wire `make calibrate`**. **Run** the unit tests → PASS (4). **Commit.**

```bash
git add shared/calibration/ shorts/calibrate.py Makefile tests/test_calibration_anchor.py
git commit -m "feat(m6): per-niche 05c floor re-anchoring (F1 + keep-precision, low-confidence flag, ADR 0016 D2)"
```

### Task 11: The weekly spot-audit report

**Files:** Create `shared/audit/__init__.py` (empty), `shared/audit/report.py`, `shorts/audit.py`; Modify `Makefile`; Test `tests/test_audit_report.py`

- [ ] **Step 1: Write the failing test** (the live floor is INJECTED, not defaulted)

```python
# tests/test_audit_report.py
from shared.audit.report import build_report


def test_report_summarizes_posts_quarantines_and_drift_vs_LIVE_floor():
    posts = [{"video_id": "a", "platform": "youtube", "url": "u1"}]
    quarantines = [{"video_id": "c", "failed_checks": ["prohibited_claims"]},
                   {"video_id": "d", "failed_checks": ["loudness", "black_run"]}]
    feature_records = [{"video_id": "a", "creative_qc_overall": 0.82, "ramp_label": {"approved": True}},
                       {"video_id": "e", "creative_qc_overall": 0.55, "ramp_label": {"approved": True}}]
    r = build_report(posts=posts, quarantines=quarantines, feature_records=feature_records, floor=0.70)
    assert r["posted_count"] == 1 and r["quarantined_count"] == 2
    assert r["quarantine_reasons"]["prohibited_claims"] == 1 and r["quarantine_reasons"]["black_run"] == 1
    # 'e' (0.55 < 0.70) the gate would HOLD, but the human APPROVED -> drift flagged
    assert any(d["video_id"] == "e" for d in r["label_score_disagreement"])
    assert all(d["video_id"] != "a" for d in r["label_score_disagreement"])      # 'a' agrees
```

- [ ] **Step 2: Implement `shared/audit/report.py`**

```python
from collections import Counter


def build_report(*, posts: list[dict], quarantines: list[dict], feature_records: list[dict],
                 floor: float) -> dict:
    """The DoD clause-2 spot-audit (read-only). Disagreement is computed vs the LIVE floor (injected
    by the caller from config), not a hardcoded default — so a promoted floor isn't audited stale."""
    reasons = Counter(c for q in quarantines for c in q.get("failed_checks", []))
    disagree = [{"video_id": fr["video_id"], "score": fr["creative_qc_overall"],
                 "human_approved": fr["ramp_label"]["approved"]}
                for fr in feature_records if "ramp_label" in fr
                and (fr["creative_qc_overall"] >= floor) != fr["ramp_label"]["approved"]]
    return {"posted_count": len(posts), "quarantined_count": len(quarantines), "posts": posts,
            "quarantine_reasons": dict(reasons), "label_score_disagreement": disagree}
```

- [ ] **Step 3: Implement `shorts/audit.py`** (`make audit`) — gather the trailing-7-day `history/posts.jsonl` records, the `quarantine/` `qc.json` failures, and labelled `feature_record`s; pass `floor=config["quality"]["floor"][niche]` (the **live** value per niche); render to stdout + **`DATA_ROOT/.metrics/audit_<date>.json`** (durable).
- [ ] **Step 4: Wire `make audit`**. **Run** → PASS. **Commit.**

```bash
git add shared/audit/ shorts/audit.py Makefile tests/test_audit_report.py
git commit -m "feat(m6): weekly spot-audit report vs the live floor (posts/quarantines/drift, DoD clause 2)"
```

---

# Part E — Stability hardening + the soak harness + the unattended-run gate

### Task 12: The offline soak harness (drives the REAL `batch_flow`)

**Files:** Create `tests/helpers/soak.py`, `tests/test_soak_offline.py`; Modify `Makefile` (`soak`), `pyproject.toml` (register the `soak` marker)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_soak_offline.py
import pytest
from tests.helpers.soak import run_offline_soak


@pytest.mark.soak   # a dedicated marker (not 'integration'); runs under `make soak`, off the default sweep
def test_soak_survives_n_batches_without_wedging(tmp_path):
    result = run_offline_soak(data_root=tmp_path, batches=14, seed=1,
                              inject={"kill_mid_batch_on": 3, "stale_lock_on": 5, "disk_low_on": 8})
    assert result["wedges"] == 0 and result["silent_failures"] == 0
    assert result["batch_3_resumed"] and result["batch_5_took_over_stale_lock"]
    assert result["batch_8_halted_with_alert"]            # disk-low pre-flight halted, not quarantined
    assert result["ledger_monotonic"] and result["runs_within_retention"]
```

- [ ] **Step 2: Implement `tests/helpers/soak.py`** — a real scaffold, not prose:

```python
# tests/helpers/soak.py
"""Drives the REAL M4 batch_flow N times with injected collaborators + a FakeClock — NOT a
re-implementation. The faults are injected as the same closures batch_flow already accepts."""
from dataclasses import dataclass, field

from shorts.run_batch import batch_flow                     # the M4 function test_run_batch_flow covers
from shared.conductor.lock import acquire_lock
from shared.conductor.reconcile import resume_plan
from shared.ops.gc import runs_to_delete


@dataclass
class FakeClock:
    now: float = 0.0
    def advance(self, days: float): self.now += days * 86400


def run_offline_soak(*, data_root, batches: int, seed: int, inject: dict) -> dict:
    clock, res = FakeClock(), {"wedges": 0, "silent_failures": 0, "ledger_monotonic": True,
                               "runs_within_retention": True}
    prev_ledger_len = 0
    for n in range(1, batches + 1):
        lock = data_root / ".run" / "batch.lock"
        if n == inject.get("stale_lock_on"):
            (data_root / ".run").mkdir(parents=True, exist_ok=True); lock.write_text("999999999")
        # fault closures passed to the SAME batch_flow signature (lock/preflight/plan/execute/commit/backup):
        preflight = (_raise_disk_low if n == inject.get("disk_low_on") else _noop)
        execute = (_kill_then_resume(res, n) if n == inject.get("kill_mid_batch_on") else _fake_execute)
        try:
            batch_flow(lock_path=lock, data_root=data_root, preflight=preflight,
                       plan=_fake_plan(n, seed), execute=execute, commit=_fake_commit, backup=_noop)
        except _SystemicHalt:
            res["batch_8_halted_with_alert"] = True
        except _KilledMidBatch:
            resume_plan(_load_batch(data_root, n)); res["batch_3_resumed"] = True
        res["batch_5_took_over_stale_lock"] = res.get("batch_5_took_over_stale_lock") or (
            n == inject.get("stale_lock_on") and lock.read_text() != "999999999")
        # invariants
        cur = _ledger_len(data_root)
        res["ledger_monotonic"] &= cur >= prev_ledger_len; prev_ledger_len = cur
        res["runs_within_retention"] &= len(runs_to_delete(_list_runs(data_root), keep_days=7,
                                                           keep_count=14)) >= 0   # bound holds
        clock.advance(1)
    return res
# (_noop/_fake_*/_raise_disk_low/_kill_then_resume/_load_batch/_ledger_len/_list_runs are small
#  fixture helpers over the M0 fake-backend harness; _SystemicHalt/_KilledMidBatch are test sentinels.)
```

The point: **`batch_flow` is the real M4 function**, exercised with the collaborators it already accepts — so the soak catches regressions in the lock/preflight/commit/backup ordering, the reconcile path, and the GC bound, not just a parallel mock.
- [ ] **Step 3: Register the marker** in `pyproject.toml` (`[tool.pytest.ini_options] markers = ["soak: the offline stability soak"]`); wire `make soak` → `N=${N:-14} uv run pytest tests/test_soak_offline.py -m soak -q`. **Run** → PASS. **Commit.**

```bash
git add tests/helpers/soak.py tests/test_soak_offline.py pyproject.toml Makefile
git commit -m "test(m6): offline soak over the REAL batch_flow — lock/reconcile/GC/no-wedge mechanics (ADR 0003)"
```

### Task 13: The unattended-run runbook + the DoD acceptance gate

**Files:** Create `deploy/host/soak-runbook.md`

- [ ] **Step 1: Write `deploy/host/soak-runbook.md`** — the procedure, with the single-Windows-box realities made explicit:
  1. **Pre-conditions:** `make soak` green; `make obs-up` healthy (Prometheus targets up incl. the nvidia-smi + queue `.prom`, Grafana live, a **synthetic alert tested end-to-end** through Alertmanager); the OAuth app in **Production**; the **`--dry-run` smoke** passes all five pre-flight gates against the real credential/quota state; the ramp gate **lifted** for ≥1 niche (M5 `gate_active == False`); ≥1 **public** account live (YouTube-led; TikTok audit status recorded).
  2. **Windows-host hardening (ADR 0013 reality):** set **Windows Update active hours** to span the batch window + disable auto-restart for the duration; add a **Task Scheduler `wsl`-at-logon** task that runs `wsl systemctl start shorts-batch.timer` (WSL2 does not auto-boot the timer after a Windows reboot); disable sleep/hibernate for the window (ADR 0015 D3).
  3. **Start:** enable the M4 `shorts-batch.timer`; record the start date.
  4. **Daily acceptance log** (one row/day): batch produced? posted (count + URLs)? quarantine (reason)? alert fired (which)? disk/VRAM/queue nominal? **any unrecovered failure?** — **the clock resets only on an UNRECOVERED failure**, not on a clean auto-recovery (a Windows reboot that the boot reconciler resumes from is a logged event, **not** a reset — DoD clause 4 is *unattended*, which the reconcile path preserves).
  5. **Weekly:** `make audit`; `make calibrate` (record + promote per-niche floors if earned).
  6. **Exit:** ~1–2 weeks of daily batches with **zero unrecovered failures, clean logs, no silent failures**, gates enforced, real posts landing.
- [ ] **Step 2: Commit.**

```bash
git add deploy/host/soak-runbook.md
git commit -m "docs(m6): the unattended-run runbook (Windows hardening + recovery-aware DoD clock)"
```

---

## M6 Acceptance Checklist (the testable "done" — = the Chapter 1 Definition of Done, made concrete)

- [ ] **Observability:** per-stage + per-batch series (incl. `shorts_batch_failed_total`, `shorts_quarantine_rate`/`_baseline`, the `running` gauge) land via the textfile collector; **GPU metrics via nvidia-smi** (not DCGM — WSL2); ComfyUI queue depth; Grafana renders; the stage heartbeat advances while running and freezes on stop → Tasks 1–3.
- [ ] **Alerting distinguishes slow from stuck and page from warn:** `StageStuck` is gated by `running == 1` (no false page on a completed stage); `StageSlow` is warn-severity and inhibited under `StageStuck`; `QuarantineSpike` uses the same two-part condition as the in-code detector → Tasks 4–6.
- [ ] **Lifecycle hygiene:** the post-batch sweep GCs `runs/` (7d/14-batch) + `quarantine/` (30d) + the cache (50 GB LRU), **never `history/`/`models/` and never the active or reconciler-resumed batch**; the full **config-driven** pre-flight list halts on any systemic failure; the wiring test invokes the **real** OAuth gate → Tasks 7–9.
- [ ] **The calibration loop is closed PER NICHE (ADR 0016 D2):** `make calibrate` emits a per-niche floor recommendation (F1 + keep-precision, **low-confidence-flagged** under 50 labels, provisional under 30) to a durable path + the `feature_index.jsonl` accumulation seam; `make audit` reports drift vs the **live** floor → Tasks 10–11.
- [ ] **Stability mechanics proven offline over the REAL `batch_flow`:** `make soak` runs 14 batches with injected kills/stale-locks/disk-low and asserts zero wedges, zero silent failures, reconcile-after-kill, stale-lock takeover, systemic-halt-not-quarantine, monotonic ledgers, GC within bounds → Task 12.
- [ ] **DoD clause 1 — unattended:** the timer produces a daily batch **post-ramp**; 05b is the durable human replacement; a failed stage retries/quarantines/halts, never wedges → Task 13 + M4/M5.
- [ ] **DoD clause 2 — quality owned + enforced:** every posted video passed **05b AND 05c**; the weekly spot-audit confirms "genuinely good, not slop," incl. original-insight → Tasks 10–11 + M3/M5.
- [ ] **DoD clause 3 — real posting:** real YouTube Data API v3 + TikTok Content Posting API to live new accounts, private-first with **≥1 public** (YouTube-led); the on-box **`--dry-run`** passed all pre-flight gates first → M5 + Task 13.
- [ ] **DoD clause 4 — stability:** **~1–2 weeks** of daily batches with **no unrecovered failure** (a clean auto-recovery from a Windows reboot does not reset the clock), clean logs, provenance intact, recorded in the acceptance log → Task 13.

---

## Self-Review

**Spec coverage (Ch.10 M6 row + Ch.8 + the Ch.1 DoD):** hardening + **alerts/GC/credential pre-flight wired** → A/B/C; the **per-niche 05c floor re-anchoring** (ADR 0016 D2) + the **weekly spot-audit** → D; the **~1–2 week unattended run** + the soak proxy → E. Open #3 (numeric tuning) is pinned as config with **explicit call-site load paths**; #10's 05c-floor question is closed (00b floor noted out of scope); #11 (cache substrate + feature-record location) is resolved (file cache + `feature_index.jsonl`).

**Review fixes folded in (from the M6 multi-lens review):** DCGM → **nvidia-smi** (DCGM is dead under WSL2); the **heartbeat daemon** + `running` gauge (the subprocess-liveness gap) and a `running`-gated `StageStuck` (no false page on completed stages); **per-niche** calibration (was pooling niches) + per-niche `shorts_quarantine_rate` labels; the **`shorts/run_batch.py`** module path (not `shared/conductor/run_batch.py`); a **real `tests/helpers/soak.py` scaffold + `FakeClock`** driving the **real `batch_flow`** (not a re-implementation); `render_batch_metrics` so the alert series actually exist; GC `protected_ids` (don't delete a resumed batch); the calibration **`low_confidence` flag + `min_labels=30`** (overfit guard); **config-load at the call site** for every knob; metrics via an **injected wrapper** (keeps `execute_batch` pure); the **`feature_record.creative_qc_overall`/`ramp_label`/`niche`** field contract pinned and consistent across Tasks 10–11; durable output under `DATA_ROOT/.metrics/` + `history/` (not GC-able `runs/`); the `QuarantineSpike` rule = the `is_spike` two-part condition; alert **severity + inhibition**; **nearest-rank p95**; a **real-OAuth-gate** wiring test; `_build_backends` **explicitly deferred** to bring-up with a `--dry-run` acceptance; `make obs-lint` (promtool/amtool in CI); the runbook's **Windows-host hardening** + **recovery-aware DoD clock**; the soak marker is `soak` (not `integration`); the `evict_to_cap` test asserts against survivors.

**Placeholder scan:** no "TBD". The integration seams (the exporter/Prometheus/Grafana deployment; `_build_backends` real wiring deferred to the runbook with a `--dry-run` gate; the soak fixture helpers over the M0 fake harness) are documented, and every pure module — metrics rendering, baselines/classify, spike, GC, LRU, budgets, per-niche `recommend_floor`, the report, the heartbeat — is implemented + unit-tested. The real run is honestly the on-box gate (Task 13).

**Type consistency vs M0–M5:** reuses the M1 `StageTimer`/`timing.jsonl`; the M4 `batch_flow`/`execute_batch` (purity preserved — emission is an injected `run_stage` wrapper)/`resume_plan`/`runs_to_delete` protected set/`backup()`; the M4 module **`shorts/run_batch.py`** + **`shorts/stage.py`**; the M5 `feature_record.ramp_label`/`creative_qc_overall`/`niche`, `posts.jsonl`, `qc.json`, the OAuth/quota gates + `PreflightFailure`; the M0 fake-backend harness. No schema changes (M6 reads existing artifacts; metrics are out-of-band `.prom` text). `make {obs-up,obs-lint,audit,calibrate,soak}` join the Makefile convention.

**Scope:** five parts, one terminal gate (the DoD). A–D are pure + CI-testable; E depends on them plus M5's lifted ramp. The deliverable is the *evidence* — green soak, live dashboards, a quiet pager, two weeks of clean daily batches — that the loop runs reliably, unattended, at a quality bar we're not embarrassed by. After M6 the PoC is done; M7 (the k8s profile) is the only remaining, optional plan.
