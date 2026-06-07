# 03 — Technical Landscape & Alternatives

**Project:** shorts-creator — free, self-hostable short-form video pipeline
**Target hardware:** ONE NVIDIA RTX 5070 Ti, 16 GB VRAM
**Hard constraints:** no recurring cost; every model/tool free *and* commercial-use licensed
**Date:** 2026-06-07

This document evaluates the realistic open-source AI stack for generating 60–90s vertical (9:16) videos on a single 16 GB GPU, the achievable throughput, the orchestration choices, and where this plan is likely to break.

---

## 1. Executive summary (candid take)

A single 16 GB GPU is *enough* to run every stage of this pipeline, but **AI image-to-video (img2vid) is the binding constraint** on both quality and throughput. The honest architectural conclusion is: **lean heavily on real stock footage**, treat AI video as "fill" not the backbone, and reserve the GPU's heavy lifting for short AI clips, image generation, TTS, and subtitle alignment — all of which are cheap and fast on 16 GB.

The "15 videos/day across 3 channels" goal is **feasible only if AI-generated motion is a minority of each video's runtime** (e.g. <20–30%). If you try to generate the full 60–90s as AI video, throughput collapses to roughly 2–4 videos/day on this hardware. This is quantified in §6.

License-wise the safe spine is: **Wan2.1/2.2 (Apache 2.0)** for AI video, **FLUX.1-schnell (Apache 2.0)** for images, **Kokoro-82M (Apache 2.0)** for TTS, and an **Apache/MIT LLM** for scripting. Several otherwise-attractive models (FLUX.1-dev, XTODO voice clones, CogVideoX-5B) carry non-commercial or restricted licenses and should be avoided or used carefully.

---

## 2. Local open-source AI VIDEO generation (2026)

### 2.1 Comparison

| Model | Params | Min VRAM (quantized) | Speed (5s clip, ref GPU) | License | img2vid | 16 GB feasible? |
|---|---|---|---|---|---|---|
| **LTX-Video / LTX-2.x** | ~2B (DiT) | ~12–16 GB at 768×512; FP8 4K needs ~24 GB | **Fastest by far** — ~4s for 5s clip on 4090; ~7–9 min on a 12 GB 3060/4060 Ti | Apache 2.0 (free <$10M ARR; license from Lightricks above) ([ltx.io](https://ltx.io/model/license)) | Native img2vid mode | ✅ Yes — best fit |
| **Wan2.1 1.3B** | 1.3B | ~8–12 GB | Moderate | **Apache 2.0** ([aifreeforever](https://aifreeforever.com/blog/open-source-ai-video-models-free-tools-to-make-videos)) | Image conditioning supported | ✅ Yes |
| **Wan2.1/2.2 14B** | 14B | ~16 GB+ with FP8/offload (tight) | 10–15 min for 720p clip on 4090 ([clore.ai](https://docs.clore.ai/guides/comparisons/video-gen-comparison)) | I2V workflow (improving) | ⚠️ Marginal — needs offload, slow |
| **CogVideoX-2B** | 2B | ~12–16 GB | Moderate | **Apache 2.0** ([medium/cog](https://medium.com/@furkangozukara/best-open-source-image-to-video-cogvideox1-5-5b-i2v-8cdfc36025bc)) | I2V variant exists | ✅ Yes |
| **CogVideoX-5B / 1.5-5B-I2V** | 5B | ~16 GB with 8-bit quant | Slower than 2B; up to 10s / 161 frames, 1360px native | **Tsinghua/Zhipu license** — commercial allowed *with restrictions* ([aifreeforever](https://aifreeforever.com/blog/open-source-ai-video-models-free-tools-to-make-videos)) | **Best low-VRAM I2V quality** | ✅ Yes (8-bit) |
| **HunyuanVideo (original)** | 13B | ~60–80 GB at 720p | ~6 min on data-center GPU | Tencent community license (restrictions) | Limited | ❌ No |
| **HunyuanVideo 1.5** | 8.3B | **14 GB+** (Nov 2025 release) | Consumer-runnable | Tencent license | Yes | ⚠️ Just fits, license caution |
| **Mochi-1** | 10B | 80 GB+ full precision | Heavy | **Apache 2.0** ([medium/mochi](https://medium.com/@cognidownunder/mochi-1-open-source-text-to-video-generation-to-run-locally-beb0f137a00c)) | T2V-focused, weak I2V | ❌ Not practical |

### 2.2 Verdict for 16 GB img2vid

- **Primary choice: LTX-Video.** It is the only model that is *both* fast enough for batch throughput *and* comfortable on 16 GB, with a native img2vid mode. Speed advantage is roughly an order of magnitude over Wan/Hunyuan ([clore.ai](https://docs.clore.ai/guides/comparisons/video-gen-comparison)). License is Apache 2.0 and a hobby/self-host project is far under the $10M-ARR threshold that would require a paid Lightricks license ([ltx.io](https://ltx.io/model/license)).
- **Quality fallback: CogVideoX-1.5-5B-I2V** when a specific shot needs higher fidelity than LTX produces, accepting ~minutes-per-clip cost. Its license permits commercial use with restricted-use carve-outs — acceptable for benign finance/educational content but read the terms.
- **Best Apache-pure option if you want to avoid even LTX's revenue clause: Wan2.1 1.3B**, which is fully Apache 2.0 and fits easily, at the cost of lower motion quality and resolution.
- **Avoid for this hardware:** original HunyuanVideo and Mochi-1 (VRAM out of reach); Wan2.2 14B is borderline and too slow for batch.

> Reality check: open-source img2vid at 16 GB in 2026 is good for **2–5 second B-roll clips with mild, plausible motion** (drifting, parallax, subtle camera moves). It is *not* reliable for long coherent narrative shots, faces in motion, or text. This caps quality — see §10.

---

## 3. Local IMAGE generation

| Model | VRAM (quantized) | Steps / speed | Realism | License | Commercial-safe? |
|---|---|---|---|---|---|
| **FLUX.1-schnell** | ~12 GB via GGUF | **4 steps** — fastest by a wide margin ([willitrunai](https://willitrunai.com/blog/flux-vs-sdxl-sd35-comparison)) | Very good; slightly behind Dev on faces/hands | **Apache 2.0** ([willitrunai](https://willitrunai.com/blog/flux-vs-sdxl-sd35-comparison)) | ✅ Yes |
| FLUX.1-dev | ~12 GB GGUF | ~20–28 steps | Best-in-class realism, lighting, skin | **Non-commercial** | ❌ No — exclude |
| SDXL + photoreal checkpoints | **~8 GB** (runs on 4060/3060) | ~28–30 steps | Good with the right checkpoint; weaker default | CreativeML Open RAIL++-M (commercial OK, content restrictions) | ✅ Yes |
| SD 3.5 Large | ~18 GB FP16 → needs 24 GB comfortable | ~28 steps | Middle — better than SDXL, below FLUX | Stability Community License (free <$1M revenue) | ✅ Yes (small-scale) |

**Verdict:** **FLUX.1-schnell** is the correct default — Apache 2.0, 4-step speed (critical for batch throughput), ~12 GB footprint that coexists with other models. Keep a **photoreal SDXL checkpoint** as a secondary for styles FLUX handles poorly and as an 8 GB-footprint option when VRAM is contended. **Do not use FLUX.1-dev** (non-commercial). SD 3.5 Large is not worth the VRAM pressure on 16 GB.

---

## 4. Local TTS narration

| Model | Params | Speed | Quality | Voice clone | License | Commercial-safe? |
|---|---|---|---|---|---|---|
| **Kokoro-82M** | 82M | **sub-0.3s** processing; runs on CPU fine | #1 on TTS Arena for its size; natural prosody | No | **Apache 2.0** ([huggingface](https://huggingface.co/hexgrad/Kokoro-82M)) | ✅ Yes |
| Piper | small | Very low latency | Good, slightly robotic | No | **MIT** | ✅ Yes |
| Chatterbox | larger | Slower | Most human-like OSS; beat ElevenLabs Turbo 65% of time | 10s clone | **MIT, no watermark** ([inferless](https://www.inferless.com/learn/comparing-different-text-to-speech---tts--models-part-2)) | ✅ Yes |
| Orpheus-3B | 3B | Slower (3B) | Excellent, expressive | Yes | Apache 2.0 (ft variant — verify) | ⚠️ Verify per-checkpoint |
| XTTS / XTTS-v2 | — | Moderate | Very good clone | Yes | **Coqui Public Model License — NON-commercial** | ❌ Avoid |

**Verdict:** Keep **Kokoro-82M** as the default — Apache 2.0, near-instant, negligible VRAM, and tops the TTS Arena for its size class ([texttolab](https://texttolab.com/blog/kokoro-tts-review)). It is effectively free on the throughput budget. If you later want a distinctive/cloned channel voice, **Chatterbox (MIT, no watermark)** is the commercial-safe upgrade. **Explicitly exclude XTTS** — its license is non-commercial despite being widely deployed.

---

## 5. Local LLMs for scripting (16 GB)

The scripting stage is light: a few hundred to ~1–2k tokens per video. Quality of hook + factual finance copy matters more than speed.

| Model | Quant | VRAM | Throughput | License |
|---|---|---|---|---|
| **Qwen2.5-14B-Instruct** | Q4_K_M | ~8.7 GB | ~33–42 tok/s on a 4070-class GPU ([willitrunai](https://willitrunai.com/blog/qwen-2-5-coder-14b-vram-requirements)) | Apache 2.0 |
| Qwen2.5-14B-Instruct | Q8_0 | ~14.7 GB | Slower, best quality | Apache 2.0 |
| Qwen2.5-7B / Llama-3.1-8B | Q5/Q6 | ~6–8 GB | 50–70 tok/s | Apache 2.0 / Llama license |

**Verdict:** **Qwen2.5-14B-Instruct at Q4_K_M or Q5_K_M** is the sweet spot — Apache 2.0, ~9–11 GB, strong instruction-following and factual coherence for finance scripts. Crucially, **the LLM should not be resident at the same time as the video model**; load it, generate all scripts for the day's batch, then unload before the GPU-heavy stages. Throughput here is a non-issue (scripts take seconds). Serve via **llama.cpp / Ollama** with GGUF, or **vLLM** if you want an OpenAI-compatible endpoint for the orchestrator.

---

## 6. Realistic THROUGHPUT for one 60–90s video & daily capacity

### 6.1 Per-stage budget (single 16 GB GPU, sequential)

Assume a 75s video = ~25–30 shots, of which (recommended) **most are real stock footage** and a minority are AI-generated.

| Stage | Model | Work per video | Est. time | VRAM |
|---|---|---|---|---|
| Script | Qwen2.5-14B Q4 | ~1–2k tokens | ~30–60s | ~9 GB |
| Stock footage fetch | Pexels/Pixabay APIs | network | seconds | 0 |
| AI images (fill) | FLUX.1-schnell | ~6–10 images × 4 steps | ~1–2 min | ~12 GB |
| **AI img2vid (fill)** | **LTX-Video** | **~6–10 clips × 2–4s** | **~3–8 min** | **~14 GB** |
| Upscale/interp | Real-ESRGAN + RIFE | as needed | ~1–3 min | ~4–6 GB |
| Face restore | GFPGAN/CodeFormer | only on faces | ~30s | ~3 GB |
| TTS | Kokoro-82M | full narration | <30s | ~1 GB |
| Subtitle align | WhisperX | full audio | ~30–60s | ~3–5 GB |
| Render | ffmpeg (NVENC) | compose + grade | ~2–4 min | minimal GPU |
| Per-platform renders | ffmpeg | 3–4 outputs | ~2–4 min | minimal |
| QC | heuristics/LLM | checks | ~30s | varies |

**Estimated wall-clock per video (stock-heavy): ~12–25 minutes.**
**If the full 75s is AI-generated video instead:** LTX would need ~15–38 clips → 10–25+ min *just for img2vid*, pushing per-video time to **45–90+ minutes**, and CogVideoX/Wan fallbacks make it far worse.

### 6.2 Daily capacity

- A single GPU runs stages **sequentially** (you cannot hold LTX + FLUX + Qwen resident simultaneously at 16 GB — they must time-share). Effective throughput ≈ 1 video at a time.
- **Stock-heavy path:** ~12–25 min/video → with ~16–20 productive GPU-hours/day, **15 videos/day is achievable** (15 × ~20 min = 5 GPU-hours of heavy work + I/O/overhead). Feasible but with little slack.
- **AI-video-heavy path:** ~60 min/video → **~2–4 videos/day max.** Not feasible for the 15/day goal.

### 6.3 Bottleneck ranking

1. **img2vid (LTX-Video)** — dominant cost; scales linearly with number/length of AI clips. *This is the lever.*
2. **Model load/unload churn** — swapping LTX/FLUX/Qwen in and out of 16 GB adds minutes of overhead per video; mitigate by **batching by stage** (all scripts, then all images, then all clips for the whole day's 15 videos) rather than per-video.
3. ffmpeg multi-platform renders (CPU/NVENC bound, parallelizable with CPU).
4. Everything else (TTS, WhisperX, upscale) is comparatively cheap.

**Bottom line:** 15 videos/day across 3 channels is feasible **only with the stock-footage-first design and stage-batched orchestration**, keeping AI motion to short fill clips.

---

## 7. Orchestration & tooling alternatives

### 7.1 Workflow engine

| Option | Model | Fit for this project |
|---|---|---|
| **Argo Workflows** (current plan) | K8s-native, YAML DAGs | Good fit on `kind`; durable, retries, artifact passing via MinIO; steep YAML overhead for a solo project |
| Prefect | Python-native, no YAML | ([datastackhub](https://www.datastackhub.com/alternatives-to/argo-workflows-alternatives/)) Easiest DX; can run without K8s; strong candidate if K8s is overkill |
| Flyte / Kubeflow Pipelines | K8s-native, ML-focused | Heavier; better for multi-node ML, overkill here |
| Temporal | Durable code workflows | Great for long-running/retryable jobs but adds a server |

**Verdict:** Argo on `kind` is reasonable for durability + artifact lineage, but for a **single-node, single-GPU** project the YAML overhead is significant. **Prefect** is a legitimate lighter alternative (pure Python, runs anywhere) if K8s maintenance becomes a burden. Keep Argo only if the K8s/GPU-operator/MinIO stack is already paying its way.

### 7.2 Generation backend: ComfyUI vs custom scripts

- **ComfyUI** is the de-facto backend for FLUX, LTX-Video, Wan, CogVideoX, and the upscale/interp/face nodes — it has the broadest, fastest-moving node ecosystem and an HTTP API for headless/queued execution. Strong recommendation as the **generation worker**, called by Argo/Prefect.
- Alternatives (InvokeAI, SwarmUI/StableSwarmUI, Fooocus) are more UI-oriented and less flexible for arbitrary pipelines ([sider.ai](https://sider.ai/blog/ai-tools/best-comfyui-alternatives-for-ai-image-workflows-in-2025)).
- **Custom diffusers scripts** give the tightest VRAM control (explicit load/unload, offload, sequential CPU offload) — valuable precisely because of the 16 GB time-sharing problem. A hybrid is ideal: ComfyUI for image/video graphs, custom Python for the orchestration glue, model lifecycle, and ffmpeg.

### 7.3 Queueing

Single GPU = single consumer. Use a simple **job queue** (Redis/RQ, Celery, or Argo's own queue) with **concurrency=1 for GPU stages** and higher concurrency for CPU stages (ffmpeg renders, API fetches). ComfyUI's built-in prompt queue can serve as the GPU serializer.

---

## 8. Local vs cloud GPU economics

The project mandates **no recurring cost**, which structurally favors the already-owned RTX 5070 Ti. But the honest economics:

- Cloud RTX 4090 rents for **$0.18–$0.44/hr median** (Salad/Vast spot) up to ~$1.7/hr on-demand ([gpuperhour](https://gpuperhour.com/), [getdeploying](https://getdeploying.com/gpus/nvidia-rtx-4090)). H100 PCIe ~$2.01/hr, spot ~$1.03/hr ([spheron](https://www.spheron.network/blog/gpu-cloud-pricing-comparison-2026/)).
- Rule of thumb: **renting wins below ~40–50% sustained utilization** of the hardware's depreciation window; owning wins above that ([synpixcloud](https://www.synpixcloud.com/blog/cloud-gpu-vs-local-gpu-cost)).
- A 15-videos/day pipeline at ~5 GPU-hours/day of heavy work is **>50% utilization on a card you already own** → local is the right economic call, and it satisfies the no-recurring-cost rule.

**When cloud beats local for this project:**
1. **Burst re-renders / backfills** — spinning up a $0.30/hr 4090 for a few hours to clear a backlog is cheaper than buying a second GPU.
2. **Quality jobs that exceed 16 GB** — a one-off CogVideoX-5B or Wan2.2-14B hero shot on a rented 24 GB card.
3. **Parallel channels at scale** — if you outgrow 1 GPU, ephemeral spot instances are cheaper than a second local card given depreciation (used 4090 expected to lose $600–1,200 over 2 years ([synpixcloud](https://www.synpixcloud.com/blog/cloud-gpu-vs-local-gpu-cost))).

Caveat: any cloud use technically violates "no recurring cost" if it becomes habitual — keep it strictly opportunistic/spot and out of the steady-state budget.

---

## 9. Scaling, parallelism & upgrade path

**On the current 16 GB single GPU:**
- **Stage batching** (not per-video pipelines) is the #1 throughput multiplier — amortizes model load/unload across the whole day's 15 videos.
- **CPU/GPU overlap:** run ffmpeg renders, stock fetches, and WhisperX (can be CPU/int8) on CPU while the GPU does the next batch's img2vid.
- **Sequential CPU offload** in diffusers/ComfyUI lets bigger models fit by paging layers to RAM — slower but unlocks Wan2.2-14B/CogVideoX-5B when quality demands.
- **NVENC** for all encoding so the GPU's CUDA cores stay free for diffusion.

**Upgrade path (in cost order):**
1. More **system RAM** (cheap) — enables aggressive offload and bigger batch queues.
2. A **24 GB card (RTX 4090/5090)** — removes most VRAM time-sharing pain, enables Wan2.2-14B/CogVideoX-5B natively, ~2× effective throughput.
3. **Second GPU / spot cloud** — horizontal scaling per channel; only worth it past ~30 videos/day.

---

## 10. Key technical risks & quality ceilings

- **img2vid quality ceiling (highest risk).** Open-source 16 GB img2vid produces short, mild-motion clips; it cannot reliably render coherent long shots, moving faces, hands, or on-screen text. **Mitigation: stock-footage-first; AI video only as short ambient fill.** This is the central design constraint, not a tuning problem.
- **VRAM contention.** No two heavy models fit together in 16 GB. Requires disciplined load/unload and stage batching; sloppy orchestration tanks throughput via load churn.
- **License traps.** FLUX.1-dev (non-commercial), XTTS (non-commercial), CogVideoX-5B and Hunyuan (restricted licenses), and LTX's >$10M-ARR clause. **Mitigation: spine = Apache/MIT only** (Wan2.1, FLUX-schnell, Kokoro, Qwen2.5); document license provenance per asset.
- **Finance factual accuracy.** LLM-generated finance copy can hallucinate numbers; the "real-data" requirement means scripts must be grounded in fetched data, not free-generated. Risk is content/compliance, not compute.
- **Faces.** AI faces in motion are the weakest link; GFPGAN/CodeFormer help on stills but not video coherence. Prefer real footage or static AI faces with Ken Burns over AI face motion.
- **Throughput fragility.** The 15/day target has little slack; any quality push toward more AI video, or model-swap inefficiency, drops it below target. Budget for ~10/day as the safe steady state, 15/day as the optimized ceiling.
- **Tooling churn.** ComfyUI nodes and video models update rapidly (Wan2.2 I2V still "rough" as of early 2026); pin versions and snapshot working graphs.

---

## Sources

- [Clore.ai — Video Generation Comparison](https://docs.clore.ai/guides/comparisons/video-gen-comparison)
- [Spheron — Best GPU for AI Video Generation 2026](https://www.spheron.network/blog/ai-video-generation-gpu-guide/)
- [AI Free Forever — 31 Open-Source AI Video Models](https://aifreeforever.com/blog/open-source-ai-video-models-free-tools-to-make-videos)
- [Medium (Lada Huang) — Image-to-Video Showdown 2025: Hunyuan vs Wan2.1 vs LTXV](https://medium.com/@lada.huang2017/open-source-image-to-video-model-showdown-2025-hunyuan-vs-wan-2-1-vs-ltxv-3d14dd3565a5)
- [Medium (Furkan Gözükara) — CogVideoX1.5-5B-I2V low-VRAM I2V](https://medium.com/@furkangozukara/best-open-source-image-to-video-cogvideox1-5-5b-i2v-8cdfc36025bc)
- [Medium (Cogni Down Under) — Mochi 1 local](https://medium.com/@cognidownunder/mochi-1-open-source-text-to-video-generation-to-run-locally-beb0f137a00c)
- [LTX.io — Model commercial license](https://ltx.io/model/license)
- [Will It Run AI — Flux vs SDXL vs SD 3.5](https://willitrunai.com/blog/flux-vs-sdxl-sd35-comparison)
- [Will It Run AI — Qwen2.5-Coder 14B VRAM requirements](https://willitrunai.com/blog/qwen-2-5-coder-14b-vram-requirements)
- [Inferless — Comparing TTS Models (Part 2)](https://www.inferless.com/learn/comparing-different-text-to-speech---tts--models-part-2)
- [TextToLab — Kokoro TTS Review 2026](https://texttolab.com/blog/kokoro-tts-review)
- [Hugging Face — hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
- [DataStackHub — Argo Workflows alternatives](https://www.datastackhub.com/alternatives-to/argo-workflows-alternatives/)
- [Sider.ai — Best ComfyUI alternatives 2025](https://sider.ai/blog/ai-tools/best-comfyui-alternatives-for-ai-image-workflows-in-2025)
- [GPUPerHour — Cloud GPU pricing comparison](https://gpuperhour.com/)
- [GetDeploying — RTX 4090 cloud pricing](https://getdeploying.com/gpus/nvidia-rtx-4090)
- [Spheron — GPU Cloud Pricing 2026](https://www.spheron.network/blog/gpu-cloud-pricing-comparison-2026/)
- [SynpixCloud — Cloud GPU vs Local GPU cost](https://www.synpixcloud.com/blog/cloud-gpu-vs-local-gpu-cost)
