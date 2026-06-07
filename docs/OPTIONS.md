# Architecture & Tooling Options — Decision Matrix

Pick one option per decision. ⭐ = my recommendation (and the documented default if you
don't choose otherwise). All options are free; commercial/monetization-safe noted per
row. GPU figures assume your **RTX 5070 Ti 16 GB (Blackwell sm_120, CUDA 12.8+)**.

Legend: 💰 commercial-safe · ⚠️ caveat · ❌ disqualified for monetized use.

---

## A. Pipeline orchestration

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Argo Workflows** | Container-per-step (each stage isolates its huge/conflicting CUDA+py deps), DAG, retries, params, `CronWorkflow`, artifact passing, UI. Native to k8s/kind. | New CRDs to learn; YAML-heavy. | Best fit for a media DAG on kind. |
| **Prefect / Dagster** | Nice Python DX, observability. | App-level, not container-per-task; you fight it to get per-stage isolated images on k8s. | If you'd rather write Python than YAML. |
| **Raw K8s Jobs + queue** | Minimal deps, full control. | You hand-build DAG, retries, artifacts. | Only if you want zero framework. |
| **Tekton** | CI/CD-grade, k8s-native. | Verbose; pipeline-as-CI ergonomics. | Viable, less media-friendly than Argo. |

## B. LLM serving runtime (script generation)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Ollama** | Dead-simple, one-line model pulls, OpenAI-compatible API, runs as in-cluster service, great for 7–8B. | Less throughput tuning than vLLM. | Perfect for our low-volume script step. |
| **vLLM** | Max throughput, batching. | Heavier, overkill for a few scripts/run. | Only if you scale to many videos. |
| **llama.cpp server** | Tiny, CPU/GPU, GGUF quants. | More manual. | Good ultra-light alternative. |

## C. Script LLM model 💰

| Option | License | Notes |
|---|---|---|
| ⭐ **Qwen2.5 7B Instruct** | Apache-2.0 | Strong instruction-following + JSON adherence; clean commercial license. |
| **Llama 3.1 8B Instruct** | Llama Community | Excellent quality; license has >700M-MAU clause (irrelevant to you) — fine. |
| **Mistral 7B / Nemo 12B** | Apache-2.0 | Solid, permissive; 12B fits 16 GB quantized. |
| **Gemma 2 9B** | Gemma terms | Good, but extra use-policy terms. |

## D. Stock footage / photos 💰

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Pexels API + Pixabay API** | Free, generous quota, commercial OK, no legal attribution required, vertical content. | Coverage gaps for niche/historical scenes (→ AI fill). | Use both, dedupe. |
| **Wikimedia Commons** | Huge, free. | Mixed licenses → must filter per-asset; attribution often required. | Good for history if you respect each license. |
| **Openverse** | Aggregates CC media. | License heterogeneity. | Supplemental. |

## E. AI image generation (fill scenes stock can't cover)

| Option | License | VRAM (16 GB?) | Verdict |
|---|---|---|---|
| ⭐ **FLUX.1-schnell** | Apache-2.0 💰 | ✅ fits (fp8/bf16) | Best quality-per-step, photoreal, fast (1–4 steps), fully commercial. |
| **SDXL / SDXL-Turbo** | OpenRAIL++ 💰 | ✅ easy | Mature ecosystem (LoRAs/ControlNet); slightly less photoreal than FLUX. |
| **Stable Diffusion 3.5** | Stability Community 💰* | ✅ medium/large | Good; *free under their community license below revenue threshold — verify. |
| **FLUX.1-dev** | non-commercial ❌ | ✅ | Higher quality but **disqualified** (non-commercial). |

## F. Image → motion ("not fully AI" movement)

| Option | License | VRAM | Verdict |
|---|---|---|---|
| ⭐ **Ken Burns (ffmpeg `zoompan`)** | n/a 💰 | none | Start here: pan/zoom/slide on stills+stock. Reliable, instant, zero risk. |
| ⭐ **LTX-Video (img2vid)** | OpenRAIL-M 💰* | ✅ fits | Real generated motion, fast for its class; *confirm commercial terms at build. Layer in after Ken Burns. |
| **CogVideoX-5B** | Apache-2.0 (5B) 💰 | ⚠️ tight, needs offload | Good quality; slower, heavier. |
| **AnimateDiff** | depends on base model | ✅ | Stylized motion; can look "AI". |
| **Stable Video Diffusion** | non-commercial ❌ | ✅ | **Disqualified** for monetized use. |

## G. Upscale & frame interpolation (polish, reduces AI "tell") 💰

| Option | Role | Verdict |
|---|---|---|
| ⭐ **Real-ESRGAN** | upscale stills/frames | BSD; standard choice. |
| ⭐ **RIFE** | interpolate to smooth 60fps | MIT; great motion smoothing. |
| **Skip for v1** | — | Acceptable; add in M3 polish. |

## H. Text-to-speech (narration) 💰

| Option | License | Quality / Notes | Verdict |
|---|---|---|---|
| ⭐ **Kokoro-82M** | Apache-2.0 💰 | Excellent natural voices, multi-voice, fast on your GPU, even CPU-viable. | Primary. |
| **Piper** | MIT 💰 | Very fast, lightweight, decent quality. | Fallback / high-volume. |
| **Bark** | MIT 💰 | Expressive, but slow & unstable. | Niche (horror ambiance?). |
| **F5-TTS / StyleTTS2** | varies | High quality; check weights' license. | Optional upgrade. |
| **XTTS-v2 / Coqui** | CPML ❌ | Great cloning but **non-commercial**. | Disqualified. |

## I. Subtitles / forced alignment

| Option | License | Notes | Verdict |
|---|---|---|---|
| ⭐ **WhisperX** | BSD + Whisper MIT 💰 | Word-level timestamps via alignment → karaoke captions. `large-v3` fits 16 GB. | Primary. |
| **faster-whisper** | MIT 💰 | Fast CTranslate2; word timestamps too. | Lean alternative. |
| **stable-ts** | MIT 💰 | Nice timestamp stabilization. | Optional. |

## J. Background music 💰

| Option | License | Verdict |
|---|---|---|
| ⭐ **YouTube Audio Library** | free, YT-safe (no strike from YT's own lib) | Safest for YouTube specifically. |
| ⭐ **Pixabay Music** | Pixabay license, commercial OK | Big, easy, no attribution. |
| **Incompetech / FMA (CC-BY)** | CC-BY | Fine **if** you auto-add attribution to descriptions. |
| **MusicGen / AudioCraft** | CC-BY-NC ❌ | **Disqualified** (non-commercial weights). |

## K. Render / encode 💰

| Option | Verdict |
|---|---|
| ⭐ **ffmpeg (libx264 / NVENC)** | The whole compositing+mux layer; NVENC on your card for fast encode. |
| **MoviePy** | Pythonic wrapper over ffmpeg; handy for complex caption animation, slightly slower. |

## L. Artifact / object storage

| Option | Verdict |
|---|---|
| ⭐ **MinIO + shared PVC** | MinIO as Argo artifact repo (S3 API) for stage I/O & finals; PVC for big scratch media + model cache. |
| **PVC only** | Simpler, no S3; lose nice artifact UI/versioning. |

## M. GPU enablement on kind (the fiddly bit)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **GPU inside kind** (NVIDIA Container Toolkit + k8s device plugin) | Truly "k8s-native", pods request `nvidia.com/gpu`. | Setup is finicky; sm_120 toolchain pinning. | Primary; documented step-by-step. |
| **Host-side GPU service** | Easiest to get GPU working; cluster calls it over HTTP. | Less "pure" k8s; a piece lives outside. | Fallback if device-plugin fights us. |
| **k3d / minikube --gpu** | minikube has first-class GPU flags. | Swaps your kind choice. | Consider if kind GPU proves painful. |

---

## Cross-cutting defaults already settled
- **Categories:** history, geopolitics, moving story, **tech news**, horror story.
- **Upload:** render + upload as **private draft only**, never auto-publish (`--dry-run` supported).
- **Monetization-safe:** all ❌ rows excluded.

## Suggested "safe default" stack (if you just want my full pick)
Argo · Ollama+Qwen2.5-7B · Pexels+Pixabay · FLUX.1-schnell · Ken Burns→LTX-Video ·
Real-ESRGAN+RIFE · Kokoro · WhisperX · Pixabay/YT-Audio music · ffmpeg+NVENC · MinIO+PVC ·
GPU-in-kind.
