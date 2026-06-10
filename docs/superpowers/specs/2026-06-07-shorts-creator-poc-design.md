# Shorts-Creator PoC — Design Specification

> **Status:** Design spec (pre-implementation). Synthesizes the locked decisions across
> `docs/POC.md` (scope), `docs/DESIGN.md` (architecture), `docs/OPTIONS.md` (tooling),
> `docs/REVIEW.md` (findings), `docs/research/01–05` (evidence), and the ADRs
> [0001 — lightened runtime](../../decisions/0001-lightened-runtime-architecture.md),
> [0002 — recency & novelty](../../decisions/0002-recency-and-novelty-ledger.md),
> [0003 — resilience, concurrency & observability](../../decisions/0003-resilience-concurrency-observability.md),
> [0004 — commercial posture & account-safety](../../decisions/0004-poc-commercial-posture-and-account-safety.md),
> [0005 — editorial quality layer](../../decisions/0005-editorial-quality-layer.md), and
> [0006 — algorithm-fit & format tuning](../../decisions/0006-algorithm-fit-and-format-tuning.md), and
> [0007 — format-aware layout templates](../../decisions/0007-format-aware-layout-templates.md), and
> [0008 — output-parity hardening](../../decisions/0008-output-parity-hardening.md), and
> [0009 — content integrity & account robustness](../../decisions/0009-content-integrity-and-account-robustness.md), and
> [0010 — implementation conventions & extensibility seams](../../decisions/0010-implementation-conventions-and-extensibility-seams.md), and
> [0011 — performance & optimization](../../decisions/0011-performance-and-optimization.md), and
> [0012 — M0 build contract & acceptance criteria](../../decisions/0012-m0-build-contract.md), and
> [0013 — Windows host support (WSL2)](../../decisions/0013-windows-host-support-wsl2.md).
> The full topology diagrams live in [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
>
> **Precedence:** the ADRs win on runtime topology; `POC.md` wins on scope. This spec is the
> single synthesized reference for implementation planning and review.
>
> **Date:** 2026-06-07

---

## Chapter 1 — Overview & definition of done

**What it is.** A free, self-hostable, **runner-first** pipeline (single-box Python conductor;
**Kubernetes-deployable by profile** — ADR 0015) that produces and
posts **per-format-length** vertical (9:16) videos for **Finance** and **Business** to **YouTube
Shorts** and **TikTok**, fully unattended. Length is set **per format** (ADR 0006): punchy formats
run **~20–35s** for completion/attention, depth formats **~61–90s (over 1 min)** to stay
TikTok-monetization-eligible. Two lanes, chosen per format; the rolling-window mix is
**phase-dependent**: the **PoC default is reach-heavy (~80/20)** — TikTok public posting is
audit-gated to SELF_ONLY and YouTube Shorts pay volume-led, so the **~60% ≥61s monetization tilt
activates only at TikTok-audit + YPP eligibility** (ADR 0006 D2 as amended) — superseding the flat
60–90s rule.

**What the PoC must prove.** Not revenue. The goal is to prove — with a solidly-engineered
system — that the **end-to-end produce-and-post loop works reliably and unattended**, on real
platforms, at a quality bar we are not embarrassed by, built well enough to **extend by
configuration rather than rewrite**. Engineering quality (clean, reliable, observable,
reproducible, genuine GPU use) is a first-class requirement, equal to the outcome.

**Definition of done — all must hold:**

1. **Unattended operation.** A scheduled run produces a daily batch with no human in the loop.
   The always-on automated **account-safety gate** (Stage 05b, ADR 0004) is the durable
   "human replacement"; a failed stage retries/quarantines rather than wedging the pipeline.
   *(During the initial **ramp** a human approves each post on top of the gate — ADR 0004 D2;
   the unattended run that satisfies this clause happens **after** the ramp.)*
2. **Quality bar — owned and enforced.** Output passes the automated **safety gate (05b)** *and*
   the automated **creative-QC quality gate (05c, ADR 0005)** *and* a human spot-check would call
   it "genuinely good," not "AI slop" — real-footage-first visuals, clean narration, synced
   captions, a coherent script with a real hook, **and an original, non-obvious point of view** (not
   a generic template fill). The creative-QC gate is what makes this clause *enforceable* rather than
   aspirational: a boring-but-safe video — or a correct-but-generic one — is quarantined, not posted.
   The **original-insight** criterion is first-class because under the 2026 inauthentic-content policy
   it is a **monetization-survival** property, not only an aesthetic one (ADR 0014 D1).
3. **Real posting.** Videos upload through the **real** YouTube Data API v3 and TikTok Content
   Posting API to **real, live, new accounts**, defaulting to private/unlisted.
4. **Stability.** The system runs **~1–2 weeks** producing its daily batch without manual
   intervention — clean logs, provenance, no silent failures.

**Explicitly out of the done-definition (ADR 0004 D1):** this PoC proves the **engineering
loop** only — it **deliberately does not validate commercial viability**. Revenue,
monetization thresholds, and view/retention targets belong to the *next* phase. "Done" must
not be read as "this makes money." *(To still earn a minimum real-world signal, ADR 0004 D4
runs ≥1 genuinely **public** account per platform alongside the private-first ones. **Honest
caveat (ADR 0009):** an unaudited TikTok app can only post **SELF_ONLY**, so the public signal
**leans on YouTube** — TikTok's public signal is best-effort and **audit-gated**, and may not land
within the PoC.)*

**Honest ceiling — what "genuinely good" means and doesn't (ADR 0008).** The bar is *"a human
would call this a genuinely good **faceless** channel,"* **not** *"indistinguishable from a top
personality creator."* Three ceilings are accepted by design: (1) **faceless + small-TTS** — no
on-camera presence and bounded vocal emotion, a notch below charismatic hosts — **actively
narrowed, not just accepted: the M3 expressive-voice gate, the brand mascot, and the opinionated
persona stances (ADR 0017 D1/D3/D6) are the mitigation; an avatar layer is the recorded future
ceiling-breaker**; (2) **no trending-
audio jacking** — the strike-safe music rule (Ch.9) structurally blocks riding trending commercial
sounds, a real TikTok reach cost we trade for account safety; (3) **bounded humor / hot-takes /
lived experience** — LLM scripting under YMYL stays educational and third-person; (4) **no automated
community engagement** — unattended and faceless, the pipeline can't reply to comments, so it forgoes
the creator-reply share of first-hours engagement velocity (ADR 0014 D4). These are known limits, not
surprises.

## Chapter 2 — Scope

**In scope:**

| Dimension | Decision | Rationale |
|---|---|---|
| **Niches** | **Finance + Business** (two profiles) | Both high-RPM, both automate from real data, both avoid the true-crime legal landmine; two genuinely different configs exercise the niche-profile abstraction. |
| **Platforms** | **YouTube Shorts + TikTok** | Exercises multi-platform native renders. TikTok is the only short-form leg that meaningfully pays; YouTube is the easiest to stand up. |
| **Pipeline** | Full end-to-end (research → script → visuals → voice → subs → music → render → QC → distribute) | The whole loop on the narrow slice. |
| **Mode** | **Auto + safety-net** | Automation gated by the QC gate + phased ramp + weekly spot-audit. |
| **Posting** | **Private-first**; **≥1 public account per platform** (ADR 0004 D4); public = a single per-platform config flag | Decouples engineering from audit timelines we don't control, while still earning a minimum reach/retention signal. |
| **Cadence** | **starts ~1 / day / niche, ramps to 1–2** (~2–4/day ceiling), phased | Well under YouTube's ~6 uploads/day. Cadence is an **enforcement-risk knob**, not just throughput (ADR 0014 D2): the ramp **starts at the low end** and only widens once original-insight output (DoD clause 2) has a track record — fewer, denser, distinctly-original uploads beat volume under the 2026 inauthentic-content policy. |
| **Hardware** | Single **RTX 5070 Ti, 16 GB** (Blackwell, sm_120) | See Chapter 7 for the GPU budget + toolchain caveat. |

**Out of scope (deferred — architecture must not preclude):**

- **True crime niche** — dropped *entirely* (not "later"). Catastrophic, automation-incompatible
  defamation risk (`research/04 R3`: $17.5M verdict; an AI true-crime channel terminated).
- **Facebook + Instagram Reels** — deferred (Reels ad-share is pennies; IG needs Business
  account + Meta App Review). The render stage stays platform-generic.
- **Long-form companions + affiliate** — the real revenue levers, a distinct future phase.
- **Multi-account / scale-out, web UI, cloud GPU autoscaling, analytics feedback loop.**

Each **niche profile** (`profiles/*.yaml`) carries not just prompts but an **editorial persona /
point of view** the 00b model writes *in* (ADR 0005 D9) — made concrete by ADR 0017 D3 as
**required fields**: a **named stance list** (positions the channel argues from), a
**catchphrase** (rotated through the end-card/CTA), and **recurring series** (≥1 per niche,
schedule-aware in the batch planner — ADR 0017 D5) — and a **brand kit** (palette, font, logo
bug, lower-third + citation-chip templates, thumbnail/cover template, **a brand mascot**
(ADR 0017 D6), **+ a channel-styled
animated engagement-CTA bump** — ADR 0005 D10) — so variety comes from *what the channel thinks*,
not only which template it filled, and 50 videos read as one channel rather than a content farm.
The CTA's second verb is the natural per-platform delta (`youtube`→Subscribe+bell,
`tiktok`/`instagram`→Follow), drawn at a **seeded constrained-random mid-roll slot** (never the
hook or outro) so placement varies without ever stepping on the moments that carry the video.
A separate **closing end-card** then makes the explicit ask with a config-driven **FOMO follow**
line (default *"Follow — the algorithm only shows us once"*; ADR 0006), placed so it doesn't break
the seamless loop.

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

**Control plane — the Python conductor (ADR 0015; supersedes the kind/Argo executor):**
- **The runner** (`shared/runner.py`, the M0 conductor promoted to production): stage **metadata
  manifests are the single source of orchestration truth** — topology, the content-addressed
  cache, `pending→running→done/quarantined` status transitions, schema validation at every
  boundary, retries/timeouts, per-video failure domains, and the ADR 0011 lane-fork/fan-out as
  runner concurrency. All of it is **plain Python exercised by the GPU-free CI on every commit** —
  the choreography that guards the unattended run is tested code, not YAML.
- **Stages** are CPU processes the runner executes; GPU-backed stages are **thin HTTP clients**
  that POST to host ComfyUI / the LLM endpoint over **localhost** and poll. A single
  `shared/host_client.py` owns the HTTP/poll logic; an unreachable host **fails the stage** (the
  runner retries/backs off) rather than hanging.
- **One filesystem, one `DATA_ROOT`** (ADR 0015 D4): no pods → no host↔pod path split. The
  Chapter 5 layout roots at a single env var; **ComfyUI's output dir is configured under
  `DATA_ROOT`** so generated assets are immediately addressable with no translation step.
- **Scheduling:** a **systemd timer inside the WSL2 distro** (ADR 0013/0015) triggers the nightly
  batch; a **run lockfile** replaces Argo's `concurrencyPolicy: Forbid`; Windows Task Scheduler is
  only the WSL boot/keep-alive trigger.

**Kubernetes is a deployment profile, not the runtime (ADR 0015 D2):** one **CI-built shared
image** (whole repo; entrypoint selects a stage or the runner) is continuously proven by running
the offline DAG inside it — so "production-deployable" is a tested property. The deferred Argo
profile (`deploy/argo/`, post-PoC, if multi-box scale demands it) wraps the same manifests in dumb
one-line templates; choreography never lives in YAML. **The full profile is designed in
[ADR 0015a](../../decisions/0015a-kubernetes-argo-deployment-profile.md)** — a three-rung ladder
(conductor-as-CronJob → Argo per-stage fan-out → everything-in-cluster incl. the GPU via the
device plugin, rational only on a dedicated Linux GPU node) with the `DATA_ROOT`-relative path
contract, the manifest→template generator, and a kind smoke test; building it is optional
milestone **M7**.

**Why this shape:** removes the #1 technical risk (GPU-in-kind) *and* the #2 operational risk
(an untested YAML control plane on kind+WSL2 guarding a 2-week unattended run); the conductor's
reliability primitives are owned, unit-tested code; the same stage contracts lift onto a cluster
by config, not rewrite.

## Chapter 4 — Pipeline stages

Each stage = **one declared manifest = a pure function of its inputs + `job.json`**, executed by
the conductor (ADR 0015; the deferred k8s profile wraps the same manifests in one shared image).
Stages are **idempotent and resumable**; a failed stage retries with backoff then
quarantines — never wedges. GPU stages (marked `→host`) are thin clients to ComfyUI / the LLM.

The day's run is **stage-batched** (ADR 0001 / REVIEW T1): each stage fans out across the day's
2–4 videos *before* the next stage starts, so a model loads **once per stage for the whole
batch** rather than once per video.

**The run is also lane-forked for throughput (ADR 0011).** Past 00b the DAG splits into a
**visual lane** (GPU-bound: 01a→01b→01c→01d) and an **audio lane** (CPU-bound: 02→03→04) that run
**concurrently and rejoin at 05** — narration/captions/music are built on the CPU while the GPU
grinds diffusion, overlapping the two heaviest time sinks at zero quality cost. "Never co-resident"
still holds (the audio lane is CPU-only; the GPU holds one visual model at a time). Within stages,
CPU work fans out **per-video across cores**, the LLM **reuses its prompt/KV-cache** across the
batch + best-of-N candidates, and the `(stage, input_hash, seed)` **stage-cache** (ADR 0010) makes
partial-batch retries cheap. The table below is *dependency* order; the lane split is *scheduling*
order. Quality-critical stages are **deliberately not optimized** — the post-render gates 05x/05b/05c
stay split (perceive→judge), and best-of-N / the vision pass / stills-over-AI-video are untouched.

| Stage | Compute | Purpose | Output |
|---|---|---|---|
| **00a research/ingest** | CPU | Market data — **FRED/stooq for daily series; Alpha Vantage reserved for quotes only** (ADR 0009 #8: 25 req/day has no headroom across two niches) — **+ recent news via free RSS, ≤3 days old**. **API budgeting + local cache** (ADR 0009: free tiers are tight — Alpha Vantage ~25 req/day, Pexels/Pixabay hourly caps — so identical queries dedup within a batch, market pulls cache; a tripped budget is a first-class WARN/degrade, not a silent throttle). **`news_reaction` requires ≥2-source corroboration** (or source-reliability weighting) before a story commits; uncorroborated → lower-confidence or skip via the starvation ladder. Fetch failure = first-class DAG state. | `data.json {market, news[]}` |
| **00b script** | CPU →host LLM | Qwen2.5-14B writing **in the channel persona** (ADR 0005 D9) → **selects + rotates a format template** (Chapter 6) → emits a **treatment** (thesis/angle/tone, per-beat visual motif, energy curve — the through-line every later stage renders against) → **best-of-N** scripts, **judge picks the winner** (ADR 0005 D1/D2) — and the winner must **clear a provisional script-time floor or the video quarantines here**, before any GPU work (ADR 0016 D3; the authoritative floor stays 05c). Output: a first-class **hook composite** {spoken, on-screen text, first-frame visual, ≤2s}, narration beats with **prosody + emphasis markup**, on-screen captions with **emphasis-word tags**, per-beat visual motif, music **mood+energy**, a **primary keyword** (for caption/on-screen/spoken placement) and the **per-format target length** (~20–35s reach / ~61–90s monetization — ADR 0006) with **content sized to the lane** (e.g. top-3 in reach vs top-7–10 in monetization — ADR 0008), per-platform title/desc/hashtags. **YMYL:** mandatory disclaimer, no buy/sell/price calls, on-screen citations, accuracy self-check. **Numeric grounding (ADR 0009):** every cited figure carries a **provenance pointer into `data.json`** (`{value, source_ref}`); a **deterministic** check — not the LLM — rejects/repicks any number with no matching source or an out-of-tolerance value. **Seed (ADR 0009):** consumes the per-video seed from `job.json` so best-of-N is reproducible on re-run. **Dedup:** `history/ledger.jsonl` (cross-run) **+ reserve the pick in `batch.json`** (intra-batch — ADR 0003 D5). Optional affiliate fields (ADR 0004 D5). | `script.json` (+ `treatment`) |
| **01a stock-fetch** | CPU | Real vertical clips/photos from Pexels/Pixabay/Mixkit/Coverr/Videvo (license verified, source logged). **Pulls N candidates per beat, ranks by image-text similarity (e.g. CLIP) against the beat's visual motif, dedups against clips used in other batch videos + the ledger** (ADR 0005 D5) — below-threshold beats fall through to 01b/01e. **Format-aware: serves the layout's media zones** (ADR 0007 — `ranked_list` → N item images, `head_to_head` → an A and a B, `explainer` → one concept clip). **Fallback ladder when no clip clears threshold** (ADR 0008): ranked stock → AI gen (01b) → branded data-viz/typographic card (01e) — **never a generic mismatched clip** in a prominent region; the hook's first frame **defaults to the designed typographic card** (the bold-claim pattern-interrupt — stock/AI only when it demonstrably beats the card, ADR 0017 D4). **Query style (ADR 0017 D2): searches carry an abstract/textural bias and a literal-cliché denylist** (coins/skylines/pointing-at-charts — the scam-ad vocabulary); where a number exists, the branded data-viz/mockup card is *preferred*, not a fallback. Real footage is the backbone. | `scenes/` + provenance |
| **01b image-gen** | →host ComfyUI | FLUX.1-schnell photoreal stills for the un-stockable only. | `scenes/` fills |
| **01c img2vid** | →host ComfyUI | LTX-Video (img→video on real frames) / Ken Burns. AI motion kept to short fill clips. | `scenes/` clips |
| **01d upscale-restore** | →host ComfyUI | Real-ESRGAN upscale + RIFE interpolation + GFPGAN/CodeFormer face restore on AI frames. | `assets.json` |
| **01e data-viz** | CPU | **Branded animated charts / counters / stat reveals** rendered from `data.json` numbers (ADR 0005 D5) via the **same composition engine as Stage 05** (ADR 0007) — deterministic, artifact-free, license-free; the finance niche's signature visual *and* a citation surface. Fills beats stock can never match. | `scenes/` viz clips |
| **02 voice** | CPU | Kokoro-82M narration — **with the M3 expressiveness gate (ADR 0017 D1): Kokoro is A/B'd against the most expressive open candidates (Orpheus/Chatterbox), judged on prosody/emotion control + hook delivery, and the winner becomes the channel voice (a hosted expressive voice is the recorded escalation if none clears the bar)** — driven by a **finance text-normalization + pronunciation lexicon** (`$1.5M`, `401(k)`, `FOMC`…) and **per-beat prosody/emphasis/pause markup** incl. a deliberate hook delivery (ADR 0005 D6), **rate-modulated by the treatment's energy curve (ADR 0017 D7)**; the **primary keyword is spoken in the opening lines** (ADR 0006). | `narration.wav` |
| **03 subtitles** | CPU | WhisperX `int8` **forced-aligned to the known script text** (ADR 0009 — *not* a fresh transcription, which would corrupt `401(k)`/tickers/`$1.5M`; free transcription is a fallback only if alignment fails) → **designed** karaoke captions: brand font, ≤N words on-screen, stroke/shadow, **emphasis-word styling**, animation, **per-platform vertical safe zones** (ADR 0005 D7); the **primary keyword appears as on-screen text in the first 2–3s** (ADR 0006). | `captions.ass/.srt`, `word_timings.json` (consumed by Stage 05) |
| **04 music** | CPU | Strike-safe track from a **per-platform curated library** (ADR 0009 — "strike-safe" is platform-scoped: YouTube Audio Library is YouTube-oriented, TikTok pushes non-personal accounts to its Commercial Music Library; cross-platform terms verified, not assumed), **selected by a closed mood/energy taxonomy tied to the format** (anti-repeat across the batch) + a **transition-SFX layer** (whoosh/tick/reveal), ducked under VO (sidechain), **per-platform LUFS** (ADR 0005 D6). | `music.wav` + sfx |
| **05 render** | CPU compositor + GPU NVENC | **Format-aware compositor** (ADR 0007 / **0007a**): a deterministic **resolve step** binds the format's **`layout`** (named frame regions on a grid-in-safe-rect, per-beat structured data, animation, transitions) + **the visual lane's chosen per-beat assets (`assets.json` → MediaZone paths)** + word timings (**incl. the `KaraokeCaption` words**) + **the 04 audio mix** + brand kit + seeded slots into a flat **`render_manifest.json`**, rendered as a **pure function of the manifest** (reproducible, ADR 0009) by the **Remotion** engine (locked, ADR 0007 §4) at **30 fps** via **CPU rasterization** on the 7800X3D (deterministic — GPU-Chromium rejected), **encoded with `h264_nvenc` on the 5070 Ti** (GPU free at render time; hash frame PNGs, not the mp4). Per-platform cuts are **manifest deltas, not code paths**. Then **word-timed cuts + visual-change target**, **per-clip color *matching* before** the grade, **brand overlay** + the **mid-roll engagement-CTA bump** (ADR 0005 D10), designed **thumbnail/cover** (TikTok cover = frame 1), a **seamless loop bridge** and a **closing FOMO end-card** (ADR 0006) → **distinct native cuts for YouTube + TikTok** (ADR 0005 D4/D7/D10). | `renders/{youtube,tiktok}.mp4`, `thumbnail.jpg` |
| **05x vision pass** | →host VLM | **One vision-language pass over sampled keyframes** (hook frame, end-card, per-beat samples) + script + asset manifest — **Qwen2.5-VL** (Apache-2.0), a GPU citizen under the never-co-resident rule, run post-render when FLUX/LTX are evicted (ADR 0008). Runs **once, on the YouTube cut** (per-platform geometry is checked deterministically per cut in 05b — ADR 0016 D4). Emits **per-keyframe observations + visual sub-scores (coherence/pacing), not verdicts** (ADR 0016 D5); served via an **OpenAI-compatible chat endpoint with image content**. Feeds **both** gates below so they judge the **rendered output, not just intent**. | `vision.json` |
| **05b safety gate** | CPU +host LLM | The always-on **account-safety gate** (Chapter 8, ADR 0004 D3): YMYL disclaimer present, no buy/sell calls, sources cited, AI-disclosure set, profanity/claims clear, repetitious-content check vs ledger, render integrity — **+ aesthetic/artifact + audio-defect checks** (morphing hands, temporal warp, garbled AI text, caption occlusion, hook dead-air, loudness, synth-duration), now grounded in the **05x vision pass** (ADR 0005 D8 / ADR 0008) — plus **per-cut geometric safe-zone assertions** over *each* platform cut's `render_manifest` (caption band / CTA bump / citation inside that platform's safe rect — pure rectangle math, every cut, no extra VLM pass; ADR 0016 D4). Pass → continue; fail → quarantine. | `qc.json` |
| **05c creative-QC** | CPU →host LLM | The **quality gate** (ADR 0005 D2), distinct from safety: an **independent, non-Qwen-lineage judge** (ADR 0016 D1 — the author model never grades its own survival criterion) scores the **rendered** video — hook strength, **original insight (ADR 0014 D1)** and payoff judged from script + treatment + the 05x **observations**, merged with the 05x **visual sub-scores** (coherence/pacing) under the rubric weights — vs a **quality floor** anchored to the **ramp's human approve/reject labels** (ADR 0016 D2). Above floor → distribute; below → **quarantine, not post**. | `creative_qc.json` |
| **06 distribute** | CPU | Per-platform **distribution adapters** (YouTube Data API v3 + TikTok Content Posting API), **exactly-once** via the `(video_id, platform)` **posted-state ledger** (`history/posts.jsonl`, ADR 0003 D1), **private-first / ≥1 public**, **AI-disclosure on every call**, the **primary keyword leads the caption's first ~150 chars** (ADR 0006), emits affiliate description when enabled. Append the novelty ledger via the batch's single fan-in commit step. | post receipts |

All clips are normalized to **1080×1920**. The scene manifest (`assets.json`) plus the
`job.json` spine make any video reconstructable.

## Chapter 5 — Data contracts & storage

**Contracts first (REVIEW C2 / P0).** The stage interfaces *are* the architecture, so they are
the **first committed code artifact**, as versioned JSON Schema under `schemas/`, validated at
every stage boundary. The prose below is the **input to M0**: M0's job is to turn each of these into
an executable, versioned JSON Schema (this is exactly what ADR 0010's "conventions" mean — authoring
the contracts is the work), built to the primitives + acceptance checklist in **ADR 0012**.

- **`job.schema.json`** — the spine threaded through every stage: `batch_id`, `video_id`, niche,
  profile, platform targets, per-stage status, the run's file paths, and a **persisted `seed`**
  (ADR 0009) the generative stages derive from, so best-of-N / FLUX / LTX re-runs are reproducible.
- **`script.schema.json`** — Stage 00b output: the chosen **`format`** (Chapter 6); **structured
  per-beat layout data keyed to the format** (e.g. `ranked_list` → ordered `items[]` of
  `{rank, title, body, media_query, stat?}`; `head_to_head` → `{side_a, side_b, verdict, round[]}`
  with `side_*: {media_query, label}`, `verdict: {text}`, `round: {metrics}`) that the
  Stage 05 layout template binds to (ADR 0007); a **`treatment`** block (thesis/angle/tone,
  per-beat visual motif, energy curve — ADR 0005 D1);
  a first-class **`hook`** composite (`{spoken, on_screen_text, first_frame_visual, duration}`)
  plus its scored variants; narration beats **with prosody/emphasis markup**; captions with
  emphasis tags; per-beat visual motif; music **mood+energy**; per-platform metadata;
  claims + citations **with `{value, source_ref}` pointers into `data.json`** (ADR 0009, for the
  deterministic numeric-grounding check); disclaimer; and **optional affiliate fields** (ADR 0004 D5).
- **`creative_qc.schema.json`** — Stage 05c output: the judge's per-criterion scores + overall
  quality score vs the floor (ADR 0005 D2). Distinct from `qc.schema.json` (safety).
- **`assets.schema.json`** — Stage 01d output: the final scene manifest (one normalized clip per
  beat).
- **`provenance.schema.json`** — per asset: `source`, `url`, `license`, `fetch_date`.
- **`qc.schema.json`** — Stage 05b output: the account-safety gate's per-check pass/fail + verdict.
- **`vision.schema.json`** — Stage 05x output: the VLM's per-keyframe **observations** (hook frame,
  end-card, per-beat samples) **plus visual sub-scores (coherence/pacing)** that feed both gates
  (ADR 0008); **verdicts stay in the gates** — 05c's independent judge scores the text-judgeable
  criteria from these observations (ADR 0016 D5). A versioned contract like every other
  stage output.
- **`posts.schema.json`** — the posted-state record keyed `(video_id, platform)`: intent →
  confirmed (with the remote post id). The **exactly-once** backbone (ADR 0003 D1), kept
  separate from the novelty ledger.
- **`profile.schema.json` / `format.schema.json`** — niches and format archetypes are **validated
  config, not code** (ADR 0010): adding a niche or a format is a checked data file behind a loader/
  registry, resolved through one precedence layer (**global → niche → batch → per-platform**).
- **`layout.schema.json`** — the format's **`layout`** recipe (ADR 0007a): named regions
  (`bbox` on a 12-col grid + vertical anchors within the per-platform safe rect, `z`, `bind` to a
  typed beat-field, `primitive`, `enter`/`exit` animation, `style` token refs) + the beat pattern.
  Validates region/bbox/animation names and — at resolve time — that every `bind` exists in that
  format's typed beat contract, so **adding a format stays data, not code**. The Stage 05 resolve
  step emits a `render_manifest` the Remotion `LayoutEngine` renders as a **pure function** (ADR 0009).
  The resolve output has its own **`render_manifest.schema.json`**; both `layout.schema.json` and
  `render_manifest.schema.json` are authored in **M2** (the compositor milestone), not M0 — hence
  neither appears in the 11-schema M0 list above.
- **`feature_record.schema.json`** — a **stable per-video record** (chosen format / seed / hook
  variant + judge scores + a reserved metrics slot) written from the first run, so the deferred
  analytics loop (ADR 0002/0005) starts *warm* instead of cold (ADR 0010 D6).

**Extensibility conventions (M0, ADR 0010).** The seams that keep "extend by configuration, not
rewrite" true are set *before the first stage is written*: schemas carry a **`schema_version`** and
a **validation harness fails loud** at every boundary, backed by a committed **golden-fixtures**
chain; stages share a thin **Stage SDK** (`run(ctx)` over declared inputs/outputs + `job.json`,
seed, logging, retry/quarantine) and **declare metadata the DAG is generated from**; the three
growth axes sit behind **adapter interfaces** — `DistributionAdapter` (exactly-once in the base),
per-capability **model backends** (so every model A/B swap is config), and a `LayoutEngine`
(abstracts the still-unpicked composition engine, ADR 0007); and a **fake-backend offline harness +
content-addressed stage cache keyed on `(stage, input_hash, seed)`** lets the whole DAG run on a
laptop / in CI with no GPU and skip already-computed work (sound because the seed is persisted, ADR
0009).

**Storage — a single host directory, `DATA_ROOT` (ADR 0015 D4).** One filesystem for the
conductor, every stage, and the host GPU services (ComfyUI's output dir is configured under it) —
on WSL2 **ext4, not `/mnt/c`** (ADR 0013). It survives reboots trivially — not cosmetic: cross-run
dedup is only possible because the ledger persists. *(Under the deferred k8s profile this same
directory mounts as the PVC via `extraMounts`.)*

```
 DATA_ROOT  (host dir; = the PVC under the deferred k8s profile)
 └── runs/<batch-id>/
     ├── batch.json                # which videos, profiles, status
     ├── data/                     # 00a: market data + recent news (≤3d)
     └── <video-id>/
         ├── job.json  script.json (+treatment)  assets.json  provenance.json
         ├── scenes/  narration.wav  captions.ass/.srt  music.wav
         ├── renders/{youtube,tiktok}.mp4  thumbnail.jpg
         └── qc.json  creative_qc.json
 └── quarantine/<video-id>/        # 05b/05c failures; retention/GC policy (ADR 0003 D8)
 └── history/ledger.jsonl          # append-only novelty ledger (Chapter 6)
 └── history/posts.jsonl           # posted-state ledger, (video,platform) exactly-once (ADR 0003 D1)
 └── models/                       # host-mounted shared weight cache (downloaded once)
```

No MinIO (REVIEW T5). The conductor passes artifacts **by path** under `DATA_ROOT`. Both `*.jsonl`
ledgers are written by a **single fan-in commit step per batch** (no concurrent appenders —
ADR 0003 D6), and a **pre-batch free-space gate** guards against the disk-full SPOF.

## Chapter 6 — Freshness & novelty (ADR 0002)

**Freshness — content made from the newest data.** Stage `00a` pulls, in one step:
- **Numeric market data** (Alpha Vantage / Yahoo / FRED), and
- **Recent news** via **free RSS feeds** from reputable finance/business outlets, filtered to
  `published ≥ now − 3 days` → `data.json = {market, news:[{title,url,source,published,summary}]}`.

No paid news API (preserves the no-recurring-cost rule; a free-tier API is a later add only if
RSS coverage proves thin). **Corroboration (ADR 0009):** a `news_reaction` story must be confirmed
across **≥2 reputable sources** (or pass a source-reliability weighting) before 00b commits it —
a single rumor/satire/wrong headline must not become a confident video; uncorroborated items drop
to a lower-confidence treatment or skip via the starvation ladder. **Licensing/policy:** articles are **source facts and angles →
original synthesis with on-screen citations** (already a YMYL requirement); we never republish
article text and skip paywalled sources. A fetch failure is a first-class DAG state.

**Novelty — don't repeat ourselves.** An append-only `history/ledger.jsonl` on the durable
volume records one entry per produced video:

```
{ id, date, niche, topic, title, hook, format, source_urls:[...], keywords:[...], embedding: null }
```

Stage `00b` queries the ledger before committing a topic and **rejects/repicks** if any
`source_url` was already used **or** keyword/title overlap with recent records exceeds a
threshold. It also **reserves its pick in `batch.json`** so two videos in the *same* batch can't
land on the same fresh story (the ledger is only written post-distribute, so it can't see
intra-batch collisions — ADR 0003 D5). Recency filtering normalizes timestamps to **UTC** and
dedups on **canonical URL/story**, not the raw feed URL. This is the **keyword + source-URL** tier — no model, robust, debuggable. The
`embedding` field is **reserved** so a cosine-similarity tier (small local embedding model,
catches reworded duplicates) layers on **post-M1 without schema rework**. The ledger doubles as
the **compliance lever** against repetitious/inauthentic-content demotion.

A **starved** batch degrades gracefully rather than wedging or silently yielding zero output:
**widen window → relax threshold → same-topic-different-angle → skip-with-WARN** (ADR 0003 D5).

### Format templates — supercharging the 00b prompt

A bare "write a finance short" prompt drifts toward the same generic talking-head every
time. Instead, Stage `00b` selects from a **library of short-form *format templates*** — each a
proven retention structure with its own hook pattern, body shape, and pacing — and the chosen
`format` is injected into the LLM prompt to steer structure, while the **recent-news topic**
(Stage 00a) supplies substance. Format × topic is what makes 50 videos feel distinct.

The PoC ships these archetypes (finance/business framing shown; the same shapes carry to any
niche):

| `format` | Hook pattern | Body shape | Example title |
|---|---|---|---|
| `ranked_list` | "The #N worst/best …" countdown | N punchy items, escalating to #1 | *Top 5 worst money decisions in your 20s* |
| `myth_buster` | "Stop believing this about …" | Claim → why it's wrong → the truth | *No, a credit card isn't free money* |
| `explainer` | "Here's how X actually works" | One concept, one concrete number worked through | *How compound interest quietly doubles your money* |
| `news_reaction` | "X just happened — here's what it means for you" | Fresh event → 2–3 implications → takeaway | *The Fed just cut rates — what it means for your savings* |
| `cautionary_tale` | "This one mistake cost people …" | Illustrative (third-person) story → lesson | *The 401(k) mistake that quietly costs you six figures* |
| `head_to_head` | "X vs Y in 60 seconds" | A vs B → when each wins → verdict | *Roth vs Traditional, settled in 60 seconds* |
| `surprising_stat` | "Did you know …?" (one number) | Counterintuitive stat → unpack → so-what | *90% of day traders lose money — here's why* |
| `how_to_steps` | "How to X in N steps" | Numbered, actionable mini-guide | *Build a 6-month emergency fund in 4 steps* |

Rules that keep this honest and non-repetitive:

- **Config-driven, not hardcoded.** Templates live in a versioned `formats/` library (hook
  pattern + structure + length target + format-specific QC notes + a **`layout`** recipe), so
  adding/retiring a format is **data, not a code change**.
- **Format owns the *picture*, not just the words (ADR 0007).** Each of the 8 archetypes carries a
  **layout template** — named 9:16 frame regions, per-region media/text binding, animation, and
  inter-beat transitions — that Stage 05's compositor renders against. This is what stops a
  polished `ranked_list` and a `head_to_head` from being *assembled identically* (the generic-
  slideshow failure mode). Layout = the format-level skeleton; the treatment (ADR 0005) fills the
  per-beat content. E.g. `ranked_list` → a repeating item card (rank badge that ticks in, item
  title ~30% height, background media zone, karaoke body ~60% height, swipe transition). 01a
  fetches the layout's media zones; 03's captions *are* a region; the engine is shared with 01e
  data-viz.
- **Length is per-format, two lanes (ADR 0006).** Punchy formats (`news_reaction`,
  `surprising_stat`, `myth_buster`) target **~20–35s** for completion/attention (the **reach
  lane**); depth formats (`explainer`, `ranked_list`, `how_to_steps`, `head_to_head`,
  `cautionary_tale`) run **~61–90s** — strictly **over 60s**, since TikTok Creator Rewards pays
  **$0** on sub-minute videos (the **monetization lane**, recommended 61–70s). Completion rate is
  the craft target (~70% aspiration), **not** a DoD metric (ADR 0004 D1) — we shape for retention,
  we don't gate "done" on views.
- **Batch mix ≈ 60% monetization-lane (ADR 0006).** Format-selection weights target, over a
  **rolling window** (a single 2–4-video batch is too small for a ratio), **~60% of videos ≥61s**
  and ~40% reach-lane. The split is **config + phase-dependent**: pre-eligibility (under 10k
  followers / 100k views-per-30-days) tilt toward reach to *reach* the bar; once eligible, hold
  ~60% monetization. Recorded in `batch.json`.
- **Format ↔ lane compatibility + content scaling (ADR 0008).** Each format declares
  **`lane_support`** so a long format never lands in a short slot: `surprising_stat` /
  `myth_buster` / `news_reaction` → **reach or both**; `explainer` / `cautionary_tale` /
  `head_to_head` → **monetization** (need room to land); `ranked_list` / `how_to_steps` → **both,
  *scaled*** — 00b sizes the payload to the lane (**top-3 / 3-steps** in reach, **top-7–10 / 5+
  steps** in monetization). The mix selector only picks **declared-compatible** format×lane pairs.
- **Discoverability built in (ADR 0006).** 00b emits a **primary keyword** threaded three ways:
  the caption's first ~150 chars (Stage 06 metadata), on-screen text in the first 2–3s (Stage 03),
  and the spoken opening (Stage 02) — so the video is *found*, not just recommended.
- **Loop + closing CTA (ADR 0006).** Where the format allows, the last line/frame **bridges back
  to the hook** for a seamless loop (replays lift AVD); a short **end-card** then makes the closing
  ask — a **FOMO follow** line (default *"Follow — the algorithm only shows us once"*, platform-
  aware Subscribe/Follow, config-driven & rotatable) placed so it doesn't break the loop. Some
  formats may run as a **series** (Part N) so the CTA becomes "follow so you don't miss Part 2."
- **`news_reaction` is freshness's natural home** — it consumes the highest-recency RSS item
  from 00a directly; the others lean on topic + market data.
- **Format is part of the novelty signal.** The ledger records `format`, and the dedup check
  treats **topic × format** as the unit — so the same story can be revisited through a *different*
  format, but the same story in the same format is a repeat (also the starvation ladder's
  "same-topic-different-angle" rung). 00b also **rotates formats within a batch** so a day's 2–4
  videos aren't all `ranked_list`.
- **YMYL still binds every template.** All formats inherit the mandatory disclaimer, no
  buy/sell/price calls, and on-screen citations; `cautionary_tale` is **illustrative/third-person**
  (never a fabricated personal "I lost $X") to stay truthful under the account-safety gate.

### Treatment, hook & best-of-N — the quality layer (ADR 0005)

Format + fresh topic make a video *structurally varied and current*; they do **not** make it
*good*. The output-quality review found the pipeline had no owner of the *whole* video — each
stage was locally optimized while nothing enforced a through-line — so 00b now owns three things:

- **A treatment (the through-line).** Before the script, 00b emits a compact creative brief:
  the one-line thesis/"so-what", the angle, the tone, a **per-beat visual motif** (the intended
  shot and *why*, not a bare keyword), and an **energy curve**. Every downstream stage renders
  against the treatment instead of doing its own lossy lookup — this is what binds words,
  pictures, captions, music, and pacing into one story.
- **Best-of-N + an LLM-as-judge.** 00b generates **N** treatments/scripts; a judge rubric (hook
  strength, says-something-non-obvious, visual↔script coherence, payoff) **selects the winner**.
  Until the deferred analytics loop exists, *the judge is the picker*. The same judge backs the
  **05c creative-QC** quality gate on the assembled video (quality floor → quarantine, not post).
- **The hook as a first-class composite.** Not a spoken line but `{spoken, on_screen_text,
  first_frame_visual, ≤2s}` — frame 1 is a designed pattern-interrupt (and the TikTok cover).
  All hook variants + the chosen one + their scores are **persisted to the ledger** (the same
  "reserved field" discipline as `embedding`) so the future feedback loop starts with data, not
  cold.

Formats are **weighted, not uniformly rotated** — bias toward the hook-native, automation-friendly
archetypes (`news_reaction`, `surprising_stat`, `myth_buster`); treat the slideshow-prone ones
(`explainer`, `ranked_list`) as high-production-requirement; the weights are config, tunable once
data exists.

**Open (tracked):** the per-niche RSS source list; the overlap threshold default; the embedding
model for the post-M1 tier; the starting **format library** + weights per niche; the **judge
rubric weights + quality floor** and **N** for best-of-N (ADR 0005).

## Chapter 7 — GPU / VRAM & throughput

**Hardware:** one **RTX 5070 Ti, 16 GB** (Blackwell, **sm_120**). The single most likely "doesn't
work on my box" failure is the toolchain: **CUDA 12.8+ and a torch `cu128` build with sm_120
kernels are mandatory** in the host GPU environment (ComfyUI + LLM); older wheels fail with
`no kernel image is available for execution on the device`. Moving the GPU to bare metal
(ADR 0001) trades the in-container toolchain problem for host-env drift, so the host **pins
`torch` cu128 + the ComfyUI commit + custom-node versions** and snapshots working graphs —
drift is a release-gated change (ADR 0003 D8).

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
`Qwen → evict → FLUX → evict → LTX → evict → ESRGAN/RIFE/GFPGAN → evict → Qwen2.5-VL (05x, post-render)`. ComfyUI's queue serializes the
diffusion stages; the LLM endpoint is up only during 00b. Because ComfyUI and the LLM are
*separate* host processes, ordering alone is not enough — a **single host GPU lease both must
hold**, an explicit **confirm-VRAM-free gate** between 00b and 01b, and `CronWorkflow
concurrencyPolicy: Forbid` (ADR 0003 D2) make "**no two heavy models ever resident together**"
a property, not a hope. That is the OOM cliff.

**Throughput:** stock-heavy path ≈ **12–25 min/video**; **plan for ~25 min as the norm** (two
platform renders ≈ double the ffmpeg encode; 12 min assumes near-zero AI motion + no load churn).
2–4/day still fits comfortably overnight. The #1 throughput multiplier is **stage-batching**
(amortizes model load/unload across the batch); the #2 is **CPU/GPU overlap** — meaning CPU
stages (ffmpeg + WhisperX + Kokoro) overlap GPU stages **within one batch**, **never two GPU
batches at once** (ADR 0003 D2). Note FLUX (~12 GB) and LTX (~14 GB) are near the 16 GB ceiling
*even singly* — leave headroom and validate before committing to any higher cadence. The quality
layer (ADR 0005) **re-opens this baseline**: best-of-N adds N−1 LLM passes and 05c a judge pass
(both cheap — the LLM is already resident), 01e data-viz adds a CPU stage; the per-video figure
must be **re-measured**, not assumed. The **format-aware compositor** (ADR 0007) re-opens it
again — headless-Chromium frame rasterization is new CPU cost, but the GPU is **idle at render
time** so `h264_nvenc` on the 5070 Ti offsets the encode side. The **05x vision pass** (ADR 0008)
adds one more serialized GPU model. These have re-opened the baseline **four times without ever
being summed** — so an **end-to-end per-video budget reconciliation** on the real box is now a
required measurement (the overnight 2–4/day window is probably still fine, but it must be proven).

**Choke points — what a 16 GB 5070 Ti *cannot* do (the binding constraints):**
- **Full-length AI video.** Generating the whole runtime as img2vid collapses throughput to
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
- **Retry → quarantine, never wedge — by design, not assertion.** Each video is a **sub-DAG
  branch with `continueOn`** (ADR 0003 D4), so a quarantined video drops out of the *remaining*
  fan-out while the batch's loaded model still serves the survivors. **Per-video** faults
  quarantine; **systemic** faults (OAuth-token expiry, disk-full, host-down) are
  **batch-halting alerts**, not per-video quarantine.
- **Stage 6 exactly-once.** Posting is side-effecting; retries must **never double-post**. A
  dedicated **posted-state ledger** `history/posts.jsonl` keyed `(video_id, platform)` writes an
  *intent* record before the API call and a *confirmed* record (remote id) after; YouTube
  `insert` has no client token, so a retry confirms via the stored remote id before re-posting
  (ADR 0003 D1). Kept **separate** from the novelty ledger.
- **Host dependency as a first-class failure state, plus supervision.** Host ComfyUI / the LLM
  run under a supervisor (`systemd Restart=always`) with `/health` endpoints; the conductor
  **gates fan-out on host health** (fail-fast + alert, not a retry-storm) and a **batch-level
  circuit breaker** halts on repeated host failures. An unreachable host fails the stage
  (→ retry/backoff) with a hard poll timeout + a per-stage deadline — it never hangs
  (ADR 0003 D2/D3, semantics re-homed to the conductor per ADR 0015).
- **Pre-flight gates.** Before fan-out: a **free-space check** (disk-full SPOF) and an
  **OAuth-token validity/refresh check** (ADR 0003 D8); `quarantine/` and old `runs/` are GC'd.
- **Backups.** `history/*.jsonl` (the novelty + posted-state ledgers — the only unrecoverable
  state) and the credential material are copied nightly to a second disk/cloud path (one rsync
  line in the post-batch step).
- **Host-reboot recovery (ADR 0003 D9).** `systemd Restart=always` recovers the host *processes*,
  but an in-flight batch dies with the box on a host/OS reboot. A **boot-time reconciler**
  inspects `batch.json` and **resumes the interrupted batch from its last completed stage** (safe
  because re-runs are seeded + idempotent, ADR 0009) or cleanly re-submits — so a mid-batch reboot
  doesn't silently drop a day's output and void the 1–2 week unattended bar.

**The account-safety gate (Stage 5b) — the always-on "human replacement" (ADR 0004 D3)**
- **Purpose:** an explicit **takedown/demonetization-risk filter** that runs on **every** video,
  including after the ramp's human gate is removed — the *durable* account protection.
- **Checks (all must hold to pass):** YMYL disclaimer present; **no buy/sell/price calls or
  guaranteed-return claims**; sources cited; **AI-disclosure flag set**; profanity/unsafe-claims
  clear; **repetitious-content** check vs the novelty ledger; render integrity (no dead audio,
  no black frames, no clipped loudness); second-pass LLM fact/sanity + hallucination flag;
  **+ aesthetic/artifact checks** (morphing hands, temporal warp, garbled AI text → quarantine or
  fall back to Ken Burns on a clean still) and **audio-defect checks** (hook dead-air, loudness
  within the platform window, synth-duration matches script) (ADR 0005 D8). The channel's own
  **engagement-CTA bump is whitelisted** (not a *foreign* watermark) but is verified to sit in the
  **platform-safe zone** — not occluding TikTok's right-rail UI or the caption band (ADR 0005 D10).
- **Outcome:** pass → distribute; fail → quarantine + log for the weekly spot-audit.
- The second-pass LLM uses the **same host endpoint + eviction rule** as 00b.
- **Human-at-publish during the ramp (ADR 0004 D2):** in addition to this gate, a person
  approves each post during the initial ramp; removed once the gates + a track record earn the
  fully-unattended run. *(Open: numeric pass/fail thresholds; ramp-exit criteria.)*
- **Account provisioning + warming (ADR 0009):** brand-new accounts posting API-driven daily YMYL
  content is a flag pattern, so accounts get a **provisioning step** (profile, bio, avatar, niche
  signals) and a **warming period** before the cadence ramps — folded into the phased ramp above,
  not a new mechanism.

**The shared vision pass (Stage 5x) — so the gates judge pixels, not intent (ADR 0008)**
- A **single vision-language pass** (Qwen2.5-VL, Apache-2.0) over **sampled keyframes** (hook
  frame, end-card, per-beat samples) + the script + asset manifest, run **post-render** when
  FLUX/LTX are evicted (a GPU citizen under the never-co-resident rule).
- **Why it exists:** a text LLM can't actually *see* the rendered video — without this, `05b`'s
  artifact checks and `05c`'s "visual↔script coherence" judge only *intent*. The vision pass makes
  both real: it feeds `05b` (artifacts / garbled on-screen text / caption occlusion / safe-zone)
  and `05c` (visual coherence, hook strength, pacing feel).

**The creative-QC quality gate (Stage 5c) — distinct from safety (ADR 0005 D2)**
- **Purpose:** enforce the DoD's "genuinely good, not slop" clause. 05b asks *"is it safe to
  post?"*; 05c asks *"is it worth watching?"* — two different questions, two gates.
- **Mechanism:** the LLM-as-judge (the same one that picks the best-of-N at 00b) scores the
  assembled video against a rubric — **hook strength, says-something-non-obvious, visual↔script
  coherence, payoff lands** — to an overall **quality floor**.
- **Outcome:** above floor → distribute; **below floor → quarantine, not post.** A boring-but-safe
  video is held back, which is the whole point — without 05c the quality bar is aspirational.
- **Known weakness — self-judging (ADR 0009):** the picker, this gate, and the 05x VLM are the
  model grading itself, which is biased and uncalibrated. Mitigation: prefer a **different model
  family** for the judge where practical, and set the floor against a **small human-labeled
  calibration set** rather than an absolute score; until then the floor is an explicit guess.
- *(The human-at-treatment checkpoint was considered and declined — ADR 0005; the judge + the
  ramp's publish-time human cover early and late quality respectively.)*

**Observability**
- Structured (JSON) logs per stage; a per-batch (`batch.json`) and per-video (`job.json`)
  manifest; clear pass/quarantine signals; **no silent failures**.
- **Backend (ADR 0003 D7):** Prometheus + node-exporter + **DCGM-exporter for GPU/VRAM**, plus
  ComfyUI queue depth and **per-stage duration + heartbeat**; persisted logs (not just pod
  stdout); **alerts** on host-down, disk > 80%, batch-failed, and quarantine-rate spike.
  Per-stage expected-duration baselines distinguish *slow* from *stuck* — essential for a 3am
  unattended stall.

**Operations — run flow**
- **One command to turn it all on:** `scripts/up.sh` (= `make up`) sequences the whole bring-up —
  host ComfyUI → Ollama (+ model pull) → a conductor→host localhost wire check (ADR 0015; no
  cluster) — and is
  **idempotent** (skips healthy pieces, health-gates each plane), so it doubles as resume-after-
  reboot. `scripts/down.sh` stops it (data under `DATA_ROOT` persists).
  Under the hood it calls the granular targets `make host-up · wire`.
- **On Windows (ADR 0013 + 0015):** run the entire Linux stack **inside one WSL2 distro** (ComfyUI
  + Ollama via the NVIDIA Windows driver; the conductor under a **WSL2 systemd timer** — no
  Docker/kind in the nightly loop); the bash scripts run unchanged, and
  `scripts\win\shorts.ps1 {up|down|trigger}` is the PowerShell entry point. Repo + data on WSL2
  **ext4 (not `/mnt/c`)**, `systemd` enabled in `wsl.conf`, and a **Task Scheduler `wsl`-at-logon**
  task keeps the daily cron alive across reboots. **Host power policy (ADR 0015 D3):** sleep
  disabled (or wake timers enabled) for the batch window and Windows Update active-hours set away
  from it — the WSL keep-alive does *not* keep Windows awake. Perf overhead is a few percent;
  VRAM is tighter, so quantized LTX is non-optional.
- **Two entry points to the *same* `shorts-batch` WorkflowTemplate, plus a dry-run flag:**
  **(a) manual / on-demand** — `scripts/trigger.sh [--profiles … --count … --dry-run --watch]`
  (= `make trigger`); **(b) scheduled** — the `CronWorkflow` fires the daily batch automatically.
  The **`--dry-run` flag** (on either path) stages all metadata and posts nothing. Manual and
  scheduled runs are identical bar the trigger, and `concurrencyPolicy: Forbid` (ADR 0003) rejects a
  manual kick that would overlap a running batch rather than letting two go co-resident.

**Testing (`POC §6`)**
- Schema validation on `job.json` and every stage output.
- Unit tests on the deterministic seams: script/treatment-schema adherence, finance text
  normalization, stock relevance-ranking, music selection, render-arg construction, QC heuristics
  (safety + creative), and dedup matching. TDD where it fits.

## Chapter 9 — Compliance & licensing

**Licensing — commercial-safe spine (Apache/MIT) only.** Qwen2.5-14B (Apache-2.0), Pexels/
Pixabay/Mixkit/Coverr/Videvo (per-asset license verified), FLUX.1-schnell (Apache-2.0),
LTX-Video (verify the >$10M-ARR clause — we are far under), Kokoro-82M (Apache-2.0), WhisperX
(BSD/MIT + Whisper MIT), **music from a per-platform source** (ADR 0009 — "strike-safe" is
platform-scoped: YouTube Audio Library is YouTube-oriented, TikTok pushes non-personal accounts to
its Commercial Music Library; Pixabay Music as a cross-platform candidate with terms verified, not
assumed), ffmpeg (LGPL/GPL).
**Composition engine (ADR 0007):** the Stage 05 / 01e templating engine must stay on the spine —
**default to the MIT-clean path (Playwright Apache-2.0 + HTML/CSS, or Motion Canvas MIT)**;
**Remotion** is permitted only at solo/≤3-person scale (it needs a **paid company license** above
that, so it is *not* a clean-spine default). Final pick locked in the visuals milestone.
**Excluded (❌ non-commercial/restricted):** FLUX.1-dev, XTTS/Coqui, MusicGen/AudioCraft, Stable
Video Diffusion. Every asset records provenance (`provenance.json`) as the evidence trail.

**Copyright-strike avoidance.** Never ingest copyrighted footage/music/images. News articles are
used as **facts + citations**, never republished; paywalled sources skipped. *(Accepted cost,
ADR 0008: the strike-safe music rule means we **cannot ride trending commercial sounds** — a real
TikTok reach disadvantage vs human creators, traded deliberately for account safety.)*

**Platform policy (separate from copyright):**
- **YMYL (finance/business).** Mandatory "educational, not financial advice" disclaimer; **no
  buy/sell/price calls**; on-screen source citations; accuracy self-check. Kept strictly
  educational/non-advisory.
- **Inauthentic / repetitious content.** Mitigated by per-video variety (the novelty ledger,
  Chapter 6) + the **creative-QC quality bar (05c)** + a **recognizable editorial persona**
  (ADR 0005 D9, the anti-content-farm lever) + the phased cadence ramp.
- **AI-content disclosure.** The disclosure flag is set on **every** publish call, both
  platforms, always — non-negotiable.

**Posting posture — private-first, public via a flag, audits in parallel.** An unaudited YouTube
project uploads **private**-only; an unaudited TikTok app posts **SELF_ONLY**, ≤5/day. We build
against the **real** APIs and **real new accounts**, defaulting private/unlisted (works
immediately, no audit). `public` vs `private` is a **single per-platform config flag**. The
YouTube + TikTok compliance audits are pursued **in parallel from day one**, declaring the
use-case honestly; each platform flips to public as its audit clears. **≥1 genuinely public
account per platform** runs alongside the private ones (ADR 0004 D4) so the PoC earns a minimum
reach/retention signal — gated by the always-on account-safety gate (Stage 5b) and the ramp's
human-at-publish step, plus the audit where required. **Honest caveat (ADR 0009):** TikTok's
unaudited Content Posting API is **SELF_ONLY**, so the public signal **leans on YouTube** (unlisted
→public works immediately); the **TikTok public signal is audit-gated and best-effort** — it may
not land within the PoC, and the DoD does not depend on it.

**True crime is dropped entirely** — catastrophic, automation-incompatible defamation risk.

## Chapter 10 — Milestones & open decisions

**Milestones (refines `POC §7` to the lightened architecture):**

| M | Goal |
|---|---|
| **M0** | Scaffold & conductor: repo structure, **host GPU verified** (ComfyUI + LLM reachable over localhost HTTP under the host supervisor — no cluster in the loop, ADR 0015), **the versioned schemas** (`job/script/assets/provenance/vision/qc/creative_qc/posts/profile/format/feature_record`) + **fail-loud validation harness + golden fixtures**, the **Stage SDK + adapter interfaces** (`DistributionAdapter`/model backends/`LayoutEngine`) and the **fake-backend offline harness + content-addressed stage cache** (ADR 0010), the observability stack bootstrapped, **CI running the full DAG GPU-free**. **Built to the concrete contract in [ADR 0012](../../decisions/0012-m0-build-contract.md)** — the `input_hash`/`ctx`/status/adapter primitives, the build ordering, and the M0 acceptance checklist that defines "done." |
| **M1** | Vertical slice: `00a (seeded job + numeric grounding) → 00b (Qwen: treatment + best-of-N + judge) → 02 (Kokoro) → 03 (WhisperX, forced-aligned to script) → 05 (ffmpeg, stills + Ken Burns)` → a real single render (`renders/youtube.mp4`, pre per-platform parity) for **finance**. Proves the shape end-to-end. |
| **M2** | Visuals for real: `01a` stock-first **(CLIP relevance + dedup, format-aware media zones)** + `01b` FLUX fill + `01c` LTX img→video + `01d` upscale/restore + **`01e` data-viz**; **lock the composition engine** (MIT-clean vs Remotion-solo) and stand up the **format-aware compositor** (ADR 0007) — the "not obviously AI" look + the finance signature visual dialed in. |
| **M3** | The **8 format layout templates** (ADR 0007), audio performance layer (normalization/prosody/music taxonomy/SFX), **caption design**, the **`05c` creative-QC gate** backed by the **`05x` vision pass** (Qwen2.5-VL, ADR 0008), persona + brand kit, **business** profile, **+ render finishing** (designed **thumbnail/cover**, the **seamless loop bridge** + **closing end-card** (ADR 0006 D5/D8), **per-clip color matching** + the **visual-change-rate check** (ADR 0005 D4) — previously unowned), **+ the creative-identity layer (ADR 0017): the expressive-voice A/B gate, opinionated persona stances + catchphrase + recurring series, the brand mascot, abstract-stock bias + data-viz-as-identity, and energy-curve→voice/music/pacing dynamics** — proving the two-niche abstraction, the format→layout binding, *and* the quality bar. |
| **M4** | **Conductor hardening + ops (ADR 0015):** runner concurrency (**stage-batching + the visual∥audio lane-fork & per-video CPU fan-out**, ADR 0011, behind the timing metric), **subprocess-per-stage execution** (real timeouts, GIL-free fan-out, crash + untrusted-media isolation, 0015a entrypoint parity), the **batch planner** (`batch.json`: videos/niche, the lane-mix knob, format rotation/anti-repeat, topic reservation) + the **single fan-in ledger commit** (previously unowned), retries/timeouts/per-video failure domains as **tested code**, never-co-resident enforced by the conductor's stage ordering + a VRAM-free check, **both entry points** (the **WSL2 systemd timer** scheduled / `scripts/trigger.sh` manual; a **run lockfile** replaces `concurrencyPolicy: Forbid`), the **one-command `scripts/up.sh` lifecycle** (host GPU + Ollama + conductor — no cluster; idempotent + health-gated) + `down.sh`, the **CI-built shared image** (the production-deployable artifact, proven by running the offline DAG inside it), the phased daily batch. **Gate:** the **end-to-end throughput reconciliation on the real box** (open #9) must confirm a full batch fits its overnight window *before M4 is done* — the unattended DoD rests on this single number, which has been deferred across ADRs 0005–0008 and must not trail into M6. |
| **M5** | Account-safety gate (`05b`) + distribution (`06`, per-platform adapters + the `posts.jsonl` exactly-once ledger) to YouTube + TikTok; private-first **plus ≥1 public** (YouTube-led; TikTok public audit-gated, ADR 0009); disclosure on; **account provisioning + warming** then the **human-at-publish ramp** (every approve/reject **captured into `feature_record` as the judge-calibration label set** — ADR 0016 D2 — via a **minimal review CLI** (`make review`: list pending → play → approve/reject), the previously-unspecified ramp mechanism); the **OAuth app moved to Production status + token-age in the credential pre-flight** (ADR 0009 #10 — Testing-status refresh tokens expire every 7 days and would kill the unattended run); affiliate fields wired (can ship disabled); platform audits submitted in parallel. |
| **M6** | Hardening + alerts/GC/credential pre-flight wired, then the **1–2 week unattended run** (post-ramp) that satisfies the Chapter 1 definition of done. |
| **M7** *(optional)* | **The Kubernetes profile (ADR 0015a):** Variant A (conductor-as-`CronJob` on kind) + the `deploy/k8s` base (PVC=`DATA_ROOT`, `host-gpu` Service/Endpoints, Secrets) + the **manifest→WorkflowTemplate generator** with its regenerate-and-diff CI check + Variant B (Argo per-stage fan-out) + the **`make k8s-smoke`** golden-DAG-on-kind test. Variant C (GPU-in-cluster via device plugin/GPU Operator) stays **design-only** — the operator host is Windows-only (ADR 0015a adopted scope), so C activates only if a separate Linux GPU node ever appears. **Gate:** the golden offline DAG runs green through A *and* B on kind. |

**Decided since (the runtime review → ADR 0003 / 0004):** Stage 6 exactly-once
(posted-state ledger); host GPU lease + confirm-evicted gate + `Forbid` concurrency; host
supervision + readiness gate; per-video failure domains; intra-batch dedup claim + starvation
ladder + timestamp hygiene; serialized ledger writes + per-video run-dir write ownership;
**boot-time batch reconciliation (host-reboot recovery, D9)**; observability backend; disk GC +
credential pre-flight; host toolchain pinning — plus the commercial-posture calls (reframed DoD,
human-at-publish ramp, always-on account-safety gate, ≥1 public account, affiliate designed-in).

**Decided since (the output-quality review → ADR 0005):** a `treatment` artifact owning the
through-line; best-of-N + an LLM-as-judge; the hook as a first-class composite (persisted to the
ledger); a pacing/assembly contract; engineered stock relevance + the `01e` data-viz stage; the
audio performance layer (normalization / prosody / music taxonomy / SFX); caption design; the
`05c` creative-QC gate (distinct from `05b` safety) + expanded aesthetic/audio QC; channel
persona + brand kit in profiles. *(Human-at-treatment considered and declined; human stays at
publish.)*

**Decided since (the algorithm-fit scan → ADR 0006):** **per-format length** — two lanes:
~20–35s reach / ~61–90s monetization (**over 60s**, since Creator Rewards pays $0 on sub-minute
videos), with a configurable **rolling-window mix targeting ~60% of videos ≥61s** (phase-dependent:
tilt to reach pre-eligibility); completion rate as a craft target (not a DoD metric); **seamless loop** construction; **save/share** CTA framing; **primary-keyword** placement
across caption/on-screen/voiceover; a **closing FOMO follow end-card** (config-driven, rotatable);
**series / multi-part** capability.

**Decided since (the format/flow review → ADR 0007):** **format owns the picture** — each of the
8 archetypes gets a **layout template** (named frame regions + animation + transitions); Stage 05
becomes a **format-aware compositor** (headless-Chromium HTML/CSS on the 7800X3D + NVENC on the
5070 Ti) **sharing one engine with 01e data-viz**; the 00b→05 contract becomes **structured
per-beat data**; 01a stock-fetch becomes **format-aware**; engine stays on the Apache/MIT spine
(MIT-clean default, Remotion solo-only).

**Decided since (the parity review → ADR 0008):** a **shared vision pass** (05x, Qwen2.5-VL) so
`05b`/`05c` judge the **rendered video, not just intent**; **format↔lane compatibility +
content scaling** (`lane_support`, top-3 vs top-10); an **asset fallback ladder** (stock → AI →
branded card, never a generic mismatch; the hook frame floors at a typographic card); and
**recorded honest ceilings** (faceless/TTS, no trending-audio, bounded humor — Ch.1).

**Decided since (the content-integrity review → ADR 0009):** **deterministic numeric grounding**
(script figures carry `{value, source_ref}` into `data.json`, a non-LLM check rejects ungrounded
numbers); a **persisted per-video seed** so generative re-runs are reproducible (makes the
idempotency claim true); **captions force-align to the known script** (no corrupting `401(k)`/
tickers); **self-judge recorded as a known weakness** (prefer a different judge model + a
human-labeled calibration floor); **per-platform music sourcing** (strike-safe is platform-scoped);
**TikTok public signal is audit-gated** (lean on YouTube); **account provisioning + warming**;
**external-API budgeting + caching**; **≥2-source news corroboration**.

**Decided since (the extensibility review → ADR 0010):** the M0 code conventions that keep "extend
by configuration, not rewrite" honest — **versioned schemas + a fail-loud validation harness +
golden fixtures**; a thin **Stage SDK** with the **DAG generated from stage metadata**; **adapter
interfaces** for the three growth axes (`DistributionAdapter`, per-capability **model backends**,
`LayoutEngine`); a **fake-backend offline harness + content-addressed stage cache** keyed on
`(stage, input_hash, seed)` (GPU-free CI, skip-completed-work); a **typed config-resolution layer**
with **profiles/formats as validated config**; and the **feedback data contract emitted now** so
the deferred analytics loop starts warm. Set *before the first stage is written* (repo is currently
docs-only — the cheapest moment).

**Decided since (the performance review → ADR 0011, quality held constant):** the DAG is
**lane-forked** after 00b into a concurrent **visual lane (GPU)** and **audio lane (CPU)** rejoining
at 05 — overlapping the two heaviest time sinks without touching "never co-resident"; plus
**GPU swap minimization + RAM pre-staging**, **per-video CPU fan-out**, **LLM prompt/KV-cache
reuse**, the **production stage-cache**, **NVENC pipelining**, and **I/O hygiene** — each adopted
behind a **per-stage/per-batch timing metric** off the M1 baseline. The post-render gates
(05x/05b/05c) are **deliberately left split** (a gate-collapse onto one model was considered and
rejected — wrong place to trade quality for one swap/day).

**Decided since (the implementation-readiness review → ADR 0012):** the concrete **M0 build
contract** that turns M0 from a design brief into a buildable milestone — the `input_hash`
canonicalization, the Stage `ctx` interface, the stage-metadata manifest (generator deferred),
the `job.json` **status enum**, `schema_version` semantics (fail-on-major / warn-on-minor), typed
**adapter Protocols**, the fake→fixture lookup + one **golden-fixture chain**, an explicit
**deliverable ordering**, and an **M0 acceptance checklist** that defines "done." Plus the
scope clarification that authoring the prose contracts *is* the M0 work.

**Decided since (the Windows-host question → ADR 0013):** the system runs on Windows by hosting the
**entire Linux stack inside one WSL2 distro** (GPU plane + control plane), Windows being just the
substrate + the NVIDIA driver — near-zero divergence from the Linux design. GPU overhead is a few
percent for this GPU-saturating workload (not the feared 95% loss); the real Windows costs are
**tighter VRAM** (hardens quantized-LTX) and two ops pieces (Task-Scheduler keep-alive, `.wslconfig`).
Driver discipline (Windows driver only, WSL-Ubuntu CUDA toolkit, cu128, pinned Blackwell Ollama) and
**data on ext4 not `/mnt/c`** are the setup rules. A thin `scripts/win/shorts.ps1` is the PowerShell
entry point; the bash scripts stay the single source of truth.

**Decided since (the content-automation best-practice audit → ADR 0014):** benchmarked the design
against current (2026) short-form practice + the **2026 enforcement climate** (YouTube's
"inauthentic content" rename + the Jan-2026 mass-termination wave; TikTok's AI-label rules). The
craft layer already matched best practice; three gaps were folded in — (1) **`05c` enforces
"original insight / authentic perspective"** and the DoD names it, because the inauthentic-content
policy makes it a *monetization-survival* property (clause 2); (2) **cadence is enforcement-sensitive**
— the ramp starts low and widens on a track record, density over volume (Ch.2); (3) a **per-platform
`publish_window`** captures the first-hours-velocity reach lever (06, config no-op for M0); plus a
recorded **no-community-engagement** ceiling. Blanket AI-disclosure (ADR 0004/0009) kept as the safe
choice; granular disclosure deferred.

**Decided since (the watchability review → ADR 0017):** the machine is sound but the **creative
identity was underdetermined** — so the three levers that actually decide whether the output is
*watchable* (not just usable) become decisions: (1) the **voice A/B is an M3 gate** judged on
expressiveness/hook-delivery (a hosted voice the recorded escalation); (2) **data-viz is the
visual identity** — abstract/textural stock bias + a literal-cliché denylist, the branded
number-card preferred over stock people; (3) the **persona is an opinionated character** —
required stance-list + catchphrase + recurring series, written *from* (not summarized neutrally),
which also feeds the original-insight gate. Plus the **text-first hook card as default**, a
**brand mascot**, and the **energy curve driving voice-rate/music-intensity/cut-pacing** (ADR 0007a
§5 activated). An avatar layer is the recorded future ceiling-breaker; trend participation stays
declined.

**Decided since (the architecture re-review → ADR 0015 / 0016):** the control plane goes
**runner-first** — the M0 Python conductor (stage manifests → topology, cache, status, quarantine)
is the **production orchestrator**, scheduled by a **WSL2 systemd timer**, with **kind/Argo demoted
to a deferred deployment profile** (a CI-built shared image + dumb templates keep
"Kubernetes-deployable" a continuously *tested* property — ADR 0015); **one filesystem /
`DATA_ROOT`** closes the host↔pod path-translation gap (ComfyUI outputs land under it); **M4 is
rescoped** to conductor hardening. **Gate integrity (ADR 0016):** an **independent non-Qwen judge**
for 05c (closes ADR 0009 #4) with the **ramp's approve/reject labels captured as the calibration
set**; a **script-time floor at 00b** (all-bad batches quarantine before any GPU spend); **per-cut
coverage decided** — one VLM pass on the YouTube cut + deterministic per-cut safe-zone math in 05b;
**05x emits observations + visual sub-scores, not verdicts**, served via an OpenAI-compatible
endpoint. Plus three operational corrections: the **PoC lane-mix default flips reach-heavy ~80/20**
(ADR 0006 D2 — the ~60% monetization tilt waits for TikTok-audit + YPP eligibility);
**FRED/stooq for daily series, Alpha Vantage quotes-only** (ADR 0009 #8); the **OAuth app moves to
Production status + token-age pre-flight** (ADR 0009 #10 — Testing-status tokens expire at 7 days,
mid-endurance-run). **The Kubernetes profile is fully designed (ADR 0015a):** a three-rung
adoption ladder (CronJob conductor → Argo fan-out → GPU-in-cluster on a dedicated Linux node),
generated-not-hand-written templates, the `DATA_ROOT`-relative path contract, and a kind smoke
test — buildable as optional **M7** without touching stage semantics.

**Still open (tracked):**

1. **Contracts + M0 conventions (P0).** Write
   `schemas/{job,script,assets,provenance,vision,qc,creative_qc,posts,profile,format,feature_record}.schema.json`
   *before* stage code — they are every stage's interface — each with a **`schema_version`** and a
   **fail-loud validation harness + golden fixtures** (ADR 0010). `script.schema` carries the
   **structured per-beat layout data** the format templates bind to (ADR 0007). Stand up the
   **Stage SDK**, the **adapter interfaces** (`DistributionAdapter` / model backends /
   `LayoutEngine`), and the **fake-backend offline harness + content-addressed stage cache** in the
   same M0 pass.
2. **Per-platform render differentiation** — concrete deltas (caption safe-zones / cover frame /
   hook timing / LUFS / **engagement-CTA verb + icon** — YT Subscribe+bell vs TikTok/IG Follow,
   ADR 0005 D10), so YouTube and TikTok cuts aren't a penalized dupe re-encode.
3. **Numeric tuning** — 05b safety thresholds + ramp-exit criteria; **05c quality floor + judge
   rubric weights + N** (ADR 0005); retry counts / backoff / per-stage timeouts; the re-measured
   throughput baseline.
4. **ADR 0002 residue** — per-niche RSS source list; topic-overlap threshold default; embedding
   model for the post-M1 similarity tier; optional free-tier news API.
5. **Posture residue (ADR 0004)** — public-vs-private account counts per niche; affiliate program
   selection + disclosure wording (kept disabled until decided).
6. **Quality-layer residue (ADR 0005)** — CLIP relevance model + data-viz tech; curated music +
   SFX libraries; the pronunciation lexicon; per-niche persona + brand kit.
7. **Algorithm-fit residue (ADR 0006)** — exact per-format second-ranges + which formats must
   loop; the end-card phrase library + rotation policy; whether `05c` factors a predicted-
   completion heuristic; revisit all against **real** retention data when analytics lands.
8. **Layout-engine residue (ADR 0007 / 0007a)** — **resolved**: engine **locked to Remotion**
   (ADR 0007 §4 D4, ≤3-person tripwire); the hybrid region model + `layout.schema.json`, the closed
   primitive + animation/transition libraries, the `ranked_list` + `head_to_head` exemplars,
   **fps = 30**, and **CPU raster + NVENC** (GPU-Chromium rejected) in **ADR 0007a**. **Still open:**
   author the other **6 region specs as data** (M3); **run** the 0007a §9 throughput method on the
   box (rolls into #9); validate the default safe insets/grid anchors on real platform UIs (M2).
9. **Parity residue (ADR 0008)** — the **VLM choice + frame-sampling** strategy and its VRAM cost;
   per-format `lane_support` + content-scaling values; the **end-to-end throughput reconciliation**
   across ADR 0005–0008 on the real box.
10. **Content-integrity residue (ADR 0009)** — numeric-match **tolerance rules**; ~~whether to run
    a separate judge model~~ **resolved: an independent non-Qwen judge is decided (ADR 0016 D1),
    and the calibration set comes from the ramp's approve/reject labels (ADR 0016 D2)** — still
    open: the judge **model pick + prompt** (at M3 bring-up) and the **floor values** (00b
    provisional + 05c, re-anchored from the labels); per-platform **music libraries** + verified
    terms; **warming duration** + provisioning checklist; per-API **budget numbers** + cache TTLs;
    the **corroboration threshold** + reputable-source list per niche.
11. **Extensibility / M0-build residue (ADR 0010 / 0012)** — ADR 0012 pinned the `input_hash`,
    `ctx`, status enum, manifest shape, and adapter Protocols; **still open**: the **cache backend
    substrate** (file vs sqlite) + eviction/TTL; the **fake-backend fidelity bar** (fixture replay
    vs a tiny real CI model); whether the **feature record** lives in the ledger or a separate
    metrics store.
12. **Performance residue (ADR 0011)** — the **timing-metric** shape + M1 baseline numbers; the
    lane-fork **CPU/RAM bounds** (so the audio lane doesn't starve the host serving the GPU plane);
    whether RAM pre-staging / NVENC pipelining clear the measurement bar at PoC batch sizes.
13. **Post-M1 A/B (non-blocking)** — LTX vs Wan2.1/CogVideoX; ~~Kokoro vs Orpheus/Chatterbox~~
    **(promoted to an M3 *gate* — the voice is the #1 watchability limiter, ADR 0017 D1 — judged
    on expressiveness/hook-delivery, with a hosted voice as the recorded escalation)**;
    FLUX-schnell vs photoreal SDXL/SD3.5; **Qwen-32B with RAM offload for 00b** (the script stage
    is where model quality matters most).

**Parked — monetization funnel & affiliate (decided, deferred to post-PoC).** A brainstorm
(2026-06-09) settled a monetization thesis — Shorts as a **data-authority top-of-funnel** to an
owned destination, with **finance affiliate** as the eventual payoff and success measured as
*qualified outbound intent* (click-through + email capture). **The affiliate/funnel work is
deferred in full** until after a **views-first PoC**, because the outbound-CTA + capture changes
touch the layout templates (ADR 0007 / 0007a) and we are **not changing templates now**. For the
PoC the engine ships and **posts publicly as designed** (private-first **+ ≥1 public**, ADR 0004
D4 / ADR 0009) and optimizes for **views** as its working success signal; affiliate fields stay
**disabled** (ADR 0004 D5); the CTA reframe (ADR 0006), the withhold-the-payoff content split
(ADR 0008), and any capture surface are revisited once the engine proves it produces watchable
finance shorts. *Consequence held knowingly:* with the funnel parked, the success signal stays the
self-referential `05c` quality gate until the deferred analytics loop lands — so **low views won't
be self-diagnosing** in the PoC. M0 is unaffected (monetization-agnostic).

---

*End of specification. Topology diagrams: [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
Decision records: [`docs/decisions/`](../../decisions/).*

