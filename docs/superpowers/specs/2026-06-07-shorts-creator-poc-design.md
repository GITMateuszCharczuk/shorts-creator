# Shorts-Creator PoC — Design Specification

> **Status:** Design spec (pre-implementation). Synthesizes the locked decisions across
> `docs/POC.md` (scope), `docs/DESIGN.md` (architecture), `docs/OPTIONS.md` (tooling),
> `docs/REVIEW.md` (findings), `docs/research/01–05` (evidence), and the ADRs
> [0001 — lightened runtime](../../decisions/0001-lightened-runtime-architecture.md),
> [0002 — recency & novelty](../../decisions/0002-recency-and-novelty-ledger.md),
> [0003 — resilience, concurrency & observability](../../decisions/0003-resilience-concurrency-observability.md),
> [0004 — commercial posture & account-safety](../../decisions/0004-poc-commercial-posture-and-account-safety.md),
> [0005 — editorial quality layer](../../decisions/0005-editorial-quality-layer.md), and
> [0006 — algorithm-fit & format tuning](../../decisions/0006-algorithm-fit-and-format-tuning.md).
> The full topology diagrams live in [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
>
> **Precedence:** the ADRs win on runtime topology; `POC.md` wins on scope. This spec is the
> single synthesized reference for implementation planning and review.
>
> **Date:** 2026-06-07

---

## Chapter 1 — Overview & definition of done

**What it is.** A free, self-hostable, Kubernetes-native (`kind`) pipeline that produces and
posts **per-format-length** vertical (9:16) videos for **Finance** and **Business** to **YouTube
Shorts** and **TikTok**, fully unattended. Length is set **per format** (ADR 0006): punchy formats
run **~20–35s** for completion/attention, depth formats **~61–90s (over 1 min)** to stay
TikTok-monetization-eligible. Two lanes, chosen per format; a configurable **rolling-window mix
targets ~60% of videos in the ≥61s monetization lane** (ADR 0006) — superseding the flat 60–90s
rule.

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
   captions, a coherent script with a real hook. The creative-QC gate is what makes this clause
   *enforceable* rather than aspirational: a boring-but-safe video is quarantined, not posted.
3. **Real posting.** Videos upload through the **real** YouTube Data API v3 and TikTok Content
   Posting API to **real, live, new accounts**, defaulting to private/unlisted.
4. **Stability.** The system runs **~1–2 weeks** producing its daily batch without manual
   intervention — clean logs, provenance, no silent failures.

**Explicitly out of the done-definition (ADR 0004 D1):** this PoC proves the **engineering
loop** only — it **deliberately does not validate commercial viability**. Revenue,
monetization thresholds, and view/retention targets belong to the *next* phase. "Done" must
not be read as "this makes money." *(To still earn a minimum real-world signal, ADR 0004 D4
runs ≥1 genuinely **public** account per platform alongside the private-first ones.)*

## Chapter 2 — Scope

**In scope:**

| Dimension | Decision | Rationale |
|---|---|---|
| **Niches** | **Finance + Business** (two profiles) | Both high-RPM, both automate from real data, both avoid the true-crime legal landmine; two genuinely different configs exercise the niche-profile abstraction. |
| **Platforms** | **YouTube Shorts + TikTok** | Exercises multi-platform native renders. TikTok is the only short-form leg that meaningfully pays; YouTube is the easiest to stand up. |
| **Pipeline** | Full end-to-end (research → script → visuals → voice → subs → music → render → QC → distribute) | The whole loop on the narrow slice. |
| **Mode** | **Auto + safety-net** | Automation gated by the QC gate + phased ramp + weekly spot-audit. |
| **Posting** | **Private-first**; **≥1 public account per platform** (ADR 0004 D4); public = a single per-platform config flag | Decouples engineering from audit timelines we don't control, while still earning a minimum reach/retention signal. |
| **Cadence** | **1–2 / day / niche** (~2–4/day), phased ramp | Well under YouTube's ~6 uploads/day; the "start small, prove compliance" posture the inauthentic-content policy demands. |
| **Hardware** | Single **RTX 5070 Ti, 16 GB** (Blackwell, sm_120) | See Chapter 7 for the GPU budget + toolchain caveat. |

**Out of scope (deferred — architecture must not preclude):**

- **True crime niche** — dropped *entirely* (not "later"). Catastrophic, automation-incompatible
  defamation risk (`research/04 R3`: $17.5M verdict; an AI true-crime channel terminated).
- **Facebook + Instagram Reels** — deferred (Reels ad-share is pennies; IG needs Business
  account + Meta App Review). The render stage stays platform-generic.
- **Long-form companions + affiliate** — the real revenue levers, a distinct future phase.
- **Multi-account / scale-out, web UI, cloud GPU autoscaling, analytics feedback loop.**

Each **niche profile** (`profiles/*.yaml`) carries not just prompts but an **editorial persona /
point of view** the 00b model writes *in* (ADR 0005 D9) and a **brand kit** (palette, font, logo
bug, lower-third + citation-chip templates, thumbnail/cover template, **+ a channel-styled
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
| **00b script** | CPU →host LLM | Qwen2.5-14B writing **in the channel persona** (ADR 0005 D9) → **selects + rotates a format template** (Chapter 6) → emits a **treatment** (thesis/angle/tone, per-beat visual motif, energy curve — the through-line every later stage renders against) → **best-of-N** scripts, **judge picks the winner** (ADR 0005 D1/D2). Output: a first-class **hook composite** {spoken, on-screen text, first-frame visual, ≤2s}, narration beats with **prosody + emphasis markup**, on-screen captions with **emphasis-word tags**, per-beat visual motif, music **mood+energy**, a **primary keyword** (for caption/on-screen/spoken placement) and the **per-format target length** (~20–35s reach / ~61–90s monetization — ADR 0006), per-platform title/desc/hashtags. **YMYL:** mandatory disclaimer, no buy/sell/price calls, on-screen citations, accuracy self-check. **Dedup:** `history/ledger.jsonl` (cross-run) **+ reserve the pick in `batch.json`** (intra-batch — ADR 0003 D5). Optional affiliate fields (ADR 0004 D5). | `script.json` (+ `treatment`) |
| **01a stock-fetch** | CPU | Real vertical clips/photos from Pexels/Pixabay/Mixkit/Coverr/Videvo (license verified, source logged). **Pulls N candidates per beat, ranks by image-text similarity (e.g. CLIP) against the beat's visual motif, dedups against clips used in other batch videos + the ledger** (ADR 0005 D5) — below-threshold beats fall through to 01b/01e. Real footage is the backbone. | `scenes/` + provenance |
| **01b image-gen** | →host ComfyUI | FLUX.1-schnell photoreal stills for the un-stockable only. | `scenes/` fills |
| **01c img2vid** | →host ComfyUI | LTX-Video (img→video on real frames) / Ken Burns. AI motion kept to short fill clips. | `scenes/` clips |
| **01d upscale-restore** | →host ComfyUI | Real-ESRGAN upscale + RIFE interpolation + GFPGAN/CodeFormer face restore on AI frames. | `assets.json` |
| **01e data-viz** | CPU | **Branded animated charts / counters / stat reveals** rendered from `data.json` numbers (ADR 0005 D5) — deterministic, artifact-free, license-free; the finance niche's signature visual *and* a citation surface. Fills beats stock can never match. | `scenes/` viz clips |
| **02 voice** | CPU | Kokoro-82M narration, driven by a **finance text-normalization + pronunciation lexicon** (`$1.5M`, `401(k)`, `FOMC`…) and **per-beat prosody/emphasis/pause markup** incl. a deliberate hook delivery (ADR 0005 D6); the **primary keyword is spoken in the opening lines** (ADR 0006). | `narration.wav` |
| **03 subtitles** | CPU | WhisperX `int8` word-level alignment → **designed** karaoke captions: brand font, ≤N words on-screen, stroke/shadow, **emphasis-word styling**, animation, **per-platform vertical safe zones** (ADR 0005 D7); the **primary keyword appears as on-screen text in the first 2–3s** (ADR 0006). | `captions.ass/.srt` |
| **04 music** | CPU | Strike-safe track from a **curated library, selected by a closed mood/energy taxonomy tied to the format** (anti-repeat across the batch) + a **transition-SFX layer** (whoosh/tick/reveal), ducked under VO (sidechain), **per-platform LUFS** (ADR 0005 D6). | `music.wav` + sfx |
| **05 render** | CPU (ffmpeg) | Editorial compose: **word-timed cuts + visual-change-rate target** (no slideshow), **per-clip color *matching* before** the unifying grade, **brand overlay** system incl. a **per-platform animated engagement-CTA bump** (`Like` + `Subscribe`/`Follow`) at a **seeded constrained-random mid-roll slot** (ADR 0005 D10), designed **thumbnail/cover** (TikTok cover = frame 1), a **seamless loop bridge** (last beat → hook, for replay-driven AVD) and a **closing FOMO follow end-card** (ADR 0006) → **distinct native cuts for YouTube + TikTok** (ADR 0005 D4). | `renders/{youtube,tiktok}.mp4`, `thumbnail.jpg` |
| **05b safety gate** | CPU +host LLM | The always-on **account-safety gate** (Chapter 8, ADR 0004 D3): YMYL disclaimer present, no buy/sell calls, sources cited, AI-disclosure set, profanity/claims clear, repetitious-content check vs ledger, render integrity — **+ aesthetic/artifact checks** (morphing hands, temporal warp, garbled AI text) **and audio-defect checks** (hook dead-air, loudness window, synth-duration match) (ADR 0005 D8). Pass → continue; fail → quarantine. | `qc.json` |
| **05c creative-QC** | CPU →host LLM | The **quality gate** (ADR 0005 D2), distinct from safety: judge scores the assembled video (hook strength, non-obvious take, visual↔script coherence, payoff) vs a **quality floor**. Above floor → distribute; below → **quarantine, not post**. | `creative_qc.json` |
| **06 distribute** | CPU | Per-platform **distribution adapters** (YouTube Data API v3 + TikTok Content Posting API), **exactly-once** via the `(video_id, platform)` **posted-state ledger** (`history/posts.jsonl`, ADR 0003 D1), **private-first / ≥1 public**, **AI-disclosure on every call**, the **primary keyword leads the caption's first ~150 chars** (ADR 0006), emits affiliate description when enabled. Append the novelty ledger via the batch's single fan-in commit step. | post receipts |

All clips are normalized to **1080×1920**. The scene manifest (`assets.json`) plus the
`job.json` spine make any video reconstructable.

## Chapter 5 — Data contracts & storage

**Contracts first (REVIEW C2 / P0).** The stage interfaces *are* the architecture, so they are
the **first committed code artifact**, as versioned JSON Schema under `schemas/`, validated at
every stage boundary:

- **`job.schema.json`** — the spine threaded through every stage: `batch_id`, `video_id`, niche,
  profile, platform targets, per-stage status, and the run's file paths.
- **`script.schema.json`** — Stage 00b output: the chosen **`format`** (Chapter 6); a
  **`treatment`** block (thesis/angle/tone, per-beat visual motif, energy curve — ADR 0005 D1);
  a first-class **`hook`** composite (`{spoken, on_screen_text, first_frame_visual, duration}`)
  plus its scored variants; narration beats **with prosody/emphasis markup**; captions with
  emphasis tags; per-beat visual motif; music **mood+energy**; per-platform metadata;
  claims + citations; disclaimer; and **optional affiliate fields** (ADR 0004 D5).
- **`creative_qc.schema.json`** — Stage 05c output: the judge's per-criterion scores + overall
  quality score vs the floor (ADR 0005 D2). Distinct from `qc.schema.json` (safety).
- **`assets.schema.json`** — Stage 01d output: the final scene manifest (one normalized clip per
  beat).
- **`provenance.schema.json`** — per asset: `source`, `url`, `license`, `fetch_date`.
- **`qc.schema.json`** — Stage 05b output: the account-safety gate's per-check pass/fail + verdict.
- **`posts.schema.json`** — the posted-state record keyed `(video_id, platform)`: intent →
  confirmed (with the remote post id). The **exactly-once** backbone (ADR 0003 D1), kept
  separate from the novelty ledger.

**Storage — a single PVC, host-backed for durability.** The data volume is backed by a host
directory via kind `extraMounts`, so it **survives `kind delete cluster` and reboots** — not
cosmetic: cross-run dedup is only possible because the ledger persists.

```
 PVC: shorts-data  →  host dir via kind extraMounts
 └── runs/<batch-id>/
     ├── batch.json                # which videos, profiles, status
     ├── data/                     # 00a: market data + recent news (≤3d)
     └── <video-id>/
         ├── job.json  script.json (+treatment)  assets.json  provenance.json
         ├── scenes/  narration.wav  captions.ass/.srt  music.wav
         ├── renders/{youtube,tiktok}.mp4  thumbnail.jpg
         └── qc.json  creative_qc.json
 └── quarantine/<video-id>/        # 05b failures; retention/GC policy (ADR 0003 D8)
 └── history/ledger.jsonl          # append-only novelty ledger (Chapter 6)
 └── history/posts.jsonl           # posted-state ledger, (video,platform) exactly-once (ADR 0003 D1)
 └── models/                       # host-mounted shared weight cache (downloaded once)
```

No MinIO (REVIEW T5). Argo passes artifacts **by path** on this shared volume. Both `*.jsonl`
ledgers are written by a **single fan-in commit step per batch** (no concurrent appenders —
ADR 0003 D6), and a **pre-batch free-space gate** guards against the disk-full SPOF.

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
  pattern + structure + length target + any format-specific QC notes), so adding/retiring a
  format is **data, not a code change**.
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
`Qwen → evict → FLUX → evict → LTX → evict → ESRGAN/RIFE/GFPGAN`. ComfyUI's queue serializes the
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
must be **re-measured**, not assumed.

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
  run under a supervisor (`systemd Restart=always`) with `/health` endpoints; Argo **gates
  fan-out on host health** (fail-fast + alert, not a retry-storm) and a **batch-level circuit
  breaker** halts on repeated host failures. An unreachable host fails the step (→ retry/backoff)
  with a hard poll timeout + `activeDeadlineSeconds` — it never hangs (ADR 0003 D2/D3).
- **Pre-flight gates.** Before fan-out: a **free-space check** (disk-full SPOF) and an
  **OAuth-token validity/refresh check** (ADR 0003 D8); `quarantine/` and old `runs/` are GC'd.

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

**The creative-QC quality gate (Stage 5c) — distinct from safety (ADR 0005 D2)**
- **Purpose:** enforce the DoD's "genuinely good, not slop" clause. 05b asks *"is it safe to
  post?"*; 05c asks *"is it worth watching?"* — two different questions, two gates.
- **Mechanism:** the LLM-as-judge (the same one that picks the best-of-N at 00b) scores the
  assembled video against a rubric — **hook strength, says-something-non-obvious, visual↔script
  coherence, payoff lands** — to an overall **quality floor**.
- **Outcome:** above floor → distribute; **below floor → quarantine, not post.** A boring-but-safe
  video is held back, which is the whole point — without 05c the quality bar is aspirational.
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
- **One-time setup (multi-step):** `make host-up` (ComfyUI + models + LLM) · `make cluster-up`
  (kind + Argo + the host-backed PVC; *no GPU device-plugin*) · `make build` (build + `kind load`
  stage images) · `make wire` (verify pods reach the host endpoint).
- **Per run (light / hands-off):** `make submit-batch PROFILES=finance,business` · `make dry-run`
  (stage metadata, post nothing) · or the `CronWorkflow` fires the daily batch automatically.

**Testing (`POC §6`)**
- Schema validation on `job.json` and every stage output.
- Unit tests on the deterministic seams: script/treatment-schema adherence, finance text
  normalization, stock relevance-ranking, music selection, render-arg construction, QC heuristics
  (safety + creative), and dedup matching. TDD where it fits.

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
human-at-publish step, plus the audit where required.

**True crime is dropped entirely** — catastrophic, automation-incompatible defamation risk.

## Chapter 10 — Milestones & open decisions

**Milestones (refines `POC §7` to the lightened architecture):**

| M | Goal |
|---|---|
| **M0** | Scaffold & cluster: repo structure, `kind` up, **host GPU verified** (ComfyUI + LLM reachable from a pod — *not* GPU-in-kind, under the host supervisor + lease), Argo installed, **the seven schemas** (`job/script/assets/provenance/qc/creative_qc/posts`) + validation, the observability stack bootstrapped, CI running the unit tests. |
| **M1** | Vertical slice: `00a → 00b (Qwen: treatment + best-of-N + judge) → 02 (Kokoro) → 03 (WhisperX) → 05 (ffmpeg, stills + Ken Burns)` → a real `final.mp4` for **finance**. Proves the shape end-to-end. |
| **M2** | Visuals for real: `01a` stock-first **(CLIP relevance + dedup)** + `01b` FLUX fill + `01c` LTX img→video + `01d` upscale/restore + **`01e` data-viz** — the "not obviously AI" look + the finance signature visual dialed in. |
| **M3** | Audio performance layer (normalization/prosody/music taxonomy/SFX), **caption design**, the **`05c` creative-QC gate**, persona + brand kit, **business** profile — proving the two-niche abstraction *and* the quality bar. |
| **M4** | Orchestration: `WorkflowTemplate` + `CronWorkflow` (`concurrencyPolicy: Forbid`), **per-video failure domains**, GPU lease + confirm-evicted gate, retries/timeouts, artifacts, **stage-batching**, the phased daily batch. |
| **M5** | Account-safety gate (`05b`) + distribution (`06`, per-platform adapters + the `posts.jsonl` exactly-once ledger) to YouTube + TikTok; private-first **plus ≥1 public**; disclosure on; **human-at-publish ramp**; affiliate fields wired (can ship disabled); platform audits submitted in parallel. |
| **M6** | Hardening + alerts/GC/credential pre-flight wired, then the **1–2 week unattended run** (post-ramp) that satisfies the Chapter 1 definition of done. |

**Decided since (the runtime review → ADR 0003 / 0004):** Stage 6 exactly-once
(posted-state ledger); host GPU lease + confirm-evicted gate + `Forbid` concurrency; host
supervision + readiness gate; per-video failure domains; intra-batch dedup claim + starvation
ladder + timestamp hygiene; serialized ledger writes; observability backend; disk GC +
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

**Still open (tracked):**

1. **Contracts (P0).** Write `schemas/{job,script,assets,provenance,qc,creative_qc,posts}.schema.json`
   *before* stage code — they are every stage's interface.
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
8. **Post-M1 A/B (non-blocking)** — LTX vs Wan2.1/CogVideoX; Kokoro vs Orpheus/Chatterbox;
   FLUX-schnell vs photoreal SDXL/SD3.5; **Qwen-32B with RAM offload for 00b** (the script stage
   is where model quality matters most).

---

*End of specification. Topology diagrams: [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md).
Decision records: [`docs/decisions/`](../../decisions/).*

