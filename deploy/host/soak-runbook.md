# Unattended-Run Runbook — Chapter 1 Definition of Done

> **Audience:** the operator running the box during the PoC soak.
> **Scope:** everything from M5 ship date to the moment you can declare the
> Chapter 1 DoD met.  Read alongside
> `deploy/host/power-policy.md`, `deploy/host/oauth-production.md`, and
> `deploy/host/platform-audit.md`.

---

## 1. Honest timeline — the DoD is wall-clock-gated, not code-gated

"M6 code-complete" is not the same as "DoD met."  The DoD (clause 1) requires a
demonstrated ~1–2 week unattended run with real posts landing.  That run cannot
start until several calendar gates clear:

```
M5 ships on a real box
        │
        ▼  ~7 days
  Provisioning / warming
  (YouTube: first public post must age before quotas normalise;
   TikTok: sandbox until audit clears)
        │
        ▼  ≥7 days + ≥10 ramp approvals  (gate-lift threshold)
  Ramp track-record
  (cadence-widen needs ≥14 days + ≥20 approvals — may overlap)
        │
        ▼  ~1–2 calendar weeks
  Unattended soak  ← the actual DoD gate
        │
        ▼
  DoD met  (≈5–7 weeks after M5 on-box, independent of code quality)
```

**The 05c floor during the soak is provisional (0.70).**  A 1–2 week ramp at
~1 video/day/niche yields ≈7–14 labels per niche — below the `min_labels=30`
guard in `shared/calibration/anchor.py`.  `make calibrate` will flag every niche as
`low_confidence` until ~50 labels accumulate.  The 0.70 floor is
operator-confirmed and intentionally not empirically anchored for the PoC run.
A genuinely data-anchored floor is a post-PoC outcome; the calibration machinery
ships and runs, surfacing this gap honestly in every report.

---

## 2. Pre-conditions checklist

Work through this list before starting the soak clock.  Every item must be green
or explicitly recorded as "tracking (see note)".

### 2a. Offline gate

- [ ] `make soak` passes (runs `tests/test_soak_offline.py` — the stability
  mechanics harness: lock takeover, reconcile-after-kill, GC bounds, ledger
  monotonicity, zero wedges, zero silent failures).  Soak green is necessary
  but not sufficient.

### 2b. Observability stack healthy

Run `make obs-up` and verify each of the following:

- [ ] Prometheus (`http://127.0.0.1:9090`) shows **all targets UP**:
  - `node` job → `127.0.0.1:9100` (node-exporter, textfile collector)
  - Confirm `nvidia.prom` is arriving in
    `$DATA_ROOT/.metrics/textfile/nvidia.prom` (the nvidia-smi poller —
    see `deploy/obs/nvidia-smi-exporter.md`).
  - Confirm `comfyui_queue.prom` is arriving in
    `$DATA_ROOT/.metrics/textfile/comfyui_queue.prom`
    (the ComfyUI queue poller — see `deploy/obs/comfyui-queue-exporter.md`).
- [ ] Grafana (`http://127.0.0.1:3000`) loads and the dashboard shows live data.
- [ ] **Synthetic alert tested end-to-end through Alertmanager.**
  Inject a `BatchFailed`-equivalent metric to exercise the full pipeline:

  ```bash
  # Write a test .prom that trips the BatchFailed rule
  # (shorts_batch_failed_total must *increase* within a 1h window)
  TEXTFILE_DIR="${DATA_ROOT:?}/.metrics/textfile"
  cat > "${TEXTFILE_DIR}/synthetic_test.prom" <<'EOF'
  # HELP shorts_batch_failed_total Synthetic test counter
  # TYPE shorts_batch_failed_total counter
  shorts_batch_failed_total{batch="synthetic",niche="test"} 1
  EOF
  # Wait ~2 scrape intervals (≥30 s), then increment so increase() > 0
  sleep 30
  cat > "${TEXTFILE_DIR}/synthetic_test.prom" <<'EOF'
  # HELP shorts_batch_failed_total Synthetic test counter
  # TYPE shorts_batch_failed_total counter
  shorts_batch_failed_total{batch="synthetic",niche="test"} 2
  EOF
  ```

  Alternatively, use `amtool` to fire a test alert directly:

  ```bash
  amtool alert add alertname=BatchFailed \
      --alertmanager.url=http://127.0.0.1:9093 \
      severity=page niche=test batch=synthetic \
      --annotation=summary="Synthetic test"
  ```

  Confirm the alert appears in Alertmanager (`http://127.0.0.1:9093`) and
  your notification channel receives a page.  Remove the synthetic `.prom`
  file and confirm the alert resolves:

  ```bash
  rm "${DATA_ROOT:?}/.metrics/textfile/synthetic_test.prom"
  ```

### 2c. OAuth and credentials

- [ ] Google Cloud OAuth consent screen is in **Production** status
  (not Testing).  Follow `deploy/host/oauth-production.md` steps 1–4.
  A Testing-status app expires refresh tokens every 7 days; a mid-soak
  expiry will break the batch silently at the `oauth` pre-flight gate.
- [ ] TikTok access token refresh is automated and wired into the pre-flight
  check (`deploy/host/oauth-production.md` step 6).  Access tokens expire
  after 24 hours; a stale token surfaces as a 401 on the first TikTok post
  attempt — it does not trip the pre-flight gate, it fails that video at
  the distribution stage.

### 2d. Dry-run smoke

Run the full pre-flight list against real credentials and quota state:

```bash
make dry-run PROFILES=finance,business COUNT=1
```

The `--dry-run` flag exercises all five pre-flight gates in order:
`free_space_gate` → `host_health_gate` → `oauth_token_age_gate(mode="production")`
→ `youtube_quota_gate` → `data_api_budget_gate`.  All five must pass.  Failures
are reported by gate name; fix before starting the soak.

### 2e. Ramp gate lifted for at least one niche

- [ ] Confirm `gate_active == False` for ≥1 niche via `make review`.
  The gate lifts after ≥10 approvals over ≥7 days with ≤1 rejection.
  Until this is true the batch produces videos but does not post them
  publicly (they are held for review).

### 2f. At least one public account live

- [ ] **YouTube:** at least one niche is posting publicly post-warming.
  YouTube-led; no external audit required.
- [ ] **TikTok:** the TikTok app audit must be **submitted** at M5 go-live.
  Track its state here using the checklist in `deploy/host/platform-audit.md`.
  Until `tiktok.audit_cleared` is `true` in the conductor config, all TikTok
  posts are forced to `SELF_ONLY` by `shared/distribution/visibility.py`
  regardless of ramp status.  The "≥1 public per platform" DoD clause leans
  on YouTube for the PoC; TikTok public is external-audit-gated and may not
  land during the soak window — record the audit state and owner here:

  | Field | Value |
  |---|---|
  | Audit submitted date | _fill in_ |
  | Audit owner | _fill in_ |
  | Current status | sandbox / under review / cleared |
  | `tiktok.audit_cleared` flipped | yes / no |

---

## 3. Windows-host hardening (ADR 0013/0015 D3)

The conductor runs inside WSL2 under a Windows host.  These hardening steps
prevent Windows from breaking the unattended run.  Follow `deploy/host/power-policy.md`
for the full checklist; the items below are the ones specific to the soak duration.

### 3a. Windows Update active hours — exclude the batch window

The `shorts-batch.timer` fires at **02:00** (see `deploy/host/shorts-batch.timer`).
The batch window is roughly **01:00–06:00**.

Set active hours so automatic restarts cannot land in that window:

- *Settings → Windows Update → Advanced options → Active hours*
  — set to a range that excludes 01:00–06:00 (e.g. 08:00–23:00).

For the soak duration, also disable automatic restart via Group Policy:

- *gpedit.msc → Computer Configuration → Administrative Templates →
  Windows Components → Windows Update →
  "No auto-restart with logged-on users for scheduled automatic
  updates installations"* → **Enabled**.

Or via registry (elevated PowerShell):

```powershell
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" `
    -Name NoAutoRebootWithLoggedOnUsers -Value 1 -Type DWord
```

Re-enable after the soak is complete.

### 3b. Task Scheduler at-logon task for WSL2 systemd

WSL2 does not auto-boot systemd timers after a Windows reboot.  A Windows
Task Scheduler task must kick the distro alive at logon so
`shorts-batch.timer` has a systemd to fire under.

Create a task in Task Scheduler (or import via XML) with:

- **Trigger:** At log on (any user)
- **Action:** Start a program
  - Program: `wsl`
  - Arguments: `-- systemctl start shorts-batch.timer`
- **Run whether user is logged on or not:** yes
- **Run with highest privileges:** yes

The same at-logon task must also start the observability pollers
(see `deploy/obs/nvidia-smi-exporter.md` and
`deploy/obs/comfyui-queue-exporter.md` — both document the Task Scheduler
approach for WSL2 hosts):

| Task name | WSL2 command |
|---|---|
| `shorts-timer` | `wsl -- systemctl start shorts-batch.timer` |
| `nvidia-smi-poller` | `wsl -- bash /opt/shorts-creator/deploy/obs/nvidia-smi-poller.sh` |
| `comfyui-queue-poller` | `wsl -- bash /opt/shorts-creator/deploy/obs/comfyui-queue-poller.sh` |

### 3c. Disable sleep and hibernate for the soak window

Elevated PowerShell:

```powershell
powercfg /change standby-timeout-ac 0    # disable sleep on AC power
powercfg /hibernate off                  # disable hibernate
```

Restore after the soak:

```powershell
powercfg /change standby-timeout-ac 30  # or whatever your normal setting is
powercfg /hibernate on
```

### 3d. Verify the timer is enabled inside WSL2

```bash
wsl -- systemctl is-enabled shorts-batch.timer
# must print: enabled
```

If not enabled:

```bash
wsl -- systemctl enable --now shorts-batch.timer
```

---

## 4. Start the soak

1. Enable the `shorts-batch.timer` if not already running (step 3d above).
2. Trigger one manual batch to confirm the end-to-end path before going
   unattended:

   ```bash
   make trigger
   ```

   Watch `journalctl -u shorts-batch -f` until the batch completes.
   Confirm a post landed (or was held in ramp — either is correct).

3. **Record the soak start date in the acceptance log (Section 5 below).**
   The DoD clock starts here.

---

## 5. Daily acceptance log

Fill in one row per calendar day.  Keep this table in a file tracked alongside
the repo (e.g. `DATA_ROOT/.metrics/soak-acceptance-log.md`) so it survives a
host rebuild.

```markdown
| Date | Batch produced? | Posts (count + URLs) | Quarantine (reason) | Alert fired (which) | Disk / VRAM / queue nominal? | Unrecovered failure? |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | yes/no | N · url1, url2 | none / reason | none / alert-name | yes/no | none / description |
```

**If a platform strike lands, record it the day it lands** with
`uv run python -m shorts.review --data-root $DATA_ROOT --record-strike "<platform/why>"` —
this feeds the ramp gate's `max_strikes` bar (`shared/ramp/policy.py`), re-activating the
human-at-publish gate until the track record clears.

**The DoD clock resets ONLY on an UNRECOVERED failure.**

Definitions:
- **Unrecovered failure:** the batch did not produce or post, AND the system
  did not resume without operator intervention.  Examples: a hung conductor
  that was not caught by `TimeoutStartSec=10h`, a corrupt lockfile that
  required manual cleanup, a credential expiry that was not caught by the
  pre-flight gate.
- **Recovered failure (log it, do NOT reset the clock):** a Windows reboot
  mid-batch where the boot-reconciler (`shared/conductor/reconcile.py`)
  detected the stale lockfile, re-queued the held videos, and the next
  scheduled run completed normally.  This is exactly what ADR 0003 clause 4
  ("unattended") requires: the reconcile path preserves the DoD invariant.
  Log the reboot and the reconcile event; do not reset the clock.
- **Quarantine (not a failure):** a video quarantined by a QC gate is a
  normal pipeline outcome.  Log the reason (which gate, which niche); alert
  only if the `QuarantineSpike` Alertmanager rule fired.

**Silent failure** — if `journalctl -u shorts-batch` shows the timer fired but
no batch artifact appeared in `DATA_ROOT/runs/`, that is an unrecovered failure
even if no alert fired.  The audit (`make audit`) will catch this as a missing
post.  Mark it in the log and investigate before continuing the clock.

---

## 6. Weekly tasks

Run both of these on the same day each week (e.g. every Monday morning before
the next batch fires at 02:00).

### 6a. Spot-audit

```bash
make audit
```

`make audit` runs `python -m shorts.audit --data-root $DATA_ROOT`.
It reports:
- trailing 7-day posts (URLs from `history/posts.jsonl`)
- quarantine reasons by check
- `creative_qc` score distribution
- label↔score agreement drift vs the **live** floor in config

Output is written to `DATA_ROOT/.metrics/audit_<date>.<niche>.json` (one file
per niche; durable; outside
GC scope).  Keep the weekly audit JSON files — they are part of the evidence
bundle (Section 7).

If the audit reports **missing posts** (timer fired, no post, no quarantine
reason) that is a silent failure — add it to the acceptance log.

### 6b. Floor calibration

```bash
make calibrate
```

`make calibrate` runs `python -m shorts.calibrate --data-root $DATA_ROOT`.
It emits a per-niche `floor_recommendation.<niche>.json` to
`DATA_ROOT/.metrics/`.

Reading the output:
- `low_confidence: true` — fewer than 50 labels; the recommendation is
  directional only.  **Do not promote.**  Expected for the full soak duration
  at PoC cadence.
- `n < 30` (below `min_labels`) — provisional 0.70 is held; no recommendation
  is computed.
- `reason: data_anchored` + `f1 > 0` — a genuinely anchored recommendation.
  The operator may choose to promote it; it is **never auto-applied**.
- `f1 = 0.0` (degenerate) — the floor is either so low that nothing is
  rejected or so high that nothing passes; the recommendation is meaningless.
  **Do not promote a degenerate floor.**

To promote a floor after reviewing the recommendation:
1. Edit the `quality.floor.<niche>` value in the conductor config.
2. Run `make audit` immediately after to confirm the drift check reflects the
   new floor.
3. Record the promotion in the acceptance log with the date and reason.

---

## 7. Exit criteria

The Chapter 1 DoD is met when **all** of the following are true:

1. **~1–2 calendar weeks of daily batches** with the clock unbroken (no
   unrecovered failures per the definition in Section 5).
2. **Zero silent failures** — every `shorts-batch.timer` firing produced either
   a post, a quarantine record, or a pre-flight rejection; nothing disappeared.
3. **Gates enforced** — `make audit` shows no posts that violated the ramp gate
   or the 05c floor.
4. **Real posts landed** — at least one public YouTube post per soak-active niche
   per week; URLs are in the acceptance log and in `history/posts.jsonl`.
5. **No persistent alerts** — no `page`-severity alert (HostDown, DiskAlmostFull,
   BatchFailed, StageStuck, GPUVramLow) firing for more than one batch cycle
   without resolution.

### Evidence bundle

Capture the following before declaring the DoD met:

| Artefact | Location |
|---|---|
| Acceptance log (daily table) | `DATA_ROOT/.metrics/soak-acceptance-log.md` |
| Weekly audit reports | `DATA_ROOT/.metrics/audit_<date>.<niche>.json` (one per niche per week) |
| Grafana dashboard screenshots | exported from `http://127.0.0.1:3000` |
| Final calibration reports | `DATA_ROOT/.metrics/floor_recommendation.<niche>.json` |
| Posted-state ledger | `DATA_ROOT/history/posts.jsonl` (all post URLs) |
| Feature index (labelled records) | `DATA_ROOT/history/feature_index.jsonl` |

Archive the evidence bundle alongside the repo commit that closes M6.

---

## Quick-reference: key commands

| Command | What it does |
|---|---|
| `make dry-run` | pre-flight smoke (5 gates, no posts) |
| `make trigger` | manual batch now |
| `make obs-up` | start Prometheus + Alertmanager + Grafana + exporters |
| `make obs-lint` | validate `deploy/obs/*.yml` + Grafana JSON (CI gate) |
| `make review` | human-at-publish ramp review CLI |
| `make audit` | weekly spot-audit vs live floor |
| `make calibrate` | per-niche floor recommendation from ramp labels |
| `make soak` | offline stability soak (pre-condition gate, not the DoD run) |

Ports: Prometheus `:9090`, Alertmanager `:9093`, Grafana `:3000`,
node-exporter `:9100`.
