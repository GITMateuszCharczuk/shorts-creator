# ADR 0011 — Performance & optimization (quality held constant)

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0001](0001-lightened-runtime-architecture.md) (stage-batched, load-once
  topology), [ADR 0003](0003-resilience-concurrency-observability.md) (observability + idempotency),
  [ADR 0005](0005-editorial-quality-layer.md) (best-of-N + gates),
  [ADR 0008](0008-output-parity-hardening.md) (05x vision pass + the open throughput
  reconciliation), [ADR 0009](0009-content-integrity-and-account-robustness.md) (seed, API
  budgeting), [ADR 0010](0010-implementation-conventions-and-extensibility-seams.md) (the stage
  cache).
- **Touches:** spec Ch.4 (pipeline/runtime), Ch.10 (milestones + open items); ARCHITECTURE §3.
- **Origin:** an all-round performance review with one hard constraint — **no quality cuts**. The
  things that make quality (best-of-N, the vision QC pass, stills-over-AI-video, the int8/schnell
  choices) are held fixed; only throughput, GPU utilization, and cost are on the table.

## Context

The pipeline is stage-batched so each model loads once per day (ADR 0001), which is good — but the
DAG runs **strictly linear by stage**, so the GPU sits idle through every CPU stage and the CPU sits
idle through the diffusion block. The work actually splits into two resource classes that barely
compete: a **GPU/visual lane** and a **CPU/audio lane**. That idle time is the largest
quality-neutral prize. The user set the appetite as **all-round wins, revise locked decisions if
the payoff is big** — so this ADR includes one structural change plus a set of additive wins, each
adopted behind a measurement gate.

## Decision

1. **Fork the DAG into a visual lane and an audio lane (the headline change).** After `script.json`
   exists at 00b, split into:
   - **Visual lane (GPU-bound):** 01a stock → 01b FLUX → 01c LTX → 01d ESRGAN → `assets.json`
   - **Audio lane (CPU-bound):** 02 Kokoro → 03 WhisperX → 04 music

   The lanes **fork after 00b and join at 05 render**, running concurrently — the CPU produces all
   narration/captions/music while the GPU grinds the diffusion block. Each lane still
   **stage-batches internally** (model loads once), and **"never co-resident" is preserved**: the
   audio lane is pure CPU, the GPU only ever holds one visual-lane model, and the confirm-VRAM-free
   gate stays between 00b and 01b. This revises the strictly-linear ARCHITECTURE §3 ordering.

2. **Minimize GPU model swaps + RAM pre-stage.** Order the visual lane so each big model loads
   exactly once (already the intent), and while model *k* computes on the GPU, **warm model *k+1*'s
   weights from the host `models/` dir into RAM page-cache** so the VRAM load is RAM→VRAM, not
   disk→VRAM.

3. **Per-video fan-out concurrency on CPU stages.** Within 00a / 01a / 02 / 03 / 04 / 05-composite,
   the N videos are independent — run them across cores (bounded by the ADR 0009 API budgets). *(GPU
   stages stay GPU-serialized — ComfyUI processes one at a time — so the win there is load
   amortization, not parallelism.)*

4. **LLM prompt/KV-cache reuse.** The system+niche prompt is identical across the batch's videos
   *and* across the best-of-N candidates; reuse the prefill (Ollama/llama.cpp prompt cache) so 00b's
   many calls don't re-pay it.

5. **Production stage-cache.** Apply ADR 0010's `(stage, input_hash, seed)` cache in real runs, not
   just dev: a retried/partial batch or a QC-repick recomputes only what changed.

6. **Caching around the edges.** Extend the ADR 0009 stock/data caches; add a **host-RAM model
   cache** so back-to-back batches skip cold loads.

7. **Pipeline NVENC.** Encode video *k* on the GPU's encoder while the CPU composites *k+1* — NVENC
   doesn't contend with diffusion (done by render time). Minor but free.

8. **I/O hygiene.** Keep intermediates on the NVMe-backed host PVC, pass-by-path only (already no
   MinIO), compress logs — keep the artifact bus from becoming the bottleneck.

9. **Measurement-gated adoption.** Define a **per-stage + per-batch timing metric** (plugs into ADR
   0003 observability and the open throughput reconciliation, ADR 0008 #9). Establish the **M1
   baseline**, land the cheap wins (D3–D8) immediately, and adopt the structural change (D1) and any
   future risky scheduling change **only when it shows a measured win on the real box**.

## Explicitly NOT done (quality guards)

- **Post-render gates left intact — deliberately.** A "collapse 05x+05b+05c onto Qwen2.5-VL" idea
  was considered and **rejected**: it saves only one model swap per day, but the gates are the most
  quality-critical stage (account-safety + editorial), 05b/05c are text-reasoning tasks where a
  vision model is plausibly weaker, and the swap-saving isn't worth muddying the clean
  **perceive (05x) → judge (05b/05c)** separation. Keeping them split also leaves the door open to a
  genuinely independent **non-Qwen judge** later (ADR 0009 D4) — the gates today already run on the
  same Qwen family as the generator, so the collapse would not have improved independence anyway.
- **No best-of-N reduction; no dropping the vision QC pass; no stills→full-AI-video** (which is both
  slower *and* lower quality); **no sub-int8 quantization; no second GPU / multi-node; no exotic
  inference (speculative decoding)** for the PoC.

## Consequences

**Positive**
- The two heaviest time sinks (GPU diffusion, CPU audio) overlap instead of serializing — the
  biggest wall-clock win, at zero quality cost.
- Cheaper swaps, parallel CPU fan-out, and KV-cache reuse compound; partial-batch retries get cheap.

**Negative / costs**
- Lane-fork makes the DAG concurrent — more orchestration surface and a real (if bounded) chance of
  CPU/RAM contention between the lanes; the measurement gate (D9) is what keeps adoption honest.
- A few items (RAM pre-stage, NVENC pipelining) are small wins that add complexity; land them only
  if the metric shows they pay.

## Open (tracked)

- The exact **timing-metric** shape + the M1 baseline numbers.
- Lane-fork **resource bounds** (CPU/RAM headroom so the audio lane doesn't starve the host serving
  the GPU plane).
- Whether RAM pre-staging / NVENC pipelining clear the measurement bar at PoC batch sizes.
