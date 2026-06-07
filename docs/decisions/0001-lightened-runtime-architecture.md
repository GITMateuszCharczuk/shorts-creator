# ADR 0001 — Lightened runtime architecture (host GPU + thin k8s)

- **Status:** Accepted (2026-06-07)
- **Supersedes:** the GPU-in-kind / MinIO / monolithic-Stage-1 runtime described in
  `DESIGN.md §2–§3, §9` and `OPTIONS.md §L/§M`.
- **Resolves (from `REVIEW.md`):** T1, T2, T3, T4, T5, the Stage-1 decomposition (Part 3),
  and the Stage-0 data-fetch split.
- **Authoritative artifact:** `ARCHITECTURE.md` (the runtime blueprint + diagrams).

This is the first entry in the ADR log `REVIEW.md` C1 recommended — the single place a
decision and its supersessions live. `DESIGN`/`OPTIONS` should be read as *tooling* truth;
where they describe the *runtime topology* they are superseded by this ADR.

---

## Context

`REVIEW.md` Part 2 raised five unreconciled runtime decisions (T1–T5) plus a per-service
finding that Stage 1 bundled 4+ GPU model lifecycles into one opaque container. The PoC's
**definition of done is reliability** (`POC §1`), and the proposed platform was the largest
operational surface available for 2–4 videos/day on a single node:

- **GPU-in-kind** via the NVIDIA device-plugin — the corpus's *own* "primary technical
  risk" (`DESIGN §11.1`, `OPTIONS §M`).
- **MinIO *and* a shared PVC** — two storage systems for one single-node job (`REVIEW T5`).
- A **persistent Ollama Deployment** pinning VRAM, in direct conflict with the "never
  co-resident" rule (`REVIEW T2`).
- **Bespoke per-stage diffusion containers**, hand-writing the VRAM load/unload lifecycle
  that `research/03 §7.2` says ComfyUI already solves (`REVIEW T4`).

We evaluated three runtime shapes:

| | ① Keep k8s, lighten | ② Full heavy (status quo) | ③ Lean, drop k8s |
|---|---|---|---|
| k8s-native (extends to full vision) | ✅ | ✅ | ❌ rebuild at scale-up |
| Reliability primitives (retry/schedule/DAG/UI/lineage) | ✅ from Argo | ✅ from Argo | ❌ hand-written |
| Dodges GPU-in-kind (the #1 risk) | ✅ | ❌ | ✅ |
| Managed VRAM lifecycle | ✅ ComfyUI | ❌ bespoke | ✅ ComfyUI |
| Redundant storage (MinIO) | ✅ dropped | ❌ kept | ✅ none |
| Bespoke orchestration to own | ⚠️ some YAML | most (CUDA imgs) | most (from scratch) |

Option ② is **dominated** — it keeps both the #1 risk and the redundant storage with no
benefit over ①. The real trade was **① vs ③**: ③ is fastest to first video but throws away
the k8s-native architecture the full vision needs and forces a re-build of the orchestration
layer at scale-up. ① keeps the architecture we carry forward while removing the parts that
were pure cost.

## Decision

Adopt **option ①: keep Argo Workflows on `kind`, but move all heavy GPU work to a
host-side ComfyUI service and collapse storage to a single PVC.** Concretely:

1. **The host owns the GPU.** A **ComfyUI** server runs on the host (outside the cluster)
   and is the single owner of the RTX 5070 Ti for diffusion/video/upscale/restore
   (FLUX.1-schnell, LTX-Video, Real-ESRGAN, RIFE, GFPGAN/CodeFormer). It manages model
   load/unload via its prompt queue. **No GPU is passed into kind** — the device-plugin and
   its sm_120 toolchain matching inside containers are eliminated.

2. **The LLM is a host-side, per-batch endpoint.** Qwen2.5-14B (Ollama / llama.cpp) runs on
   the host, loaded once per batch to generate *all* scripts, then **evicted** before any
   diffusion work. It is never a persistent GPU resident. (Resolves **T2**.)

3. **The cluster is the CPU control plane.** Argo (controller, DAG, retries, params,
   `CronWorkflow`, UI, artifact passing) and all CPU stages run in `kind`. The GPU-backed
   stages are **thin CPU client pods** that POST a graph to host ComfyUI / the LLM endpoint
   and poll for results — the GPU work happens on the host.

4. **Single shared PVC, no MinIO.** Run workdirs, the `job.json` spine, provenance, and the
   quarantine store live on one PVC. Argo passes artifacts by path on the shared volume.
   (Resolves **T5**.)

5. **Stage 1 is decomposed** into `01a stock-fetch` (CPU) → `01b image-gen` (FLUX) →
   `01c img2vid` (LTX/Ken Burns) → `01d upscale-restore` (ESRGAN/RIFE/GFPGAN) — one model
   per sub-stage, each a clean load/run/evict with independent retry. (Resolves **Stage-1
   finding**; enables T1.)

6. **Stage 0 splits out data-fetch.** `00a data-fetch` (Alpha Vantage / Yahoo / FRED) is a
   first-class DAG step ahead of `00b script`, so a fetch failure is a visible state, not a
   hidden failure mode inside scripting. (Resolves **Stage-0 finding**.)

7. **Stage-batched orchestration.** The `CronWorkflow` runs one **batched** DAG per day:
   each stage fans out across the day's 2–4 videos so the LLM loads once for all scripts,
   ComfyUI loads FLUX once for all images, LTX once for all clips, etc. Per-video model
   reload churn is amortized. (Resolves **T1**; this is the architecture we keep toward the
   research's 15/day target.)

Light audio/subtitle work (Kokoro TTS, WhisperX `int8`) runs **CPU-side in-cluster** to keep
the GPU-contention surface minimal; both are CPU-viable per `research/03 §4, §6`. They can be
promoted to the host GPU later if quality/speed demands it (Post-M1 A/B). Render stays
ffmpeg/`libx264` in-cluster, with NVENC available as a host-side encode upgrade.

## Consequences

**Positive**
- The #1 technical risk (GPU-in-kind) is removed outright.
- VRAM lifecycle is delegated to a battle-tested tool instead of bespoke code — the
  riskiest code we'd otherwise own.
- One storage system, fewer moving parts to deploy and debug.
- Argo still provides retries, scheduling, lineage, and a UI for free; the architecture
  extends to the full vision by config, not rewrite.
- The "never co-resident" rule is now **structurally enforced** by batch ordering + a
  single GPU owner, not by hope.

**Negative / the costs we accept**
- **A host dependency outside the cluster.** If host ComfyUI / the LLM endpoint is down, the
  pipeline stalls. The host is now a first-class operational component.
- **The cluster↔host boundary** must be wired once (pods reach host services over the kind
  network gateway) — the most common "why can't my pod reach it" gotcha. Documented in
  `host/README.md` and `ARCHITECTURE.md §6`.
- **Two tools to learn:** Argo workflow YAML *and* ComfyUI's API/graph format.
- **Slightly less portable** than a pure-container approach — the GPU half is not fully
  containerized, so "works on my host" risk creeps back at the host boundary.

**Setup vs. per-run (explicit):** this trades a heavier *one-time* setup (stand up ComfyUI +
models on the host, bring up kind+Argo+PVC, wire the boundary) for a light *per-run*
experience — submitting a batch stays effectively one command, and the `CronWorkflow` makes
the steady state hands-off.

## Alternatives considered

- **② Full heavy (status quo):** rejected — dominated by ①; keeps the #1 risk and MinIO
  with no compensating benefit.
- **③ Lean, drop k8s (Prefect/ComfyUI, thin Python orchestrator):** rejected — fastest to
  first video, but abandons the k8s-native architecture the full vision needs and forces an
  orchestration-layer rebuild at scale-up. Reconsider only if Argo's YAML maintenance ever
  outweighs what it buys (`research/03 §7.1` keeps Prefect as a legitimate fallback).

## Still open (tracked, not closed by this ADR)

- **C2** — `job.json` / `script.json` / `assets.json` / `provenance.json` as versioned JSON
  Schema. These are the stage contracts and should be the first committed code artifact.
- **Stage 5** per-platform render differentiation spec; **Stage 5b** QC thresholds +
  quarantine/spot-audit subsystem; **Stage 6** idempotency / posted-state ledger.
