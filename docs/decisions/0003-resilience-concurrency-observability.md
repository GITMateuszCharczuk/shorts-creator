# ADR 0003 — Resilience, concurrency & observability hardening

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0001](0001-lightened-runtime-architecture.md) (lightened runtime),
  [ADR 0002](0002-recency-and-novelty-ledger.md) (recency + novelty ledger).
- **Touches:** spec Ch.3–Ch.8, Ch.10; `ARCHITECTURE.md` §3–§6; Stages `00b`, `01b`, `05b`, `06`.
- **Origin:** the five-specialist review of the design spec (workflow, architecture, bug-hunt,
  and SRE/performance lenses converged on these).

## Context

The locked design (0001/0002) is sound on the **happy path**. A multi-lens review found the
risk concentrated on the **failure path**: several reliability guarantees were *asserted* but
not *designed*, and the system's stated bar is precisely reliability under a 1–2 week unattended
run. The findings clustered, with multiple independent reviewers landing on the same items:

1. **Exactly-once posting is not achieved.** The novelty ledger was being reused as the
   posted-state record; it has no platform/receipt field. A crash *after* a post but *before*
   the append double-posts on retry; partial multi-platform posts (YT ok, TikTok fails) aren't
   representable.
2. **"Never co-resident" is unenforced across two GPU owners.** ComfyUI **and** the LLM endpoint
   are separate host processes sharing one 16 GB card with no shared lock. DAG ordering only
   sequences *within* Argo; a crash mid-eviction or an overlapping cron run collides them → OOM.
3. **The host GPU plane is an un-supervised SPOF.** ADR 0001 accepted "host down → pipeline
   stalls" as a cost, but defined no recovery — fatal for *unattended* operation.
4. **"Retry → quarantine, never wedge" was asserted, not designed.** Under stage-batching, one
   video's failure can fail the whole stage's fan-in; and systemic faults (token expiry,
   disk-full) wrongly get per-video quarantine.
5. **Cross-run dedup misses intra-batch collisions** (two same-day videos pick the same fresh
   story, since neither is in the ledger yet) and **the ledger has no concurrent-write
   discipline.**
6. **Observability was left open** — disqualifying for unattended; no GPU/VRAM telemetry, no
   alerting, no slow-vs-stuck signal.

## Decision

1. **Exactly-once posting via a dedicated posted-state ledger.** Add `history/posts.jsonl`
   (distinct from the novelty ledger), keyed `(video_id, platform)`. Each post writes an
   **intent** record *before* the API call and a **confirmed** record (with the remote post id)
   *after*. Retries consult it first. YouTube `insert` has no client idempotency token, so —
   to close the crash window *between* a successful API call and the confirmed-record write (an
   intent with no confirmation) — a retry does **not** blindly re-post: it first **searches the
   channel for a recent upload matching this video** (title/hash) and only posts if none is found.
   Per-platform records make partial multi-platform posts first-class. The novelty ledger is
   **never** reused for posting state.

2. **A single host-level GPU lease + a confirm-evicted gate.** Both ComfyUI and the LLM endpoint
   must hold one host GPU lease to run; the DAG inserts an explicit **VRAM-free confirmation**
   between `00b` (LLM) and `01b` (FLUX) — step-completion is not trusted as proof of eviction.
   The `CronWorkflow` sets **`concurrencyPolicy: Forbid`**. This reconciles the apparent tension
   in the spec: "CPU/GPU overlap" means **CPU stages overlap GPU stages *within one batch*** —
   **never two GPU batches concurrently**.

3. **Host-plane supervision + a readiness gate.** ComfyUI and the LLM run under a supervisor
   (`systemd Restart=always`) with `/health` endpoints. Argo **gates fan-out on host health**
   (fail-fast + alert, not a retry-storm against a dead host). A **batch-level circuit breaker**
   halts-and-alerts on repeated host failures instead of quarantining every video.

4. **Per-video failure domains + systemic-vs-per-video classification.** Each video is a sub-DAG
   branch with `continueOn` so a quarantined video drops out of the *remaining* fan-out while
   the batch's loaded model serves the survivors — this is what actually backs "never wedge."
   **Systemic** faults (OAuth-token expiry, disk-full, host-down) are **batch-halting alerts**,
   not per-video quarantine. Every host-client step gets a hard poll timeout +
   `activeDeadlineSeconds`.

5. **Intra-batch dedup claim + starvation ladder + timestamp hygiene.** `00b` **reserves** its
   chosen topic/source-URLs in `batch.json` so two same-batch videos can't pick the same fresh
   story (closes the TOCTOU the cross-run ledger can't see). Starvation degrades gracefully —
   **widen window → relax threshold → same-topic-different-angle → skip-with-WARN** — and never
   wedges or silently yields zero output. Recency filtering normalizes timestamps to **UTC**,
   falls back `published → fetched` when `published` is absent/implausible, and dedups on
   **canonical URL / story**, not the raw feed URL.

6. **Serialized ledger writes + per-video run-dir ownership.** Both `ledger.jsonl` and
   `posts.jsonl` are written by a **single fan-in commit step per batch** (or `flock` + `fsync`);
   concurrent appender pods are not permitted. With per-video CPU fan-out and the lane-fork (ADR
   0011) now writing the shared RWO PVC concurrently, each `runs/<batch>/<video-id>/` subtree has
   **exactly one writer at a time** (the visual and audio lanes write *disjoint* files and join only
   at 05), and per-stage `job.json` status updates are **section-scoped atomic writes** (write-temp
   + rename), never whole-file rewrites — so two concurrent stages can't clobber each other's status.

7. **An observability backend (closes the open item).** Prometheus + node-exporter +
   **DCGM-exporter for GPU/VRAM**, ComfyUI queue depth, and per-stage duration + heartbeat;
   persisted logs (not just pod stdout); alerts on **host-down, disk > 80%, batch-failed,
   quarantine-rate spike, and a cron run skipped due to `concurrencyPolicy: Forbid`** (a wedged or
   over-running batch must surface, not silently halt the daily cadence). Per-stage
   expected-duration baselines distinguish *slow* from *stuck*.

8. **Disk GC + pre-flight checks; host toolchain pinning.** Retention/GC for `quarantine/` and
   old `runs/`; a **pre-batch free-space gate** and a **pre-batch OAuth validity/refresh check**.
   The host environment **pins `torch` cu128 + the ComfyUI commit + custom-node versions** and
   snapshots working graphs — host-env drift (the relocated sm_120 risk) is a release-gated
   change.

9. **Boot-time batch reconciliation (host-reboot recovery).** `systemd Restart=always` recovers the
   host *processes*, but an in-flight Argo batch dies with the node on a host/OS reboot — the
   controller and all running stage pods are lost, which would silently drop that day's output and
   void the "1–2 week unattended" bar. So a **boot-time reconciler** (a systemd unit / Argo startup
   hook) inspects `batch.json` status on bring-up: an interrupted batch is **resumed from the last
   completed stage** (idempotent + seeded re-runs make this safe, ADR 0009) or cleanly re-submitted,
   and the event is alerted. Argo's own restart behavior is documented rather than assumed.

## Consequences

**Positive**
- The four reliability guarantees the PoC's success bar depends on (exactly-once, never-OOM,
  never-wedge, observable) become *designed properties*, not hopes.
- Systemic failures surface as alerts in minutes instead of silently quarantining a fortnight of
  output.

**Negative / costs**
- More moving parts at bring-up: a supervisor, a metrics stack, a GPU lease, two ledgers.
  Justified — they are exactly the unattended-reliability surface.
- The GPU lease + `Forbid` concurrency caps throughput at one GPU batch at a time (already the
  physical reality of one card; now explicit).

## Open (tracked)

- Concrete **retry counts / backoff curve / per-stage timeouts** and `activeDeadlineSeconds`.
- **QC thresholds** (strengthened in scope by ADR 0004; numeric tuning still open).
- Metrics-stack footprint inside `kind` vs on the host.
- Embedding model for the post-M1 dedup tier (carried from ADR 0002).
