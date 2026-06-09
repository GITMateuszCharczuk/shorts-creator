# Runtime Architecture — the locked blueprint

> **Status:** Accepted design, pre-implementation. This is the authoritative description of
> the **runtime topology** and the **repository layout**. It implements **[ADR
> 0001](decisions/0001-lightened-runtime-architecture.md)** and resolves the open runtime
> findings in **[REVIEW.md](REVIEW.md)** (T1–T5 + the Stage-1/Stage-0 decompositions).
> Freshness (recent-news sourcing) and cross-run de-duplication are added by
> **[ADR 0002](decisions/0002-recency-and-novelty-ledger.md)**. Failure-path hardening
> (exactly-once posting, host GPU lease + supervision, per-video failure domains, observability)
> is added by **[ADR 0003](decisions/0003-resilience-concurrency-observability.md)**; the PoC's
> commercial posture + account-safety gate by
> **[ADR 0004](decisions/0004-poc-commercial-posture-and-account-safety.md)**; the editorial
> quality layer (treatment, best-of-N, the `01e` data-viz + `05c` creative-QC stages) by
> **[ADR 0005](decisions/0005-editorial-quality-layer.md)**; per-format length, loops, keyword
> placement + the closing follow CTA by
> **[ADR 0006](decisions/0006-algorithm-fit-and-format-tuning.md)**; the per-format **layout
> templates** + the headless-Chromium composition engine (Stage 05 / 01e) by
> **[ADR 0007](decisions/0007-format-aware-layout-templates.md)** + its **layout design** (hybrid
> region model, primitive/animation library, 30fps, CPU raster+NVENC) by
> **[ADR 0007a](decisions/0007a-layout-template-design.md)**; the shared **vision QC pass**,
> format↔lane fit, the asset fallback ladder + honest limits by
> **[ADR 0008](decisions/0008-output-parity-hardening.md)**; deterministic numeric grounding,
> seed/determinism, forced-aligned captions, per-platform music, account warming + the honest
> TikTok-public caveat by
> **[ADR 0009](decisions/0009-content-integrity-and-account-robustness.md)**; the M0 extensibility
> seams — versioned schemas + validation harness, the Stage SDK + metadata-generated DAG, the
> distribution/model/layout adapter interfaces, and the fake-backend offline harness + content-
> addressed stage cache — by
> **[ADR 0010](decisions/0010-implementation-conventions-and-extensibility-seams.md)**; the
> performance work — the visual∥audio lane-fork, GPU swap minimization, CPU fan-out, and
> measurement-gated adoption (quality held constant) — by
> **[ADR 0011](decisions/0011-performance-and-optimization.md)**.
>
> **Precedence:** for *tooling* choices, `OPTIONS.md` stands. For *scope*, `POC.md` wins.
> Where `DESIGN.md §2–§3/§9` describes the older GPU-in-kind / MinIO / monolithic-Stage-1
> topology, **this doc supersedes it** (per ADR 0001).

The shape in one sentence: **the host owns the GPU (ComfyUI + a per-batch LLM); a thin Argo
control plane on `kind` orchestrates CPU stages and calls into the host over HTTP; one PVC
holds everything; the day's videos are built stage-batched so each model loads once.**

---

## 1. The two planes

The design splits cleanly into a **host GPU plane** (bare metal, owns the card) and a
**cluster control plane** (`kind`, all CPU). This split is the whole point of the lightened
architecture — it removes GPU-in-kind (the #1 risk) and hands VRAM management to ComfyUI.

| Concern | Host GPU plane (bare metal) | Cluster control plane (`kind`) |
|---|---|---|
| **Owns the GPU?** | ✅ yes — sole owner | ❌ no GPU passed into kind |
| **Components** | ComfyUI server; LLM endpoint (Qwen2.5-14B, per-batch) | Argo controller + UI; all stage pods; PVC |
| **Heavy models** | FLUX, LTX-Video, Real-ESRGAN, RIFE, GFPGAN/CodeFormer, Qwen | none resident — pods are thin HTTP clients |
| **VRAM lifecycle** | managed by ComfyUI queue + batch ordering | n/a |
| **CPU work** | — | research/ingest, stock-fetch, TTS, subs, music, render, QC, distribute |
| **Reliability primitives** | ComfyUI prompt queue (GPU serializer) | Argo retries, backoff, scheduling, lineage, UI |

> **GPU placement rule.** At any instant the host GPU has **one logical owner**. Diffusion/
> video/upscale run inside ComfyUI's single queue; the LLM loads only during the script
> sub-stage and is evicted before diffusion. Light audio (Kokoro) and subtitle alignment
> (WhisperX `int8`) run **CPU-side in-cluster** to keep the contention surface minimal — both
> are CPU-viable (`research/03 §4, §6`). They can move onto the GPU later if needed.

---

## 2. System topology

```
        ┌──────────────────────────────────────────────────────────────────────┐
        │                          HOST  (bare metal)                           │
        │                     RTX 5070 Ti 16 GB · CUDA 12.8 · sm_120            │
        │                                                                        │
        │   ┌───────────────────────────┐        ┌──────────────────────────┐   │
        │   │   ComfyUI server (HTTP)    │        │   LLM endpoint (HTTP)     │   │
        │   │   single GPU owner / queue │        │   Ollama·llama.cpp        │   │
        │   │   ┌─────────────────────┐  │        │   Qwen2.5-14B (per-batch) │   │
        │   │   │ FLUX · LTX · ESRGAN │  │        │   load → all scripts →    │   │
        │   │   │ RIFE · GFPGAN graphs│  │        │   EVICT before diffusion  │   │
        │   │   └─────────────────────┘  │        └──────────────────────────┘   │
        │   └───────────▲───────────────┘                  ▲                     │
        └───────────────┼──────────────────────────────────┼─────────────────────┘
                        │  HTTP (kind network gateway, §6)  │
        ┌───────────────┼──────────────────────────────────┼─────────────────────┐
        │               │      kind cluster (CPU only)      │                     │
        │   ┌───────────┴──────────────────────────────────┴─────────────────┐   │
        │   │                 Argo Workflows controller + UI                  │   │
        │   │     CronWorkflow (daily)  →  one BATCHED DAG for N videos        │   │
        │   └───────────────────────────────┬─────────────────────────────────┘   │
        │                                   │  schedules thin CPU client pods       │
        │                                   ▼                                       │
        │  00a data-fetch · 00b script · 01a stock · 01b/01c/01d (→host) · 01e viz │
        │  02 voice · 03 subs · 04 music · 05 render · 05b safety · 05c quality · 06 │
        │                                   │                                       │
        │                                   ▼                                       │
        │   ┌─────────────────────────────────────────────────────────────────┐   │
        │   │      shared PVC — run workdirs · job.json · provenance · quarantine│  │
        │   │                        (NO MinIO)                                 │   │
        │   └─────────────────────────────────────────────────────────────────┘   │
        └───────────────────────────────────────────────────────────────────────┘
                                          │
                       ┌──────────────────┴───────────────────┐
                       ▼                                       ▼
                YouTube Data API v3                   TikTok Content Posting API
                (private-first, AI-disclosure flag, idempotent — §Stage 6)
```

---

## 3. The batched pipeline DAG

One `CronWorkflow` submits a **single batched DAG per day**. Each stage fans out across the
day's 2–4 videos *before* the next stage starts, so a model loads once per stage for the
whole batch (resolves **REVIEW T1**). GPU stages (`→host`) are thin clients to ComfyUI/LLM.

**Two lanes, forked after 00b (ADR 0011).** Past `script.json` the DAG splits into a
**visual lane** (GPU-bound: 01a→01b→01c→01d) and an **audio lane** (CPU-bound: 02→03→04) that
**run concurrently and rejoin at 05 render** — the CPU makes narration/captions/music while the GPU
grinds diffusion, overlapping the two heaviest time sinks. Each lane still stage-batches internally
(model loads once), and **"never co-resident" holds**: the audio lane is pure CPU, the GPU only ever
holds one visual-lane model, and the confirm-VRAM-free gate stays between 00b and 01b. The linear
column below is the *dependency* order; the visual/audio split is the *scheduling* order.

```
              ┌──────────── per-niche seeds: finance, business ────────────┐
              ▼                                                            ▼
   ╔══════════════════════╗   CPU       market data (Alpha Vantage/Yahoo/FRED)
   ║ 00a research/ingest   ║   + RECENT NEWS via free RSS, published ≥ now−3d → data.json
   ╚══════════╤═══════════╝   (fetch failure = visible DAG state; cite, don't republish)
              ▼
   ╔══════════════════════╗   →HOST LLM   ── load Qwen ONCE for the whole batch ──┐
   ║ 00b script  (×N)      ║   Qwen2.5-14B → script.json per video                 │ EVICT
   ║   ↑ dedup: query      ║   reject/repick if source-URL reused or topic overlaps │ before
   ║   history/ledger      ║   recent records (keyword now, embeddings post-M1)     │ diffusion
   ╚══════════╤═══════════╝                                                        │
              ▼                                                                    │ diffusion
   ╔══════════════════════╗   CPU                                                  ▼
   ║ 01a stock-fetch (×N)  ║   Pexels/Pixabay/Mixkit/Coverr/Videvo → real clips + provenance
   ╚══════════╤═══════════╝   (real-footage-first; AI only fills gaps)
              ▼
   ╔══════════════════════╗   →HOST ComfyUI ── FLUX loaded ONCE for the batch
   ║ 01b image-gen  (×N)   ║   FLUX.1-schnell → photoreal stills for un-stockable scenes
   ╚══════════╤═══════════╝
              ▼
   ╔══════════════════════╗   →HOST ComfyUI ── LTX loaded ONCE for the batch
   ║ 01c img2vid    (×N)   ║   LTX-Video (img→video) / Ken Burns → short motion clips
   ╚══════════╤═══════════╝
              ▼
   ╔══════════════════════╗   →HOST ComfyUI ── ESRGAN/RIFE/GFPGAN
   ║ 01d upscale-restore(×N)║  Real-ESRGAN + RIFE + GFPGAN/CodeFormer → assets.json
   ╚══════════╤═══════════╝
              ▼
   ╔══════════════════════╗   CPU (Kokoro)        ╔══════════════════════╗  CPU
   ║ 02 voice       (×N)   ║   narration.wav  ───► ║ 03 subtitles  (×N)    ║  WhisperX int8
   ╚══════════════════════╝                       ╚══════════╤═══════════╝  → captions.ass
                                                              ▼
   ╔══════════════════════╗   CPU                 ╔══════════════════════╗  CPU (ffmpeg)
   ║ 04 music       (×N)   ║   ducked mix  ──────► ║ 05 render     (×N)    ║  per-platform
   ╚══════════════════════╝                       ╚══════════╤═══════════╝  YT + TikTok cuts
                                                              ▼
                                              ╔══════════════════════╗  CPU (+ →host LLM)
                                              ║ 05b QC gate   (×N)    ║  pass → continue
                                              ╚══════════╤═══════════╝  fail → quarantine
                                                         ▼  (gated)
                                              ╔══════════════════════╗  CPU
                                              ║ 06 distribute (×N)    ║  idempotent, private-
                                              ║   → append history/   ║  first, AI-disclosure;
                                              ║     ledger.jsonl      ║  record topic for dedup
                                              ╚══════════════════════╝
```

CPU stages (`02 voice`, `04 music`, the renders) overlap GPU work freely — while ComfyUI
runs the next batch's clips, ffmpeg can render the previous one (`research/03 §9` CPU/GPU
overlap).

---

## 4. VRAM choreography (host GPU, one owner at a time)

The "never co-resident" rule (`POC §4`) is enforced **structurally** by the batch ordering
above, not by hope. A day's batch walks the GPU through one model at a time:

```
 VRAM
 16GB ┤                  ┌─FLUX─┐        ┌──LTX──┐     ┌ESRGAN┐
      │   ┌─Qwen-14B─┐    │~12GB │        │ ~14GB │     │RIFE  │
  ~9G ┤   │  ~9GB    │    │      │        │       │     │+GFPGAN
      │   │ (scripts)│    │images│        │ clips │     │~4-6GB│
   0  ┼───┴──────────┴────┴──────┴────────┴───────┴─────┴──────┴──────────────►  time
          │   evict  │    │ evict│        │ evict │     │      │
          └──00b─────┘    └─01b──┘        └─01c───┘     └─01d──┘
                                                          (CPU: 02 voice, 03 subs, 04 music,
                                                           05 render, 05b QC, 06 distribute —
                                                           run alongside, no GPU contention)
```

No two heavy models are ever resident together (`research/03 §6.2, §10`). ComfyUI's queue
serializes 01b/01c/01d; the LLM endpoint is up only for 00b. This is *why* stages are
batched and serialized rather than packed: predictable VRAM beats clever contention, and
zero-OOM is a PoC reliability requirement.

---

## 5. Storage — a single PVC (host-backed for durability)

The data volume is a single PVC **backed by a host directory via kind `extraMounts`**, so
everything below lives on the host disk and **survives `kind delete cluster` and reboots**.
This durability is not cosmetic: the novelty ledger (below) can only prevent repeats across
runs because it persists — a plain in-cluster PVC would be wiped on every cluster rebuild
(ADR 0002 §4).

```
 PVC: shorts-data  →  host dir via kind extraMounts  (one RWO volume, mounted into pods)
 └── runs/
     └── <batch-id>/                     # one CronWorkflow run = one day's batch
         ├── batch.json                  # batch manifest: which videos, profiles, status
         ├── data/                       # 00a: market data + recent news (≤3d) + summaries
         └── <video-id>/                 # one per video in the batch
             ├── job.json                # ⭐ the spine — threads through every stage (+ persisted seed, ADR 0009)
             ├── script.json             # 00b — treatment + {value,source_ref} numeric grounding (ADR 0005/0009)
             ├── scenes/                 # 01a stock + 01b/01c/01d AI fills + 01e data-viz (1080×1920)
             ├── assets.json             # 01d — final scene manifest
             ├── provenance.json         # source/URL/license/fetch-date per asset (audit trail)
             ├── narration.wav           # 02
             ├── captions.ass / .srt     # 03
             ├── music.wav               # 04
             ├── renders/                # 05 — youtube.mp4, tiktok.mp4 + thumbnail.jpg
             ├── vision.json             # 05x — VLM read of sampled frames (ADR 0008)
             ├── qc.json                 # 05b — safety gate pass/fail + reasons
             └── creative_qc.json        # 05c — quality-gate score vs floor (ADR 0005/0008)
 └── quarantine/<video-id>/              # 05b/05c failures, kept for the weekly spot-audit
 └── history/
     └── ledger.jsonl                    # ⭐ append-only novelty ledger (ADR 0002): one record
                                         #   per produced video {id,date,niche,topic,title,hook,
                                         #   format,source_urls,keywords,embedding=null}. 00b queries it
                                         #   to reject repeats; 06 appends after a successful post.
     └── posts.jsonl                     # ⭐ posted-state ledger (ADR 0003): (video_id,platform)
                                         #   intent→confirmed records — Stage 06 exactly-once.
 └── models/                             # (host-mounted) shared weight cache, downloaded once
```

No MinIO (resolves **REVIEW T5**). Argo passes artifacts by **path** on this shared volume;
the `job.json` spine + `provenance.json` make any run reconstructable (`POC §6`
reproducibility / auditability). The `history/ledger.jsonl` gives the pipeline **memory
across runs** — freshness (00a, ≤3-day news) and novelty (00b dedup) together are what keep
output current and non-repetitive, which is also the compliance lever against repetitious-
content demotion (ADR 0002).

---

## 6. Cluster ↔ host wiring (the one gotcha)

Stage pods in `kind` must reach ComfyUI and the LLM endpoint running on the host. This is the
single most common "why can't my pod connect" failure, so it is pinned here:

- The host services bind on the host (e.g. ComfyUI `:8188`, LLM `:11434`).
- `kind` runs in Docker; pods reach the host via the **kind network gateway** (the Docker
  bridge gateway address), surfaced into the cluster as a fixed `Service`/`Endpoints` or an
  env var (`HOST_GPU_ENDPOINT`) injected into every GPU-client stage.
- `host/README.md` carries the concrete bring-up + the exact gateway wiring for this box;
  `shared/` provides a single `host_client.py` so no stage hand-rolls the HTTP/poll logic.
- Failure mode: if the host endpoint is unreachable, the GPU-client stage **fails the Argo
  step** (which retries/backs off) rather than hanging — the host is a first-class dependency
  with a first-class failure state.

---

## 7. Repository / folder structure

Updated from `DESIGN §8` to implement ADR 0001: `host/` plane added, `minio/` removed,
`stages/01-visuals` decomposed into `01a–01d`, `00a-data-fetch` split out, `schemas/` and
`docs/decisions/` added.

```
shorts-creator/
├── docs/
│   ├── ARCHITECTURE.md            # ⭐ this blueprint (runtime topology + layout)
│   ├── POC.md                     # authoritative scope
│   ├── STRATEGY.md  DESIGN.md  OPTIONS.md  REVIEW.md  DEV-WORKFLOW.md
│   ├── decisions/                 # ADR log — decision-of-record (REVIEW C1)
│   │   └── 0001-lightened-runtime-architecture.md
│   └── research/                  # 01–05 evidence
├── schemas/                       # ⭐ the contracts = first code artifact (REVIEW C2/P0) — all schema_version'd (ADR 0010)
│   ├── job.schema.json            #    the spine (+ persisted seed)
│   ├── script.schema.json         #    Stage 00b output
│   ├── assets.schema.json         #    Stage 01d output
│   ├── provenance.schema.json     #    per-asset audit record
│   ├── profile.schema.json        #    niche config, validated (ADR 0010)
│   ├── format.schema.json         #    format archetype config, validated (ADR 0010)
│   └── feature_record.schema.json #    stable per-video record → warm-start the analytics loop (ADR 0010)
├── profiles/                      # per-niche config, validated against profile.schema (ADR 0010)
│   ├── finance.yaml
│   └── business.yaml
├── prompts/                       # LLM system/user templates per niche
│   ├── finance.md
│   └── business.md
├── host/                          # ⭐ the GPU plane — runs on the host, NOT in kind
│   ├── comfyui/
│   │   ├── graphs/                # pinned FLUX / LTX / ESRGAN / RIFE / GFPGAN graphs
│   │   └── setup.md               # install + model download to models/ cache
│   ├── llm/                       # Ollama/llama.cpp Qwen2.5-14B; per-batch load/evict
│   └── README.md                  # host bring-up + cluster↔host networking (§6)
├── stages/                        # one dir = one image = pure fn of inputs + job.json
│   ├── 00a-research/              #   CPU — market data (AlphaVantage/Yahoo/FRED) + RSS news ≤3d
│   ├── 00b-script/                #   CPU client → host LLM; dedup-checks history/ledger.jsonl
│   ├── 01a-stock-fetch/           #   CPU — Pexels/Pixabay/Mixkit/Coverr/Videvo
│   ├── 01b-image-gen/             #   client → host ComfyUI (FLUX)
│   ├── 01c-img2vid/               #   client → host ComfyUI (LTX / Ken Burns)
│   ├── 01d-upscale-restore/       #   client → host ComfyUI (ESRGAN/RIFE/GFPGAN)
│   ├── 01e-dataviz/               #   CPU — branded charts/counters via the shared compositor (ADR 0005/0007)
│   ├── 02-voice/                  #   CPU — Kokoro-82M (text-normalization + prosody)
│   ├── 03-subtitles/              #   CPU — WhisperX int8, forced-aligned to script (ADR 0009)
│   ├── 04-music/                  #   CPU — per-platform taxonomy-matched track + SFX, ducked mix (ADR 0009)
│   ├── 05-render/                 #   format-aware compositor: pure(render_manifest), 30fps CPU raster + NVENC; cuts, CTA, loop, end-card (ADR 0007/0007a)
│   ├── 05x-vision/                #   →host Qwen2.5-VL over sampled frames; feeds both gates (ADR 0008)
│   ├── 05b-qc/                    #   safety gate (pass → continue / fail → quarantine)
│   ├── 05c-creative-qc/           #   quality gate — judge score vs floor, vision-grounded (ADR 0005/0008)
│   └── 06-distribute/             #   CPU — exactly-once, private-first, AI-disclosure;
│                                  #         appends to history/ledger.jsonl after a post
├── shared/                        # ⭐ the Stage SDK (ADR 0010): run(ctx) base, job.json IO, seed, provenance, logging, retry/quarantine
│   ├── stage.py                   #    base contract + stage metadata (DAG generated from it)
│   ├── adapters/                  #    DistributionAdapter (exactly-once in base) · model backends (per-capability) · LayoutEngine
│   ├── config.py                  #    precedence resolver: global → niche → batch → per-platform
│   └── fakes/                     #    fixture-returning host backends → GPU-free local/CI runs + content-addressed (stage,input_hash,seed) cache
├── deploy/
│   ├── kind/                      # cluster config — NO GPU device-plugin needed anymore
│   ├── argo/                      # install + WorkflowTemplate (batched DAG) + CronWorkflow (scheduled) — manual trigger reuses the template
│   └── storage/                   # the single shared PVC (NO minio/)
├── music/                         # strike-safe local library + index.json (mood→tracks)
├── tests/                         # schema validation + golden fixtures + GPU-free full-DAG run via shared/fakes (ADR 0010)
├── scripts/                       # ⭐ one-command lifecycle: up.sh (turn it all on) · trigger.sh (manual run) · down.sh
├── Makefile                       # up · trigger · down · host-up · cluster-up · build · wire · test
└── README.md
```

**What changed vs. `DESIGN §8`, and why:**

| Change | Reason |
|---|---|
| `+ host/` plane | GPU work moves out of kind onto host ComfyUI/LLM (ADR 0001 / T3·T4) |
| `− deploy/minio/` | single PVC only (T5) |
| `01-visuals/ → 01a–01d` | one model per sub-stage, clean load/evict, independent retry (Stage-1 finding) |
| `+ 00a-research/` | data-fetch split out *and* widened to recent-news ingestion (Stage-0 finding + ADR 0002) |
| `+ history/ledger.jsonl` (on PVC) | cross-run novelty memory so we don't repeat topics (ADR 0002) |
| `+ schemas/` | the stage contracts are the architecture; first code artifact (C2/P0) |
| `+ docs/decisions/` | ADR log = decision-of-record (C1) |
| `deploy/kind/` no device-plugin | GPU-in-kind eliminated — the #1 risk is gone |

---

## 8. How you actually run it

**The one-command path (convenience):**
```
scripts/up.sh        # turn the WHOLE system on: host ComfyUI → Ollama → kind+Argo+PVC, then a wire check
scripts/trigger.sh   # run a batch now by hand (manual trigger; --dry-run / --profiles / --count / --watch)
scripts/down.sh      # stop it (host-backed data persists; --purge also deletes the cluster)
```
`up.sh` is idempotent — it skips anything already healthy and waits on each plane's health endpoint
before moving on — so it doubles as "resume after a reboot." `make up` / `make trigger` / `make down`
are equivalent wrappers.

**What it does under the hood** — the same two moments as before, just sequenced for you:

**One-time setup (heavier — paid once per machine; `up.sh` calls these in order):**
```
make host-up        # start ComfyUI + pull FLUX/LTX/ESRGAN/RIFE/GFPGAN; start the Ollama LLM endpoint
make cluster-up     # kind cluster + Argo + the shared PVC   (no GPU device-plugin)
make build          # build stage images, kind-load them
make wire           # verify pods can reach host ComfyUI/LLM over the gateway (§6)
```

**Per run — two equal entry points to the *same* `shorts-batch` WorkflowTemplate:**
```
scripts/trigger.sh --profiles finance,business     # MANUAL: on-demand, today's batch
scripts/trigger.sh --dry-run                         # stage all metadata, post nothing
# …or do nothing: the CronWorkflow fires the daily batch on schedule (SCHEDULED).
```
Manual and scheduled runs are byte-identical except for what triggered them, and `CronWorkflow
concurrencyPolicy: Forbid` (ADR 0003) means a manual kick that overlaps a running batch is rejected,
never co-resident. So day-to-day it is genuinely one command (or zero, via cron); the multi-step
part is the one-time bring-up. That is the deliberate trade in ADR 0001: heavier setup, lighter
steady state, the GPU's VRAM managed for you with full visibility when something breaks.

---

## 9. How this resolves the REVIEW findings

| REVIEW item | Resolution here |
|---|---|
| **T1** per-video vs stage-batching | Batched DAG (§3); each model loads once per batch |
| **T2** persistent Ollama pins VRAM | LLM is a **per-batch** host endpoint, evicted before diffusion (§4) |
| **T3** infra complexity vs reliability | GPU-in-kind + MinIO removed; Argo kept for the reliability primitives (ADR 0001) |
| **T4** ComfyUI as backend | ComfyUI **is** the host GPU plane; bespoke per-stage CUDA images dropped (§1) |
| **T5** two storage systems | Single PVC, artifacts by path (§5) |
| **Stage 1** monolith | Decomposed `01a–01d`, one model each (§3, §7) |
| **Stage 0** embedded data-fetch | Split into `00a data-fetch` (§3) |

## 10. Still open (the next decisions, tracked)

Not closed by this blueprint — these are the remaining `REVIEW.md` items, in priority order:

1. **C2 — the contracts.** Write `schemas/*.schema.json` (`job`/`script`/`assets`/
   `provenance`) as versioned JSON Schema **before** stage code. They are every stage's
   interface.
2. **Stage 6 idempotency.** A posted-state ledger / idempotency key so a retry never
   double-posts (real bug for unattended-with-retries).
3. **Stage 5 render-differentiation spec** — what concretely differs per platform (caption
   style / hook / length / sound), so the YouTube and TikTok cuts aren't a dupe re-encode.
4. **Stage 5b QC spec** — pass/fail thresholds, the second-pass LLM's VRAM source (host
   endpoint, same eviction rule), the quarantine + weekly spot-audit subsystem.
```
