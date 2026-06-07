# Shorts-Creator PoC — Design Specification

> **Status:** Design spec (pre-implementation). Synthesizes the locked decisions across
> `docs/POC.md` (scope), `docs/DESIGN.md` (architecture), `docs/OPTIONS.md` (tooling),
> `docs/REVIEW.md` (findings), `docs/research/01–05` (evidence), and the ADRs
> [0001 — lightened runtime](../../decisions/0001-lightened-runtime-architecture.md) and
> [0002 — recency & novelty](../../decisions/0002-recency-and-novelty-ledger.md). The full
> topology diagrams live in [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
>
> **Precedence:** the ADRs win on runtime topology; `POC.md` wins on scope. This spec is the
> single synthesized reference for implementation planning and review.
>
> **Date:** 2026-06-07

---

## Chapter 1 — Overview & definition of done

**What it is.** A free, self-hostable, Kubernetes-native (`kind`) pipeline that produces and
posts 60–90s vertical (9:16) videos for **Finance** and **Business** to **YouTube Shorts** and
**TikTok**, fully unattended.

**What the PoC must prove.** Not revenue. The goal is to prove — with a solidly-engineered
system — that the **end-to-end produce-and-post loop works reliably and unattended**, on real
platforms, at a quality bar we are not embarrassed by, built well enough to **extend by
configuration rather than rewrite**. Engineering quality (clean, reliable, observable,
reproducible, genuine GPU use) is a first-class requirement, equal to the outcome.

**Definition of done — all must hold:**

1. **Unattended operation.** A scheduled run produces a daily batch with no human in the loop
   (the QC gate is the "human replacement"); a failed stage retries/quarantines rather than
   wedging the pipeline.
2. **Quality bar.** Output passes the automated QC gate *and* a human spot-check would call it
   "genuinely good," not "AI slop" — real-footage-first visuals, clean narration, synced
   captions, a coherent script with a real hook.
3. **Real posting.** Videos upload through the **real** YouTube Data API v3 and TikTok Content
   Posting API to **real, live, new accounts**, defaulting to private/unlisted.
4. **Stability.** The system runs **~1–2 weeks** producing its daily batch without manual
   intervention — clean logs, provenance, no silent failures.

**Explicitly out of the done-definition:** revenue, monetization thresholds, view/retention
targets. Those belong to the *next* phase.

## Chapter 2 — Scope

**In scope:**

| Dimension | Decision | Rationale |
|---|---|---|
| **Niches** | **Finance + Business** (two profiles) | Both high-RPM, both automate from real data, both avoid the true-crime legal landmine; two genuinely different configs exercise the niche-profile abstraction. |
| **Platforms** | **YouTube Shorts + TikTok** | Exercises multi-platform native renders. TikTok is the only short-form leg that meaningfully pays; YouTube is the easiest to stand up. |
| **Pipeline** | Full end-to-end (research → script → visuals → voice → subs → music → render → QC → distribute) | The whole loop on the narrow slice. |
| **Mode** | **Auto + safety-net** | Automation gated by the QC gate + phased ramp + weekly spot-audit. |
| **Posting** | **Private-first**; public = a single per-platform config flag | Decouples our engineering from platform-audit timelines we don't control. |
| **Cadence** | **1–2 / day / niche** (~2–4/day), phased ramp | Well under YouTube's ~6 uploads/day; the "start small, prove compliance" posture the inauthentic-content policy demands. |
| **Hardware** | Single **RTX 5070 Ti, 16 GB** (Blackwell, sm_120) | See Chapter 7 for the GPU budget + toolchain caveat. |

**Out of scope (deferred — architecture must not preclude):**

- **True crime niche** — dropped *entirely* (not "later"). Catastrophic, automation-incompatible
  defamation risk (`research/04 R3`: $17.5M verdict; an AI true-crime channel terminated).
- **Facebook + Instagram Reels** — deferred (Reels ad-share is pennies; IG needs Business
  account + Meta App Review). The render stage stays platform-generic.
- **Long-form companions + affiliate** — the real revenue levers, a distinct future phase.
- **Multi-account / scale-out, web UI, cloud GPU autoscaling, analytics feedback loop.**

**Carry-forward (designed-in, not built):** third niche → add a profile + prompts; FB/IG → add
per-platform render cuts + distribution adapters; long-form/affiliate + analytics → future phases.

## Chapter 3 — Architecture & topology

The system splits into **two planes** (ADR 0001). The full diagrams are in
`ARCHITECTURE.md §1–§2`; this is the contract.

**Host GPU plane (bare metal — owns the card):**
- **ComfyUI server** is the *single owner* of the RTX 5070 Ti for diffusion/video/upscale/
  restore (FLUX.1-schnell, LTX-Video, Real-ESRGAN, RIFE, GFPGAN/CodeFormer). It manages model
  load/unload via its prompt queue. **No GPU is passed into `kind`** — the device-plugin and
  its sm_120 toolchain-matching-inside-containers are eliminated.
- **LLM endpoint** (Ollama / llama.cpp, Qwen2.5-14B), loaded **per batch** and **evicted**
  before any diffusion work — never a persistent GPU resident.

**Cluster control plane (`kind`, CPU only):**
- **Argo Workflows** (controller, DAG, retries, backoff, params, `CronWorkflow`, UI, artifact
  passing).
- **Stage pods** — CPU. GPU-backed stages are **thin HTTP clients** that POST a graph to host
  ComfyUI / the LLM endpoint and poll; the heavy work happens on the host.
- **One shared PVC**, host-backed (Chapter 5). No MinIO.

**Cluster ↔ host wiring (the one gotcha):** stage pods reach the host services via the **kind
network gateway**, surfaced as a fixed `Service`/`Endpoints` + a `HOST_GPU_ENDPOINT` env var
injected into GPU-client stages. A single `shared/host_client.py` owns the HTTP/poll logic. If
the host endpoint is unreachable the stage **fails the Argo step** (which retries/backs off)
rather than hanging — the host is a first-class dependency with a first-class failure state.

**Why this shape:** removes the #1 technical risk (GPU-in-kind); delegates VRAM lifecycle to a
battle-tested tool instead of bespoke code; keeps Argo's reliability primitives (retry, schedule,
lineage, UI) for free; extends to the full vision by config, not rewrite.

## Chapter 4 — Pipeline stages

Each stage = **one container image = one Argo template = a pure function of its inputs +
`job.json`**. Stages are **idempotent and resumable**; a failed stage retries with backoff then
quarantines — never wedges. GPU stages (marked `→host`) are thin clients to ComfyUI / the LLM.

The day's run is **stage-batched** (ADR 0001 / REVIEW T1): each stage fans out across the day's
2–4 videos *before* the next stage starts, so a model loads **once per stage for the whole
batch** rather than once per video. CPU stages overlap GPU work.

| Stage | Compute | Purpose | Output |
|---|---|---|---|
| **00a research/ingest** | CPU | Market data (Alpha Vantage/Yahoo/FRED) **+ recent news via free RSS, ≤3 days old**. Fetch failure = first-class DAG state. | `data.json {market, news[]}` |
| **00b script** | CPU →host LLM | Qwen2.5-14B → hook-first 60–90s script: hook variants, narration beats, on-screen captions, per-scene visual keywords, music mood, per-platform title/desc/hashtags. **YMYL:** mandatory "educational, not financial advice" disclaimer, no buy/sell/price calls, on-screen source citations, accuracy self-check. **Dedup:** query `history/ledger.jsonl`, reject/repick repeats. | `script.json` |
| **01a stock-fetch** | CPU | Real vertical clips/photos from Pexels/Pixabay/Mixkit/Coverr/Videvo (license verified, source logged). Real footage is the backbone. | `scenes/` + provenance |
| **01b image-gen** | →host ComfyUI | FLUX.1-schnell photoreal stills for the un-stockable only. | `scenes/` fills |
| **01c img2vid** | →host ComfyUI | LTX-Video (img→video on real frames) / Ken Burns. AI motion kept to short fill clips. | `scenes/` clips |
| **01d upscale-restore** | →host ComfyUI | Real-ESRGAN upscale + RIFE interpolation + GFPGAN/CodeFormer face restore on AI frames. | `assets.json` |
| **02 voice** | CPU | Kokoro-82M narration. | `narration.wav` |
| **03 subtitles** | CPU | WhisperX `int8` word-level alignment → karaoke captions. | `captions.ass/.srt` |
| **04 music** | CPU | Mood-matched strike-safe track, ducked under VO (sidechain), loudness-normalized. | `music.wav` |
| **05 render** | CPU (ffmpeg) | Compose + burn captions + mix audio + finishing polish (color grade / film grain / motion blur) → **distinct native cuts for YouTube + TikTok** (no foreign watermarks). | `renders/{youtube,tiktok}.mp4`, `thumbnail.jpg` |
| **05b QC gate** | CPU +host LLM | The safety-net (Chapter 8). Pass → continue; fail → quarantine. | `qc.json` |
| **06 distribute** | CPU | YouTube Data API v3 + TikTok Content Posting API, **idempotent**, **private-first**, **AI-disclosure flag on every call**. Append to the novelty ledger after a successful post. | post receipts |

All clips are normalized to **1080×1920**. The scene manifest (`assets.json`) plus the
`job.json` spine make any video reconstructable.

## Chapter 5 — Data contracts & storage

**Contracts first (REVIEW C2 / P0).** The stage interfaces *are* the architecture, so they are
the **first committed code artifact**, as versioned JSON Schema under `schemas/`, validated at
every stage boundary:

- **`job.schema.json`** — the spine threaded through every stage: `batch_id`, `video_id`, niche,
  profile, platform targets, per-stage status, and the run's file paths.
- **`script.schema.json`** — Stage 00b output: hook variants, narration beats, on-screen
  captions, per-scene visual keywords, music mood, per-platform metadata, claims + citations,
  disclaimer.
- **`assets.schema.json`** — Stage 01d output: the final scene manifest (one normalized clip per
  beat).
- **`provenance.schema.json`** — per asset: `source`, `url`, `license`, `fetch_date`.

**Storage — a single PVC, host-backed for durability.** The data volume is backed by a host
directory via kind `extraMounts`, so it **survives `kind delete cluster` and reboots** — not
cosmetic: cross-run dedup is only possible because the ledger persists.

```
 PVC: shorts-data  →  host dir via kind extraMounts
 └── runs/<batch-id>/
     ├── batch.json                # which videos, profiles, status
     ├── data/                     # 00a: market data + recent news (≤3d)
     └── <video-id>/
         ├── job.json  script.json  assets.json  provenance.json
         ├── scenes/  narration.wav  captions.ass/.srt  music.wav
         ├── renders/{youtube,tiktok}.mp4  thumbnail.jpg
         └── qc.json
 └── quarantine/<video-id>/        # 05b failures, kept for the weekly spot-audit
 └── history/ledger.jsonl          # append-only novelty ledger (Chapter 6)
 └── models/                       # host-mounted shared weight cache (downloaded once)
```

No MinIO (REVIEW T5). Argo passes artifacts **by path** on this shared volume.

## Chapter 6 — Freshness & novelty (ADR 0002)

**Freshness — content made from the newest data.** Stage `00a` pulls, in one step:
- **Numeric market data** (Alpha Vantage / Yahoo / FRED), and
- **Recent news** via **free RSS feeds** from reputable finance/business outlets, filtered to
  `published ≥ now − 3 days` → `data.json = {market, news:[{title,url,source,published,summary}]}`.

No paid news API (preserves the no-recurring-cost rule; a free-tier API is a later add only if
RSS coverage proves thin). **Licensing/policy:** articles are **source facts and angles →
original synthesis with on-screen citations** (already a YMYL requirement); we never republish
article text and skip paywalled sources. A fetch failure is a first-class DAG state.

**Novelty — don't repeat ourselves.** An append-only `history/ledger.jsonl` on the durable
volume records one entry per produced video:

```
{ id, date, niche, topic, title, hook, source_urls:[...], keywords:[...], embedding: null }
```

Stage `00b` queries the ledger before committing a topic and **rejects/repicks** if any
`source_url` was already used **or** keyword/title overlap with recent records exceeds a
threshold. This is the **keyword + source-URL** tier — no model, robust, debuggable. The
`embedding` field is **reserved** so a cosine-similarity tier (small local embedding model,
catches reworded duplicates) layers on **post-M1 without schema rework**. The ledger doubles as
the **compliance lever** against repetitious/inauthentic-content demotion.

**Open (tracked):** the per-niche RSS source list; the overlap threshold + how a *starved* batch
behaves (widen window / relax / skip); the embedding model for the post-M1 tier.

## Chapter 7 — GPU / VRAM & throughput

**Hardware:** one **RTX 5070 Ti, 16 GB** (Blackwell, **sm_120**). The single most likely "doesn't
work on my box" failure is the toolchain: **CUDA 12.8+ and a torch `cu128` build with sm_120
kernels are mandatory** in the host GPU environment (ComfyUI + LLM); older wheels fail with
`no kernel image is available for execution on the device`. Pin and document it.

**Model budget (all commercial-safe, all fit 16 GB *individually*):**

| Model | Role | ~VRAM |
|---|---|---|
| Qwen2.5-14B (Q4/Q5) | script | ~9–11 GB |
| FLUX.1-schnell | image fill | ~12 GB |
| LTX-Video | img→video | ~14 GB |
| Real-ESRGAN + RIFE | upscale/interp | ~4–6 GB |
| GFPGAN/CodeFormer | face restore | ~3 GB |
| WhisperX large-v3 | subtitle align | CPU (`int8`) |
| Kokoro-82M | TTS | CPU / ~1 GB |

**Never-co-resident rule — structurally enforced** by batch ordering, not by hope:
`Qwen → evict → FLUX → evict → LTX → evict → ESRGAN/RIFE/GFPGAN`. ComfyUI's queue serializes the
diffusion stages; the LLM endpoint is up only during 00b. **No two heavy models are ever
resident together** — that is the OOM cliff.

**Throughput:** stock-heavy path ≈ **12–25 min/video**; the PoC's 2–4/day fits comfortably
overnight. The #1 throughput multiplier is **stage-batching** (amortizes model load/unload across
the batch); CPU/GPU overlap (ffmpeg + WhisperX on CPU while the GPU does the next batch's clips)
is the #2.

**Choke points — what a 16 GB 5070 Ti *cannot* do (the binding constraints):**
- **Full-length AI video.** Generating the whole 60–90s as img2vid collapses throughput to
  ~2–4/day *or worse* and looks "AI." **Mitigation (architectural, not tuning):** real-footage-
  first; AI motion is short fill (<20–30% of runtime).
- **Two heavy models at once** → OOM. Enforced away by serialization.
- **Wan2.2-14B** — borderline at 16 GB, too slow for batch. **CogVideoX-5B** — 8-bit only,
  minutes/clip (quality fallback for hero shots, not the default).
- **HunyuanVideo (original, ~60–80 GB)** and **Mochi-1 (80 GB+)** — out of reach.
- **SD 3.5 Large** — ~18 GB FP16, VRAM pressure; not worth it on 16 GB.
- **FLUX.1-dev** — non-commercial (excluded regardless of VRAM).

**Upgrade path (cost order):** more system RAM (enables offload + bigger batch queues) → a 24 GB
card (removes most time-sharing, unlocks Wan2.2-14B/CogVideoX-5B, ~2× throughput) → second GPU /
opportunistic spot cloud (only past ~30/day).

## Chapter 8 — Reliability, observability & operations

**Reliability**
- **Idempotent, resumable stages.** Each stage is a pure function of its inputs + `job.json`; a
  retried or re-run stage is safe.
- **Retry → quarantine, never wedge.** Failed stages retry with backoff, then quarantine the
  video and continue the batch.
- **Stage 6 exactly-once.** Posting is side-effecting; retries must **never double-post**. A
  **posted-state ledger / idempotency key** per (video, platform) gates every upload. *(Promoted
  from REVIEW open item — first-class design element.)*
- **Host dependency as a first-class failure state.** If host ComfyUI / the LLM endpoint is
  unreachable, the GPU-client stage fails the Argo step (→ retry/backoff), it does not hang.

**The QC gate (Stage 5b) — the safety-net / "human replacement"**
- **Checks:** second-pass LLM fact/sanity + hallucination flag; claims/profanity filter;
  **finance/business YMYL** check (disclaimer present, no buy/sell calls, sources cited); render
  integrity (no dead audio, no black frames, no clipped loudness).
- **Outcome:** pass → distribute; fail → quarantine + log for the weekly spot-audit.
- The second-pass LLM uses the **same host endpoint + eviction rule** as 00b.
- *(Open: concrete pass/fail thresholds; the quarantine + spot-audit subsystem.)*

**Observability**
- Structured (JSON) logs per stage; a per-batch (`batch.json`) and per-video (`job.json`)
  manifest; clear pass/quarantine signals; **no silent failures**. Run state is visible in the
  Argo UI. *(Open: where logs/metrics land beyond stdout + Argo UI.)*

**Operations — run flow**
- **One-time setup (multi-step):** `make host-up` (ComfyUI + models + LLM) · `make cluster-up`
  (kind + Argo + the host-backed PVC; *no GPU device-plugin*) · `make build` (build + `kind load`
  stage images) · `make wire` (verify pods reach the host endpoint).
- **Per run (light / hands-off):** `make submit-batch PROFILES=finance,business` · `make dry-run`
  (stage metadata, post nothing) · or the `CronWorkflow` fires the daily batch automatically.

**Testing (`POC §6`)**
- Schema validation on `job.json` and every stage output.
- Unit tests on the deterministic seams: script-schema adherence, music selection, render-arg
  construction, QC heuristics, and dedup matching. TDD where it fits.

## Chapter 9 — Compliance & licensing

**Licensing — commercial-safe spine (Apache/MIT) only.** Qwen2.5-14B (Apache-2.0), Pexels/
Pixabay/Mixkit/Coverr/Videvo (per-asset license verified), FLUX.1-schnell (Apache-2.0),
LTX-Video (verify the >$10M-ARR clause — we are far under), Kokoro-82M (Apache-2.0), WhisperX
(BSD/MIT + Whisper MIT), music from YouTube Audio Library / Pixabay Music, ffmpeg (LGPL/GPL).
**Excluded (❌ non-commercial/restricted):** FLUX.1-dev, XTTS/Coqui, MusicGen/AudioCraft, Stable
Video Diffusion. Every asset records provenance (`provenance.json`) as the evidence trail.

**Copyright-strike avoidance.** Never ingest copyrighted footage/music/images. News articles are
used as **facts + citations**, never republished; paywalled sources skipped.

**Platform policy (separate from copyright):**
- **YMYL (finance/business).** Mandatory "educational, not financial advice" disclaimer; **no
  buy/sell/price calls**; on-screen source citations; accuracy self-check. Kept strictly
  educational/non-advisory.
- **Inauthentic / repetitious content.** Mitigated by per-video variety (the novelty ledger,
  Chapter 6) + the quality bar + the phased cadence ramp.
- **AI-content disclosure.** The disclosure flag is set on **every** publish call, both
  platforms, always — non-negotiable.

**Posting posture — private-first, public via a flag, audits in parallel.** An unaudited YouTube
project uploads **private**-only; an unaudited TikTok app posts **SELF_ONLY**, ≤5/day. We build
against the **real** APIs and **real new accounts**, defaulting private/unlisted (works
immediately, no audit). `public` vs `private` is a **single per-platform config flag**. The
YouTube + TikTok compliance audits are pursued **in parallel from day one**, declaring the
use-case honestly; each platform flips to public as its audit clears.

**True crime is dropped entirely** — catastrophic, automation-incompatible defamation risk.

## Chapter 10 — Milestones & open decisions

**Milestones (refines `POC §7` to the lightened architecture):**

| M | Goal |
|---|---|
| **M0** | Scaffold & cluster: repo structure, `kind` up, **host GPU verified** (ComfyUI + LLM reachable from a pod — *not* GPU-in-kind), Argo installed, `job.json` schema + validation, CI running the unit tests. |
| **M1** | Vertical slice: `00a → 00b (Qwen) → 02 (Kokoro) → 03 (WhisperX) → 05 (ffmpeg, stills + Ken Burns)` → a real `final.mp4` for **finance**. Proves the shape end-to-end. |
| **M2** | Visuals for real: `01a` stock-first + `01b` FLUX fill + `01c` LTX img→video + `01d` upscale/restore — the "not obviously AI" look dialed in. |
| **M3** | Music, polish, **business** profile — proving the two-niche abstraction. |
| **M4** | Orchestration: `WorkflowTemplate` + `CronWorkflow`, retries, artifacts, **stage-batching**, the phased daily batch. |
| **M5** | QC gate (`05b`) + distribution (`06`) to YouTube + TikTok, private-first, disclosure flags on; platform audits submitted in parallel. |
| **M6** | Hardening + the **1–2 week unattended run** that satisfies the Chapter 1 definition of done. |

**Open decisions (tracked):**

1. **Contracts (P0).** Write `schemas/{job,script,assets,provenance}.schema.json` *before* stage
   code — they are every stage's interface.
2. **Stage 6 idempotency** — the posted-state ledger / idempotency-key design (Chapter 8).
3. **Stage 5 render differentiation** — what concretely differs per platform (caption style /
   hook / length / sound), so YouTube and TikTok cuts aren't a penalized dupe re-encode.
4. **Stage 5b QC** — concrete pass/fail thresholds + the quarantine/spot-audit subsystem.
5. **ADR 0002 opens** — per-niche RSS source list; topic-overlap threshold + starved-batch
   behavior; embedding model for the post-M1 similarity tier; optional free-tier news API.
6. **Observability backend** — where logs/metrics land beyond stdout + the Argo UI.
7. **Post-M1 A/B (non-blocking)** — LTX vs Wan2.1/CogVideoX; Kokoro vs Orpheus/Chatterbox;
   FLUX-schnell vs photoreal SDXL/SD3.5; Qwen-32B with RAM offload.

---

*End of specification. Topology diagrams: [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
Decision records: [`docs/decisions/`](../../decisions/).*

