# Shorts Creator — Design & Implementation Plan

A Kubernetes-native (Kind-compatible) data pipeline that automatically produces and
publishes short-form vertical video across multiple niches and platforms using free,
self-hostable AI tools.

> Status: **Plan / pre-implementation**. This document is the agreed blueprint. No
> pipeline code exists yet.
>
> ⚠️ **Scope note:** this doc describes the broader 3-niche / 4-platform vision. The
> **current build is narrowed** to a proof-of-concept — **Finance + Business** on
> **YouTube + TikTok**, private-first. See **[POC.md](POC.md)**, which is authoritative on
> present scope; treat true-crime / FB / IG / tech-news mentions here as future vision.

---

## 1. Goals & non-goals

> **Strategy note:** the content/monetization fundamentals — niches, platforms, earnings,
> automation policy, compliance — live in **`STRATEGY.md`**. This doc covers architecture.

**Goals**
- Generate full, ready-to-publish vertical (9:16) videos end-to-end, **auto + safety-net**
  (full automation gated by automated QC, phased ramp, weekly spot-audit — see STRATEGY §4).
- **3 channels / niches:** **Finance**, **True crime**, **Business** (high-RPM cluster).
- **Length 60–90s** (required for TikTok payouts; hook-first, retention-optimized).
- **Multi-platform distribution:** YouTube Shorts + TikTok + Facebook Reels + Instagram
  Reels, with **distinct native renders per platform** (no foreign watermarks; dodges
  duplicate-content penalties). FB/TikTok are the earners; YT/IG are reach/funnel.
- Visuals that look polished and **not obviously AI-generated** (hybrid real footage + AI).
- Subtitles, AI narration (dub), and fitting background music per video.
- Optional automated upload to YouTube.
- Run **locally on `kind`** (Kubernetes in Docker), container-native, reproducible.
- **No recurring cost** — all tools free/self-hosted.
- **No copyright strikes** and **commercial/monetization-safe** licensing throughout.

**Non-goals (for v1)**
- Multi-account / multi-channel management.
- A web UI (CLI + Argo UI is enough to start).
- Cloud GPU autoscaling (single local GPU box assumed).

> *(Removed an obsolete non-goal that listed "cross-posting to TikTok/Reels" as out of
> scope — multi-platform distribution is now a core goal; see §1 Goals and Stage 6.)*

---

## 2. Decisions (from requirements Q&A)

| Topic | Decision |
|---|---|
| Niches / channels | **Finance · True crime · Business** (3 channels) — see STRATEGY §2. |
| Monetization | **Ad-share, multi-platform** (FB Reels + TikTok primary earners) — STRATEGY §1. |
| Distribution | **YouTube + TikTok + Facebook + Instagram**, native per-platform renders. |
| Video length | **60–90s** (TikTok payout requirement; hook-first). |
| Automation | **Auto + safety-net** (QC gate + phased ramp + spot-audit) — STRATEGY §4. |
| GPU | **RTX 5070 Ti, 16 GB VRAM** available locally. |
| Visual style | **Real-footage-first hybrid**: real 4K stock is the backbone; AI fills only genuine gaps; prefer **img→video on real frames** over text→video. AI video always carries an "AI look", so it is used sparingly. |
| Script LLM | **Qwen2.5-14B-Instruct** (Apache-2.0, fits 16 GB) — upgraded from 7B for quality. |
| Monetization | **Yes** → strict commercial-safe licenses only. |
| Orchestration | **Argo Workflows** on `kind` — confirmed. |
| GPU exposure | **GPU inside kind** (NVIDIA Container Toolkit + k8s device plugin) — confirmed. |
| Image generation | **FLUX.1-schnell** (Apache-2.0) — confirmed. |
| Motion | **LTX-Video** (img→video) wired in from the start — confirmed (A/B vs Wan2.1/CogVideoX after M1). |
| Voice | **Kokoro-82M** for M1 (A/B vs Orpheus/Chatterbox after M1). |
| Finishing polish | **GFPGAN/CodeFormer** face restoration + color grade + film grain + motion blur in render — baked in. |
| First deliverable | This plan document. |

### 2.1 Hardware caveat — Blackwell (sm_120)
The RTX 5070 Ti is **Blackwell architecture, compute capability sm_120**. Practical impact:
- Requires **CUDA 12.8+** and a **PyTorch build that includes sm_120 kernels** (recent
  stable or nightly `cu128` wheels). Older default `torch` wheels will fail with
  `no kernel image is available for execution on the device`.
- Base container images for GPU steps must use a matching CUDA runtime
  (`nvidia/cuda:12.8.x-runtime` or newer) and install the correct torch index URL.
- This is the single most likely "it doesn't work on my box" issue — pinned and
  documented in each GPU step's Dockerfile.

---

## 3. High-level architecture

```
                        ┌────────────────────────────────────────────────────┐
                        │                 kind cluster                        │
                        │                                                     │
  CronWorkflow ───────► │  Argo Workflows controller                          │
  (N videos/day,        │        │                                            │
   per category)        │        ▼  (DAG, one container per stage)            │
                        │  ┌──────────┐  artifacts via MinIO / shared PVC     │
                        │  │ 0 script │──┐                                     │
                        │  └──────────┘  │                                     │
                        │  ┌──────────┐  ▼                                     │
                        │  │ 1 assets │  scenes.json + media refs              │
                        │  │ (visuals)│  (GPU node)                            │
                        │  └──────────┘                                        │
                        │  ┌──────────┐                                        │
                        │  │ 2 voice  │  narration.wav  (GPU/CPU)              │
                        │  └──────────┘                                        │
                        │  ┌──────────┐                                        │
                        │  │ 3 subs   │  captions.ass   (GPU whisper align)    │
                        │  └──────────┘                                        │
                        │  ┌──────────┐                                        │
                        │  │ 4 music  │  picks track, ducks under VO           │
                        │  └──────────┘                                        │
                        │  ┌──────────┐                                        │
                        │  │ 5 render │  ffmpeg mux → final.mp4 (9:16)         │
                        │  └──────────┘                                        │
                        │  ┌──────────┐                                        │
                        │  │ 6 upload │  YouTube Data API v3 (optional)        │
                        │  └──────────┘                                        │
                        └────────────────────────────────────────────────────┘
```

**Why Argo Workflows:** container-native DAG, each stage is an independent image with
its own deps (huge + conflicting Python/CUDA stacks per stage), built-in artifact
passing, retries, parameters (category), and a `CronWorkflow` scheduler. Runs cleanly
on `kind`. Alternatives considered: Kubeflow (too heavy/ML-training oriented),
Airflow/Dagster/Prefect (more app-level, weaker container-per-task story), raw K8s Jobs
+ queue (more glue code).

**Artifact passing:** a per-run working directory on a **shared PVC** for large media,
plus **MinIO** (S3-compatible) as the Argo artifact repository for stage inputs/outputs
and for the final video. A small JSON manifest (`job.json`) threads through every stage
describing the video being built.

**GPU scheduling on kind:** the cluster has one GPU node. GPU steps (visuals, TTS,
whisper) request `nvidia.com/gpu: 1`; CPU steps (script via Ollama-as-a-service, music
selection, ffmpeg render, upload) do not. See §9 for the kind GPU enablement steps.

---

## 4. Pipeline stages (detailed)

Each stage = one container image, one Argo template. Inputs/outputs are files in the
run workdir, described by `job.json`.

### Stage 0 — Script & storyboard (CPU)
- **Purpose:** From `channel` (+ optional topic/seed), produce a **60–90s, hook-first**
  script: **multiple scroll-stopping hook variants** (first 1–2s is the whole ballgame),
  narration beats with a retention curve, on-screen captions, per-scene **visual keywords**,
  music **mood**, and **per-platform** title/description/hashtags. For Finance/Business it
  also fetches **real data** (Alpha Vantage / Yahoo Finance / FRED) for original charts and
  injects the mandatory **"educational, not financial advice"** disclaimer. Output
  `script.json`.
- **Tool:** **Ollama** running as an in-cluster service (Deployment + Service), model
  **Qwen2.5-14B-Instruct** (Apache-2.0; fits 16 GB at Q4/Q5). Upgraded from 7B because
  script quality is the highest-leverage lever on perceived video quality. Since the LLM
  runs as a distinct stage, the GPU is free for media work the rest of the time; 32B is a
  possible future bump with RAM offload (6/day absorbs the slower inference).
- **Prompting:** per-category system prompts + a strict JSON schema (validated before
  the stage exits). Templates live in `prompts/<category>.md`.
- **Risk control:** for **history / geopolitics**, add a "claims" field and a
  lightweight self-check pass; flag low-confidence facts. (See §6 accuracy.)
- **License:** ✅ commercial-OK.

### Stage 1 — Visuals / assets (GPU) — the "not fully AI" strategy
This is the differentiator. Strategy: **real footage first, AI to fill gaps, GPU for
motion & polish.**

**Real-footage-first.** The decided strategy weights real stock heavily; AI fills only
genuine gaps. AI video always carries an "AI look", so we minimise it.

1. **Stock-first retrieval (primary source).** For each scene's keywords, pull **real**
   vertical clips/photos from **Pexels, Pixabay, Mixkit, Coverr, Videvo** (all free; each
   license verified for commercial use; source logged regardless). Real 4K B-roll is the
   backbone and the main reason output looks real, not AI.
2. **AI fill for the un-stockable only.** Categories like *history* and *horror* need
   scenes no stock library has ("a Roman legion at dusk"). For those, generate photoreal
   stills with **FLUX.1-schnell** (Apache-2.0), tuned for realism, not "AI art".
3. **Add motion (GPU) — prefer animating real frames.** Favour **img→video on a real
   stock frame or photoreal still** (stays real) over text→video (drifts into AI-land).
   **LTX-Video** for M1; apply **Ken Burns** (`ffmpeg zoompan`) when img2vid is overkill.
   (Wan2.1 / CogVideoX A/B vs LTX after M1.)
4. **Polish (GPU).** **Real-ESRGAN** upscale + **RIFE** interpolation (smooth 60fps), plus
   **GFPGAN/CodeFormer** face restoration on any AI frames → kills the AI/stutter tells.
- **Output:** `scenes/` (one clip per beat, normalized to 1080×1920) + `assets.json`.
- **License:** Pexels/Pixabay ✅ commercial. FLUX.1-schnell weights **Apache-2.0** ✅.
  SDXL base **CreativeML OpenRAIL++** (commercial-OK, use-restrictions only) ✅. SVD has
  a **non-commercial** community license ⚠️ → prefer **LTX-Video (Apache/OpenRAIL,
  check)** or Ken Burns for the monetized path. **Final pick confirmed at build time.**
- **VRAM:** FLUX-schnell and LTX-Video each fit in 16 GB (fp8/bf16, possibly with
  sequential offload). We run image-gen and img2vid as **separate sub-steps** so we never
  need both resident at once.

### Stage 2 — Voice / narration (GPU or CPU)
- **Purpose:** Dub `script.json` narration → `narration.wav` + per-line timing hints.
- **Tool:** **Kokoro-82M** (⭐ primary — **Apache-2.0**, excellent quality, multiple
  voices, fast on GPU and even viable on CPU). Fallback **Piper** (**MIT**, very fast).
- **Why not XTTS-v2/Coqui:** **non-commercial (CPML)** license → disqualified for a
  monetized channel.
- **Output:** `narration.wav` (mono/stereo, normalized loudness).
- **License:** ✅ commercial.

### Stage 3 — Subtitles / forced alignment (GPU)
- **Purpose:** Word-level timestamps from `narration.wav` for animated, perfectly-synced
  captions (the bouncing/karaoke word style that performs well on Shorts).
- **Tool:** **WhisperX** or **faster-whisper** (CTranslate2) — word-level alignment.
  16 GB runs `large-v3` easily.
- **Output:** `captions.ass` (styled, vertical-safe positioning) + `captions.srt`.
- **License:** ✅ (MIT/Apache; OpenAI Whisper weights MIT).

### Stage 4 — Music selection & mixing (CPU)
- **Purpose:** Pick a mood-matched track and mix it **ducked** under the voice.
- **Tool/source:** curated local library pulled from **YouTube Audio Library** and
  **Pixabay Music** (both ✅ commercial, no strikes). A `music/index.json` maps
  mood→tracks. ffmpeg sidechain compress (duck music under VO) + loudness normalize.
- **Why not AI music (MusicGen/AudioCraft):** **MusicGen weights are CC-BY-NC** →
  non-commercial → disqualified for monetization. Revisit only if a permissively-licensed
  model matures.
- **Output:** `music.wav` (trimmed/looped to video length).
- **License:** ✅ commercial. We store provenance per track for auditability.

### Stage 5 — Render / mux (CPU, GPU optional)
- **Purpose:** Compose scenes + burn captions + mix VO & music + **finishing polish** →
  final 9:16 MP4.
- **Tool:** **ffmpeg** (concat scenes, overlay `.ass`, audio mix, 1080×1920, **60–90s**,
  H.264/AAC, faststart). NVENC on the 5070 Ti for fast encode.
- **Per-platform native renders:** emit a **distinct cut per platform** (YouTube/TikTok/FB/
  IG) — no foreign watermarks, platform-specific caption style / hook / sound / length — to
  avoid duplicate-content penalties (STRATEGY §5). Output `renders/<platform>.mp4`.
- **Finishing polish (baked in):** unified **color grade** (LUT/curves), subtle **film
  grain** and **motion blur**, and consistent contrast/saturation across scenes so real
  stock and AI fills match — this "real edit" pass is what most separates polished output
  from AI slop. (Face restoration GFPGAN/CodeFormer runs upstream in Stage 1.)
- **Output:** `final.mp4` + `thumbnail.jpg`.
- **License:** ✅ (LGPL/GPL ffmpeg build).

### Stage 5b — Automated QC gate (CPU/GPU) — the safety-net
- **Purpose:** Auto-reject bad/risky videos **before** they post (STRATEGY §4.3). Functions
  as the "human replacement" so the system stays hands-off but compliant.
- **Checks:** second-pass LLM fact/sanity + hallucination flag; claims/profanity filter;
  **finance/business YMYL** check (disclaimer present, no buy/sell calls, sources cited);
  render integrity (no dead audio / black frames / clipped loudness).
- **Output:** pass → continue to distribution; fail → quarantine + log for the spot-audit.

### Stage 6 — Multi-platform distribution (CPU, gated)
- **Purpose:** Post the per-platform renders to **YouTube, TikTok, Facebook, Instagram** with
  per-platform title/description/tags/hashtags from Stage 0.
- **Tools:** **YouTube Data API v3** `videos.insert`; **TikTok Content Posting API**;
  **Facebook/Instagram Graph API** (Reels). OAuth/refresh tokens per channel as K8s Secrets.
- **Auto + safety-net behavior:** posting is automated but gated by Stage 5b QC and a
  **phased volume ramp** (start 1–2/day/channel → scale to 5/day). YouTube uses
  `privacyStatus` controllable per phase; a `--dry-run` stages metadata without posting.
- **Hard constraints (see §7):** YouTube API quota ≈ **6 uploads/day/project** (1 project per
  channel = fine); each platform's posting API needs its own app review/approval; unaudited
  YouTube projects upload **private only** until audited.
- **Policy:** YMYL + inauthentic-content + duplicate-content handled in §6 / STRATEGY §5.

---

## 5. Per-channel configuration

The pipeline is one DAG; a **channel profile** parameterizes it. Profiles live in
`profiles/<channel>.yaml` (visual style, voice, music mood, hook templates, data sources).
See STRATEGY §2 for rationale.

| Channel | Visual sourcing bias | Voice tone | Music mood | Special risk |
|---|---|---|---|---|
| **Finance** | real-data **charts/viz** + stock B-roll + AI fill | clear/authoritative | modern/neutral | **YMYL** — disclaimer, no buy/sell calls, cite sources, accuracy |
| **True crime** | cinematic stock + AI atmospheric fill | low/tense narrator | dark ambient/tension | sensitivity, factual accuracy, no defamation |
| **Business** | clean corporate stock + charts + AI fill | upbeat/confident | modern/upbeat | **YMYL**-adjacent — accuracy, no get-rich-quick claims |

---

## 6. Copyright, licensing & policy compliance (must-read)

**Licensing matrix (commercial / monetized use):**

| Component | Choice | License | Commercial? |
|---|---|---|---|
| LLM | Llama 3.1 / Qwen 2.5 | Llama Community / Apache-2.0 | ✅ |
| Stock video/photo | Pexels, Pixabay | Pexels/Pixabay License | ✅ |
| Image gen | FLUX.1-schnell | Apache-2.0 | ✅ |
| Image gen (alt) | SDXL | OpenRAIL++ | ✅ (use-restrictions) |
| Img→video | LTX-Video / Ken Burns | (verify at build) / n/a | ✅ target |
| Img→video (avoid) | Stable Video Diffusion | SVD non-commercial | ❌ |
| TTS | Kokoro / Piper | Apache-2.0 / MIT | ✅ |
| TTS (avoid) | XTTS-v2 / Coqui | CPML non-commercial | ❌ |
| Subtitles | WhisperX | BSD/MIT + Whisper MIT | ✅ |
| Music | YT Audio Library, Pixabay Music | respective free licenses | ✅ |
| Music (avoid) | MusicGen | CC-BY-NC | ❌ |
| Encode | ffmpeg | LGPL/GPL | ✅ |

**Copyright-strike avoidance**
- Never ingest copyrighted footage/music/images. Sources above are strike-safe.
- Store **provenance** (`provenance.json`) per asset: source, URL, license, fetch date.
  This is your evidence if a claim ever lands.

**YouTube policy risk (separate from copyright)**
- **Mass-produced / repetitious AI content** can be demonetized or removed under YT's
  inauthentic-content and "reused content" policies. Mitigations: per-video variety,
  quality bar, human-in-the-loop before public, reasonable upload cadence.
- **Decision (resolved):** the **True Crime** niche is **dropped** from the active build due
  to catastrophic defamation/privacy risk on real, named people (see `research/04` R3:
  $17.5M verdict, May 2026; an AI true-crime channel terminated by YouTube). Active niches are
  **Finance + Business** (PoC); both are YMYL and kept strictly educational/non-advisory.
  *(Earlier relics — "celebrity news", "tech news", history/geopolitics/horror — are obsolete
  category names from prior iterations and no longer part of the design.)*

**Factual accuracy (history/geopolitics)**
- LLMs hallucinate. Add a claims-extraction + optional retrieval/self-check step, and
  keep these categories on **manual-review-before-public** until trusted.

**Disclosure**
- YouTube requires disclosing **realistic altered/synthetic media**. The upload stage
  will set the "altered content" flag when AI-generated visuals/voice are used.

---

## 7. YouTube upload — the gotchas, concretely
- **Private-until-audited:** A Google Cloud project that hasn't passed YouTube's API
  compliance audit can upload, but videos are **locked to `private`**. Plan: ship v1
  uploading as private/unlisted for review; pursue the audit if/when you want auto-public.
- **Quota:** default **10,000 units/day**; `videos.insert` costs **1,600** →
  **~6 uploads/day** ceiling. Cadence and CronWorkflow schedule must respect this.
- **Auth:** OAuth2 (TV/limited-input or installed-app flow) → long-lived **refresh
  token** stored as a K8s Secret; never commit credentials.

---

## 8. Repository structure (proposed)

```
shorts-creator/
├── docs/
│   └── DESIGN.md                 # this file
├── profiles/                     # per-category config
│   └── <category>.yaml
├── prompts/                      # LLM system/user templates
│   └── <category>.md
├── services/                     # long-running in-cluster services
│   └── ollama/                   # Deployment + Service + model pull
├── stages/                       # one dir per pipeline stage = one image
│   ├── 00-script/
│   ├── 01-visuals/
│   ├── 02-voice/
│   ├── 03-subtitles/
│   ├── 04-music/
│   ├── 05-render/
│   └── 06-upload/
├── shared/                       # job.json schema, provenance, py utils
├── deploy/
│   ├── kind/                     # kind cluster config (+ GPU enablement)
│   ├── argo/                     # Argo install, WorkflowTemplate, CronWorkflow
│   ├── minio/                    # artifact store
│   └── storage/                  # PVC for model cache + run workdirs
├── music/                        # local strike-safe library + index.json
├── Makefile                      # cluster up/down, build, submit-workflow
└── README.md
```

---

## 9. Local cluster (kind + GPU) plan
- **kind** single node, with **NVIDIA Container Toolkit** configured so the node
  container sees the GPU; mount `nvidia` runtime, install the **NVIDIA k8s device
  plugin** so pods can request `nvidia.com/gpu`. (This is the fiddly part; documented
  step-by-step in `deploy/kind/`.) If GPU-in-kind proves unstable, fallback option:
  run GPU stages as a host-side sidecar service the cluster calls — but default plan is
  GPU **inside** kind.
- **Model cache PVC:** large model weights (FLUX, Whisper, Kokoro, LTX) downloaded once
  to a persistent volume; stage images stay slim and pull weights at runtime.
- **Image builds:** GPU stages on `nvidia/cuda:12.8-runtime` base + torch `cu128`
  (sm_120). Built locally and `kind load`-ed into the cluster (no registry needed).

---

## 10. Milestones

1. **M0 — Scaffold & cluster:** repo structure, `kind` cluster up with GPU verified
   (`nvidia-smi` in a pod), Argo + MinIO installed, `job.json` schema.
2. **M1 — Vertical slice (CPU-ish):** Stage 0 (Ollama) → 2 (Kokoro) → 3 (WhisperX) →
   5 (ffmpeg, stills + Ken Burns) → a real `final.mp4` for one category. No music/upload.
   Proves the pipeline shape end-to-end.
3. **M2 — Visuals for real:** Stage 1 stock retrieval + AI fill + img2vid/upscale; the
   "not fully AI" look dialed in.
4. **M3 — Music + polish:** Stage 4 ducking/mix, caption styling, per-category profiles.
5. **M4 — Orchestration:** WorkflowTemplate + CronWorkflow, retries, artifacts in MinIO,
   GPU scheduling, run N/day.
6. **M5 — Upload:** Stage 6 with OAuth2 secret, private-draft default, disclosure flags.
7. **M6 — Hardening:** provenance logging, accuracy checks for history/geopolitics,
   monitoring, cost/quota guards.

---

## 11. Open risks & gaps (tracked)
1. **GPU-in-kind stability** — primary technical risk; fallback documented.
2. **sm_120 toolchain** — must pin CUDA 12.8+/torch cu128 in every GPU image.
3. ~~Celebrity-news category~~ — **resolved: dropped, replaced with tech news.**
4. **YouTube API audit** — uploads private until passed; quota ≈6/day.
5. **YT inauthentic-content policy** — automation cadence + quality bar + human review.
6. **LTX-Video license** — confirm commercial terms at build time; Ken Burns is the safe
   fallback for motion.
7. **VRAM choreography** — never co-resident big models; run image-gen and img2vid as
   distinct steps with cache eviction.
8. **Factual accuracy** — hallucination mitigation for history/geopolitics.

---

## 12. Cost
All tooling is free/self-hosted. Real costs: **electricity + local compute time**, plus
optional future spend if you choose paid stock/music or cloud GPU. API quotas (YouTube,
Pexels, Pixabay) are free-tier sufficient for this scale.
