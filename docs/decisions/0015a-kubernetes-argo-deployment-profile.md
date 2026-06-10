# ADR 0015a — The Kubernetes/Argo deployment profile: design

- **Status:** Accepted design (2026-06-10) — **build deferred** (optional milestone M7, post-PoC;
  the *decision* that the PoC runs runner-first is ADR 0015 and is unchanged).
- **Builds on:** [ADR 0015](0015-runner-first-orchestration.md) (runner-first; this designs its
  "deferred deployment profile" fully), [ADR 0010](0010-implementation-conventions-and-extensibility-seams.md)
  (the seams + the honest multi-node scope), [ADR 0012](0012-m0-build-contract.md) (the manifests
  + runner this wraps), [ADR 0001](0001-lightened-runtime-architecture.md) (host-owned GPU plane —
  kept), [ADR 0013](0013-windows-host-support-wsl2.md) (WSL2 substrate for the local cluster).
- **Touches:** spec Ch.3 (profile pointer), Ch.10 (optional M7 milestone); `deploy/` tree (new);
  Makefile (`cluster-up`/`build` targets get a real owner).
- **Origin:** the operator wants the system **genuinely Kubernetes-deployable on demand** — not as
  marketing, as a working profile — while the PoC stays runner-first on the Windows/WSL2 box.

## Context

ADR 0015 demoted kind/Argo to "a deferred deployment profile" and required that
production-deployability be a **tested property** (one shared image, CI-proven). This ADR designs
that profile completely, so building it later is execution, not design. The design goal is the
**thinnest possible k8s layer**: everything the cluster does must be *derivable* from artifacts
the PoC already maintains (the stage manifests, the shared image, `DATA_ROOT`), so the profile can
never drift into a second orchestrator again.

## Design

### D1. Two variants, adopted as a ladder

**Variant A — "conductor-in-cluster" (the minimal lift).** The entire runner — unchanged — runs as
**one Kubernetes `CronJob`** (`concurrencyPolicy: Forbid` replaces the lockfile 1:1). Kubernetes
provides scheduling, restart, log capture, and Secrets; **all orchestration stays in the tested
Python conductor**. No Argo at all. This variant is nearly free (a ~40-line manifest around the
shared image) and is the **default k8s profile**.

**Variant B — "Argo fan-out" (the scale step).** Argo Workflows executes the DAG with **one pod
per stage**, for when per-stage parallelism across nodes matters (multi-box batches, >1 GPU
host). Templates are **generated, never hand-written** (D3); each step is the dumb one-liner
`python -m shorts.stage <id> --video <video-id>` against the same image, with the Stage SDK doing
IO/validation/cache exactly as under the conductor. Argo owns only *placement and retry policy*;
the stage semantics live in the SDK. CronWorkflow + `concurrencyPolicy: Forbid` mirror A.

**Variant C — "everything-in-cluster" (GPU included).** ComfyUI, Ollama, and the VLM server also
move into the cluster as GPU workloads (D7). Rational only on a **dedicated Linux GPU node**; on
the current Windows/WSL2 box it is technically possible but the wrong trade (D7 explains exactly
why, and how the card talks to Kubernetes when it *is* the right trade).

Adoption ladder: **runner-first (PoC) → A (same box or any single node) → B (real fan-out) → C
(dedicated GPU node)**. Each rung changes *where* code runs, never *what* runs.

### D2. Topology

```
            ┌─ Kubernetes cluster (kind on WSL2 locally; any conformant cluster later) ─┐
            │  Namespace: shorts                                                        │
            │  ┌──────────────────────────┐      ┌─────────────────────────────┐        │
 CronJob ──▶│  │ A: conductor Job (1 pod) │  or  │ B: Argo Workflow (pod/stage)│        │
            │  └─────────────┬────────────┘      └──────────────┬──────────────┘        │
            │                │  reads/writes /data (PVC)        │                       │
            │  PVC `shorts-data` ◀── hostPath/local PV = the same host DATA_ROOT dir    │
            │                │                                  │                       │
            │  Service `host-gpu` (manual Endpoints → the GPU box) ◀── HTTP ────────────┘
            └────────────────┼──────────────────────────────────┼───────────────────────┘
                             ▼                                  ▼
                  host ComfyUI :8188                   host Ollama / VLM :11434
                  (owns the RTX 5070 Ti — ADR 0001; never moves into the cluster in this design)
```

- **The GPU plane stays host-owned** (ADR 0001 unchanged): pods reach it through a **`Service`
  with manual `Endpoints`** pinning the host (locally: kind's host gateway; multi-node: the GPU
  box's address), surfaced as the same `HOST_GPU_ENDPOINT` env the stages already use. Host health
  gates batch fan-out exactly as in ADR 0003 — it's an HTTP check either way.
- **Storage:** the PVC's backing store **is the host `DATA_ROOT` directory** (kind `extraMounts` →
  hostPath PV locally; a local-PV on the GPU node otherwise), mounted at the **same canonical
  mount point (`/data`) in every pod**.

### D3. The template generator (small, owned, tested)

ADR 0010 deferred a DAG generator because hand-written templates plus choreography would have made
it complex. Under this design the generator is **trivial and finally earns its keep**: it emits
the Variant-B `WorkflowTemplate` **from the stage manifests** — `id`, `inputs[]`/`outputs[]`
(→ DAG dependencies), `compute`/`resources` (→ pod resources, node selectors), `capability`
(→ env). Every step body is identical except the stage id. ~100 lines of Python + a template;
**CI regenerates and diffs** against the committed YAML (the new drift-catcher: generated ⟷
committed, replacing the old YAML ⟷ manifest eyeball check). Choreography (retries/backoff
values, lease gates) is *parameterized from the same config the conductor reads* — one source of
policy.

### D4. The path contract survives the return of pods

ADR 0015 D4's "one filesystem" honesty does not survive pods *unless paths are relative* — so the
contract is: **every artifact path stored in `job.json`/`batch.json`/stage outputs is
`DATA_ROOT`-relative** (the M0 SDK already does this — `ctx` maps declared names to run-dir
paths). Each process resolves against its **own** `DATA_ROOT` env: `/data` in pods, the WSL2 dir
on the host. ComfyUI is configured with its output dir under the host `DATA_ROOT` (ADR 0015 D4),
and the host client converts returned host-absolute paths to relative **at the API boundary**
(one function in `shared/host_client.py`, unit-tested). No other component ever sees an absolute
path. This is the single rule that makes runner-mode and cluster-mode byte-compatible on disk.

### D5. Secrets & identity

Runner-mode reads credentials from the env/file vault on the host; cluster-mode mounts the same
material as **Kubernetes `Secret`s** (YouTube/TikTok OAuth, API keys), projected to the same env
names. The ADR 0009 #10 token-age pre-flight runs unchanged (it's a stage). Nothing else changes:
exactly-once posting is ledger-based (ADR 0003 D1), not identity-based.

### D6. What each variant must prove (the smoke test)

The profile is **tested the same way the runner is**: a `make k8s-smoke` target spins **kind**,
applies the profile, and runs the **golden offline DAG with fakes** (no GPU, fixture backends)
end-to-end — Variant A as a one-off Job, Variant B through Argo — asserting the golden `posts`
record lands on the PVC. Runs locally and as a **manual/nightly CI job** (kind-in-CI is slow;
it is not in the per-commit path). The per-commit guarantee remains the shared image + offline
DAG inside it (ADR 0015 D2); the smoke test guards the k8s wrapper itself.

### D7. Variant C — everything in Kubernetes, GPU included: how the card talks to the cluster

**The mechanics (how a GPU reaches a pod).** Containers never "own" hardware — the chain is:
1. The **NVIDIA driver stays on the node OS** (it is never inside an image).
2. The **NVIDIA container toolkit** teaches the container runtime to inject `/dev/nvidia*` device
   nodes + the driver's user-space libraries (`libcuda.so` …) into a container at start.
3. The **NVIDIA device plugin** (a DaemonSet; usually installed via the **GPU Operator**, which
   also manages toolkit/driver lifecycle) advertises the card to Kubernetes as a schedulable
   resource: `nvidia.com/gpu: 1`.
4. A pod **requests** that resource (`resources.limits: {nvidia.com/gpu: 1}`); the scheduler
   places it on the GPU node, kubelet+runtime wire the devices in, and the process inside sees
   the RTX 5070 Ti exactly as a host process would.
5. So in Variant C, **ComfyUI / Ollama / the VLM become in-cluster Deployments** claiming the
   GPU; stages reach them through normal cluster `Service`s (the `host-gpu` Service of D2 simply
   re-points — nothing else in the system changes, which is the payoff of the HTTP seam).

**The three honest catches — and why C is wrong for the current box:**
- **One consumer GPU = one indivisible resource.** Kubernetes has no fractional GPU scheduling on
  consumer cards (MIG is datacenter-only; time-slicing/MPS gives no VRAM isolation). With
  ComfyUI *and* Ollama each requesting `nvidia.com/gpu: 1`, only one can ever be scheduled — which
  *enforces* never-co-resident, but turns every model swap into a **pod stop/start** (slow
  reloads, lost warm caches) instead of the cheap in-process load/unload the VRAM choreography
  (Ch.7) relies on. The alternative — sharing the device without resource requests — forfeits
  scheduling guarantees entirely. Process-level choreography on one card is simply finer-grained
  than pod-level scheduling.
- **The WSL2 layering.** On this box the chain becomes Windows driver → WSL2 `libcuda` → Docker →
  the kind node container → the pod. The GPU Operator does not manage WSL2; the toolkit must be
  hand-wired into kind nodes. Workable for an experiment, fragile as the thing a 2-week unattended
  run stands on — the exact failure surface ADR 0015 removed.
- **The Blackwell toolchain returns to images.** sm_120-matched CUDA wheels must then be pinned
  *inside* the GPU images (the containerized-toolchain problem ADR 0001 eliminated by keeping the
  GPU plane on the host).

**When C is rational:** a **dedicated Linux GPU node** (second box or this box dual-booted/
repurposed later) joined to the cluster, GPU Operator installed, ComfyUI/Ollama as GPU
Deployments with the model cache on a node-local PV, and ideally **two cards** (or accepted
pod-swap latency) so the safety/quality judges don't fight diffusion for the device. The design
above is C-ready by construction: the only diffs are the `host-gpu` Service target and GPU
resource requests on the model-server Deployments.

### D8. Honest scale boundaries (restating ADR 0010, now with the profile attached)

- **Single node → bigger single node:** config only (either variant).
- **Multi-node CPU fan-out (Variant B):** requires the artifact volume to go **RWX** (NFS) or
  object storage — the known, deliberate cost recorded in ADR 0010; the `DATA_ROOT`-relative
  contract (D4) is what keeps that swap contained to the PV layer.
- **Multiple GPU hosts:** needs a lease arbiter above per-host queues (out of scope here; the
  `Service`/`Endpoints` indirection is where it would slot).
- **The GPU into the cluster**: Variant C (D7) — rational only with a dedicated Linux GPU node;
  ADR 0001's host-owned GPU stands for the current box.

### D9. Repo layout

```
deploy/
  k8s/
    base/            # namespace, PVC (hostPath/local-PV), host-gpu Service+Endpoints, Secrets (templates)
    conductor/       # Variant A: CronJob + one-off Job (manual trigger)
    overlays/
      kind-local/    # extraMounts path, host-gateway endpoint
      prod/          # real node selectors, storage class, endpoint IPs
  argo/
    generator/       # manifest -> WorkflowTemplate generator (+ its unit tests)
    generated/       # committed output; CI diffs against regeneration (D3)
```

`make cluster-up` / `make build` (the shared image) / `make k8s-smoke` get real bodies in M7.

## Consequences

**Positive** — the k8s story is now a complete, buildable design with zero drift surface: every
cluster artifact derives from the manifests + image + config the PoC already maintains; adopting
it never forks stage semantics. The user's "Kubernetes when I want it" is a designed ladder, not
a rewrite.

**Negative / costs** — the generator + smoke test are new (small) code to own in M7; Variant B's
multi-node promise still carries the RWX storage cost (D7) — deferred knowingly, again.

## Open (tracked, for M7)

- Argo retry/backoff parameter mapping from the conductor's config (one policy source).
- Whether the kind smoke test runs nightly in CI or stays a manual gate.
- Secret rotation story beyond the pre-flight check (fine for single-operator).
