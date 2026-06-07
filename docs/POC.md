# Proof-of-Concept Scope (authoritative current scope)

> **This document defines what we are building *now*.** Where `DESIGN.md` (architecture) or
> `STRATEGY.md` (business) describe the broader 3-niche / 4-platform vision, **this doc wins on
> scope** — it narrows that vision to a deliberately small, deeply-engineered first slice.
>
> The vision is unchanged; the PoC is the first proof that the core loop works, built well
> enough to extend by configuration rather than rewrite.

---

## 1. Why a PoC (and what it must prove)

Money is the long-term aim, but the honest economics (`research/01`, `STRATEGY §6`) say ad-share
is a months-long, volume-and-time game. So the near-term goal is **not revenue** — it is to prove,
with a solidly-engineered system, that the **end-to-end production-and-posting loop works
reliably and unattended**, on real platforms, at a quality bar we are not embarrassed by.

**Engineering quality is a first-class requirement of this PoC**, equal to the outcome: clean,
reliable, observable, reproducible, and a genuine use of the available GPU. A narrow slice built
excellently beats a broad slice built shakily — and it gives an architecture that extends to the
full vision by adding config, not by rewriting.

### Definition of done

The PoC succeeds when **all** of the following hold:

1. **Unattended operation.** A scheduled run produces a daily batch with no human in the loop
   (the QC gate is the "human replacement"); a failed stage retries/quarantines rather than
   wedging the pipeline.
2. **Quality bar.** Output videos pass the automated QC gate *and* a human spot-check would call
   them "genuinely good," not "AI slop" — real-footage-first visuals, clean narration, synced
   captions, coherent script with a real hook.
3. **Real posting.** Videos are uploaded through the **real** YouTube Data API v3 and TikTok
   Content Posting API to **real, live, new accounts** — defaulting to private/unlisted (see §5),
   with public gated only by the platform audits, not by our code.
4. **Stability.** The system runs for **~1–2 weeks** producing its daily batch without manual
   intervention, with clean logs, provenance, and no silent failures.

Revenue, monetization thresholds, and view/retention targets are explicitly **out of scope** for
the PoC's done-definition (they are the *next* phase's concern).

---

## 2. Scope

### In scope

| Dimension | Decision | Rationale |
|---|---|---|
| **Niches** | **Finance + Business** (two profiles) | Both high-RPM, both automate cleanly from real data, both avoid the true-crime legal landmine. Two niches exercise the niche-profile abstraction with two genuinely different configs. |
| **Platforms** | **YouTube Shorts + TikTok** | Exercises the multi-platform distribution path with per-platform native renders. TikTok is the only short-form leg that meaningfully pays (`STRATEGY §1`); YouTube is the easiest to stand up and the long-form upgrade path. |
| **Pipeline** | Full end-to-end (script → visuals → voice → subs → music → render → QC → distribute) | The whole loop, proven on the narrow slice. |
| **Mode** | **Auto + safety-net** | Full automation gated by the automated QC gate + phased ramp + weekly spot-audit. |
| **Posting posture** | **Private-first**, public = single config flag, audits pursued in parallel | Decouples our engineering from platform approval timelines we don't control (see §5). |
| **Cadence** | **1–2 / day / niche** (~2–4/day total), phased ramp | Well under YouTube's ~6 uploads/day quota; the "start small, prove compliance" posture the inauthentic-content policy demands (`research/04 R1`). |
| **Hardware** | Single **RTX 5070 Ti, 16 GB** (Blackwell, sm_120) | See §4 for the GPU-utilization plan and the sm_120 toolchain caveat. |

### Out of scope (deferred to later phases — architecture must not preclude)

- **True crime niche** — dropped entirely. Catastrophic, automation-incompatible defamation risk
  (`research/04 R3`: $17.5M verdict, AI-true-crime channel terminated). Not "later"; **not at all**
  in the current product as automated.
- **Facebook Reels + Instagram Reels** — deferred. Reels ad-share is pennies (`STRATEGY §1`), and
  IG content publishing needs a Business account + Meta App Review. The render stage stays
  platform-generic so adding them later is config, not rework.
- **Long-form companion videos & affiliate** — the real revenue levers (`STRATEGY §6`), deferred
  to a future phase once the PoC loop is proven.
- **Multi-account / scale-out, web UI, cloud GPU autoscaling** — out (per `DESIGN §1` non-goals).
- **Analytics feedback loop** (retention/hook ranking) — build after the core loop works
  (`STRATEGY §7`).

---

## 3. Pipeline (unchanged shape, narrowed wiring)

The architecture, stage breakdown, tooling, and licensing matrix in **`DESIGN.md §3–§9`** stand as
written. The PoC only narrows *which paths are wired and tested*:

- **Stage 0 (script):** two profiles only — `finance`, `business`. Both are **YMYL**: mandatory
  "educational, not financial advice" disclaimer, no buy/sell/price calls, on-screen source
  citations, accuracy self-check (`STRATEGY §5`, `research/04 R7/R8`).
- **Stage 1 (visuals):** real-footage-first as designed; FLUX.1-schnell fill + LTX-Video / Ken
  Burns motion + Real-ESRGAN/RIFE polish.
- **Stages 2–4 (voice/subs/music):** Kokoro-82M, WhisperX, commercial-safe music library — as
  designed.
- **Stage 5 (render):** native cuts for **YouTube + TikTok only** (no FB/IG cut yet). Finishing
  polish baked in. No foreign watermarks (`research/04 R4`).
- **Stage 5b (QC gate):** the safety-net. Must pass before any upload.
- **Stage 6 (distribute):** **YouTube Data API v3 + TikTok Content Posting API only.** AI-content
  disclosure flag set on every publish call (`research/04 R6`, non-negotiable). Private-first (§5).

Any stage/feature in `DESIGN.md` referencing true crime, tech/celebrity news, history/geopolitics,
or FB/IG is **not part of the PoC** and should be read as future vision.

---

## 4. GPU utilization plan ("use the whole 5070 Ti")

Ambition: **maximum quality within a reliable 16 GB VRAM budget**, with the GPU genuinely worked —
not a token local model. Reliability is weighted over raw parallelism.

- **Model picks (all commercial-safe, all fit 16 GB):** Qwen2.5-14B-Instruct (script), FLUX.1-schnell
  (image fill), LTX-Video (img→video), Real-ESRGAN + RIFE (upscale/interpolate), GFPGAN/CodeFormer
  (face restore), WhisperX large-v3 (alignment), Kokoro-82M (TTS).
- **VRAM choreography (the reliability rule):** big models are **never co-resident**. Each GPU
  sub-step loads → runs → evicts before the next. Image-gen and img→video run as distinct steps.
  This is why stages are serialized rather than packed — predictable VRAM beats clever contention.
- **Throughput posture:** the daily batch is small (§2 cadence), so serialized GPU work fits
  comfortably overnight. We optimize for *quality per video* and *zero OOM surprises*, not peak
  GPU occupancy.
- **sm_120 toolchain caveat (`DESIGN §2.1`):** CUDA 12.8+ and a torch `cu128` build with sm_120
  kernels are mandatory in every GPU image — pinned and documented per Dockerfile. This is the
  single most likely "doesn't work on my box" failure.
- **Post-slice experiments (not PoC-blocking):** A/B bigger models once the slice is solid —
  Wan2.1 / CogVideoX vs LTX, Qwen-32B with RAM offload, Orpheus/Chatterbox TTS.

---

## 5. Posting & the audit gate

The platform reality (`research/04 R2`): an **unaudited** YouTube project can upload but videos are
locked to **`private`**; an **unaudited** TikTok app can post only **SELF_ONLY (private)**, ≤5/day.
Public posting requires passing each platform's compliance audit (TikTok: manual review ~2–6 weeks),
and that audit scrutinizes exactly this kind of automation.

**Posture (chosen): private-first, flag to public, audits in parallel.**

- Build the full posting integration against the **real** APIs and **real new accounts**, defaulting
  to **private/unlisted** — which works immediately, no audit required.
- `public` vs `private` is a **single per-platform config flag**, not a code path rewrite.
- Pursue the YouTube API compliance audit and the TikTok Content Posting API audit **in parallel
  from day one**, declaring the real use-case honestly. Flip each platform to public as its audit
  clears.
- This makes the PoC's "real posting" success criterion satisfiable on our own timeline (real
  uploads to live accounts), while public visibility rides the platforms' approval clock.
- Disclosure: the AI-content flag is set on **every** publish call, both platforms, always
  (`research/04 R6`).

---

## 6. Engineering standards (the "not ashamed of it" bar)

These are PoC acceptance criteria, not nice-to-haves:

- **Config-driven, not hardcoded.** Niche and platform are configuration (`profiles/<niche>.yaml`);
  adding the third niche or FB/IG later is a config + small adapter, never a rewrite.
- **Idempotent, resumable stages.** Each stage is a pure function of its inputs + `job.json`; a
  retried or re-run stage is safe. Failed stages retry with backoff, then quarantine — never wedge.
- **Reproducible.** Pinned model versions, pinned CUDA/torch, pinned base images; a run is
  reconstructable from `job.json` + provenance.
- **Provenance & auditability.** Every asset records source/URL/license/fetch-date
  (`provenance.json`); every QC decision is logged. This is the evidence trail for licensing and
  the weekly spot-audit.
- **Observability.** Structured logs per stage, a per-run manifest, clear pass/quarantine signals.
  No silent failures.
- **Tested.** Schema validation on `job.json` and stage outputs; unit tests on the deterministic
  logic (script schema, music selection, render arg construction, QC checks). TDD where it fits.
- **Secrets discipline.** OAuth refresh tokens / API keys live in K8s Secrets, never committed.

---

## 7. PoC milestones

Refines `DESIGN §10` to the PoC slice:

1. **M0 — Scaffold & cluster.** Repo structure, `kind` up with GPU verified (`nvidia-smi` in a pod),
   Argo + MinIO installed, `job.json` schema + validation, CI that runs the unit tests.
2. **M1 — Vertical slice.** Stage 0 (Qwen2.5-14B) → 2 (Kokoro) → 3 (WhisperX) → 5 (ffmpeg, stills +
   Ken Burns) → a real `final.mp4` for **finance**. Proves the shape end-to-end.
3. **M2 — Visuals for real.** Stage 1 stock-first retrieval + FLUX fill + LTX img→video + upscale;
   the "not obviously AI" look dialed in.
4. **M3 — Music, polish, second profile.** Stage 4 ducking/mix, caption styling, and the **business**
   profile — proving the two-niche abstraction.
5. **M4 — Orchestration.** WorkflowTemplate + CronWorkflow, retries, MinIO artifacts, GPU scheduling,
   the phased daily batch.
6. **M5 — QC gate + distribution.** Stage 5b QC, then Stage 6 posting to YouTube + TikTok
   (private-first), disclosure flags on; audit applications submitted in parallel.
7. **M6 — Hardening & the 1–2 week run.** Provenance, accuracy checks, monitoring, quota/VRAM guards;
   then the unattended stability run that satisfies the §1 done-definition.

---

## 8. Carry-forward to the full vision (designed-in, not built)

The PoC is built so these are additive, not disruptive:

- **Third niche** → add a profile + prompts.
- **FB Reels / IG Reels** → add per-platform render cuts + distribution adapters (render stage is
  already platform-generic).
- **Long-form + affiliate** → the highest-leverage revenue work, a distinct future phase.
- **Analytics feedback loop** → close the loop on hooks/formats once data exists.
