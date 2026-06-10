# ADR 0015 — Runner-first orchestration; Kubernetes becomes a deployment profile

- **Status:** Accepted (2026-06-10)
- **Builds on:** [ADR 0013](0013-windows-host-support-wsl2.md) (the whole Linux stack lives in one
  WSL2 distro — this ADR decides *what orchestrates inside it*),
  [ADR 0003](0003-resilience-concurrency-observability.md) (whose resilience semantics survive,
  re-homed), [ADR 0011](0011-performance-and-optimization.md) (whose lane-fork/fan-out survive as
  runner concurrency), [ADR 0012](0012-m0-build-contract.md) (whose runner + manifests this
  promotes to production).
- **Supersedes in part:** [ADR 0001](0001-lightened-runtime-architecture.md)'s control-plane
  *executor* (kind + Argo Workflows) and [ADR 0010](0010-implementation-conventions-and-extensibility-seams.md)
  D2's "hand-written Argo templates + drift-catcher." The two-plane *separation* (host GPU
  processes ↔ CPU stages over HTTP) is **kept**; only the executor changes.
- **Touches:** spec Ch.1/Ch.3/Ch.10 (M0 + M4 rows), ARCHITECTURE (control-plane sections),
  README, Makefile, the M0 plan (runner status), plans M1–M3 (light).
- **Origin:** a top-to-bottom architecture re-review found the design running **two
  orchestrators**: the M0 Python DAG runner (topology, cache, status, quarantine — fully
  CI-tested) *and* the same choreography re-expressed in Argo YAML on a kind cluster, kept in
  sync by a drift-catcher. The constraint set: the operator runs **Windows** (WSL2, single RTX
  5070 Ti box) and wants the system **production-deployable on demand** — without the PoC paying
  the cluster tax nightly.

## Context

The workload is **2–4 videos, once a night, on one machine**, where every GPU stage is already a
thin HTTP client to host processes (ADR 0001). Against that, the kind/Argo control plane costs:

- **The least-tested code is the most failure-prone.** Retries, `continueOn`, the GPU
  lease/confirm-evicted gate, `concurrencyPolicy` live only in Argo YAML — which the GPU-free CI
  *cannot execute*. Meanwhile the M0 runner implements the same semantics in Python and is tested
  on every commit.
- **An ops surface that produces zero videos.** kind-cluster lifecycle, ~15 stage images built +
  `kind load`-ed per change (ARCHITECTURE: "one dir = one image"), PVC `extraMounts`, docker-bridge
  networking to host services, Task-Scheduler keep-alives — these are the things most likely to
  break a 2-week unattended run on WSL2 (the DoD), and none of them is content work.
- **A silent path-namespace split.** Pods see the PVC mount path; host services (ComfyUI, Ollama,
  the VLM endpoint) see host paths; ComfyUI writes to its own output dir. No document owned the
  host↔pod path translation. Removing pods removes the split.

"Kubernetes-native" was a first-line README goal. This ADR re-reads that goal honestly: what the
project needs is **Kubernetes-deployable** (a proven container + declarative stage metadata — the
ability to lift onto a cluster when scale demands it), not Kubernetes-*resident* for a single-box
nightly batch.

## Decision

1. **The M0 Python runner is the production conductor.** `shared/runner.py` — already built to the
   ADR 0012 contract (stage manifests → topology, content-addressed cache, `pending→running→done/
   quarantined` status transitions, schema validation at every boundary) — runs the nightly batch.
   The **stage metadata manifests are the single source of orchestration truth**; nothing is
   re-expressed in YAML. ADR 0011's lane-fork (visual ∥ audio) and per-video fan-out become runner
   concurrency (process/thread pools), adopted behind the same timing metrics ADR 0011 demands.

2. **kind/Argo is demoted to a deferred *deployment profile*, and "production-deployable" becomes a
   CI-proven property.** Concretely:
   - **One shared image** (the whole repo; entrypoint selects a stage or the runner by argument)
     replaces one-image-per-stage. CI **builds this image and runs the GPU-free offline DAG inside
     it** — so the deployable artifact is continuously tested, not aspirational.
   - The Argo profile (`deploy/argo/`, post-PoC, built only if/when multi-box scale demands it)
     uses **dumb one-line templates** (`python -m shorts.stage <id>`) generated against the same
     manifests. Choreography never lives in YAML; the drift-catcher (manifest ⟷ registry) already
     guards the only contract that matters.
   - The Stage SDK, declared-IO manifests, adapter Protocols, and config layer (ADR 0010/0012) are
     untouched — they are exactly the seams that make the lift cheap later.

3. **Scheduling and the concurrency guarantee re-home to the OS.** Inside the WSL2 distro
   (ADR 0013), a **systemd timer** (WSL2 supports systemd) triggers the nightly batch; Windows
   Task Scheduler remains only the WSL boot/keep-alive trigger. Argo's `concurrencyPolicy: Forbid`
   is replaced by a **run lockfile** (atomic create; a second trigger exits, mirroring ADR 0003's
   no-overlap rule). The boot-time batch reconciler (ADR 0003 D9) is unchanged and now has fewer
   layers to reconcile.

4. **One filesystem, one `DATA_ROOT` — the path contract.** With no pods there is no host↔pod path
   split: stages, the runner, ComfyUI, Ollama, and the VLM endpoint all run in the same WSL2
   filesystem. The data layout (spec Ch.5) roots at a single **`DATA_ROOT`** env var (ext4, not
   `/mnt/c` — ADR 0013); **ComfyUI's output directory is configured to a path under `DATA_ROOT`**
   so generated assets are immediately addressable by the stages with no copy/translation step.
   This closes the path-translation gap as a *contract*, not a workaround.

5. **What survives from ADR 0001/0003, re-homed.** The two-plane separation survives as **process
   boundaries**: ComfyUI/Ollama stay independently-supervised host services reached over
   localhost HTTP, with health gates before the batch starts (`up.sh` semantics unchanged). The GPU
   lease + confirm-evicted gate simplify: the runner is now the *only* GPU client, so
   never-co-resident is enforced by the conductor's own stage ordering plus a VRAM-free check
   before diffusion stages. Retries/backoff/per-video failure domains/quarantine are runner
   features — written once, unit-tested in CI.

6. **M4 is rescoped** from "Argo orchestration" to **"conductor hardening + ops"**: runner
   concurrency (lane-fork/fan-out), retries/timeouts as tested code, the lockfile + systemd timer
   + Task-Scheduler boot trigger, `up.sh`/`down.sh` against host services only (no cluster), the
   CI-built shared image, and the unchanged **M4 gate** — the end-to-end overnight throughput
   reconciliation (open #9).

## Consequences

**Positive**
- **One orchestrator, fully exercised by CI** — the choreography that guards the 2-week unattended
  run is tested on every commit instead of discovered at 3 a.m.
- **The Windows posture gets dramatically more robust**: WSL2 + one Python process + systemd is a
  far smaller failure surface than WSL2 + Docker + kind + Argo (ADR 0013's residual risks shrink
  with it).
- **Dev loop collapses** to `pytest` / `python -m shorts.run` — no image builds, no `kind load`.
- **Production-deployability is *more* honest than before**: a continuously-built, DAG-tested
  image + declarative manifests is a stronger k8s story than untested YAML.

**Negative / costs**
- Argo's free reliability primitives (retry UI, lineage, CronWorkflow) are replaced by code we own
  — the runner becomes load-bearing and M4 must harden it (that work was always owed; now it's
  visible).
- No workflow UI; observability leans on the ADR 0003 stack (structured logs + metrics + the
  status ledger), which was already the source of truth.
- The "Kubernetes-native" learning/portfolio goal is **deferred, not deleted** — recorded honestly
  as a post-PoC profile.

## Open (tracked)

- The runner's concurrency implementation (process pool vs asyncio) — decide in M4 against the
  timing metrics.
- The shared image's base + size budget; whether CI also smoke-runs the Argo profile's template
  generation (post-PoC).
- `scripts/up.sh`/`Makefile` rewrite lands with M4 (the cluster targets are marked deferred until
  then).
