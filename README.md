# shorts-creator

A free, self-hostable, Kubernetes-native (Kind-compatible) pipeline that automatically
produces and distributes short-form video (60–90s) across **3 channels** —
**Finance, True Crime, Business** — to **YouTube, TikTok, Facebook & Instagram**, with
native per-platform renders. Runs **"auto + safety-net"**: full automation gated by an
automated QC check, a phased volume ramp, and a weekly spot-audit.

The pipeline: pick a channel → script (hook-first, real-data-driven) → build visuals (real
stock footage + AI fill + GPU motion/upscale) → AI narration (TTS) → synced animated
subtitles → mood-matched music → render + finishing polish → automated QC gate →
distribute per-platform.

**Constraints:** no recurring cost, commercial/monetization-safe licensing, no copyright
strikes, runs locally on a single NVIDIA-GPU box (Windows/WSL2) — **runner-first,
Kubernetes-deployable by profile** ([ADR 0015](docs/decisions/0015-runner-first-orchestration.md)).

## Docs
- **[docs/POC.md](docs/POC.md)** — ⭐ **authoritative current scope.** The deliberately narrow,
  deeply-engineered first slice we are building now (2 niches, 2 platforms). Read this first.
- **[docs/STRATEGY.md](docs/STRATEGY.md)** — content & monetization fundamentals (niches,
  platforms, earnings, automation policy, compliance). The *why* (full vision).
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — ⭐ the **locked runtime blueprint**:
  topology diagrams, the batched DAG, VRAM choreography, storage, and the repo layout.
  Supersedes the older runtime topology in DESIGN where they disagree.
- **[docs/DESIGN.md](docs/DESIGN.md)** — architecture, tools, pipeline stages (the *how*).
- **[docs/OPTIONS.md](docs/OPTIONS.md)** — tooling decision matrix.
- **[docs/REVIEW.md](docs/REVIEW.md)** — architecture review (corpus + per-service findings,
  applied fixes, and open decisions to resolve before/during implementation).
- **[docs/decisions/](docs/decisions/)** — ADR log (decision-of-record); start at
  **[0001](docs/decisions/0001-lightened-runtime-architecture.md)** (lightened runtime).

> **Current focus:** a proof-of-concept narrowed to **Finance + Business** on **YouTube Shorts +
> TikTok**, posting private-first. The blurb above and STRATEGY/DESIGN describe the broader
> 3-niche / 4-platform vision; **[POC.md](docs/POC.md) wins on what's being built now.**

## Status
Pre-implementation (planning). No pipeline code yet. Active scope = **[docs/POC.md](docs/POC.md)**.

## Stack at a glance
> Runtime topology: **[ADR 0001](docs/decisions/0001-lightened-runtime-architecture.md)** (two
> planes: the host owns the GPU — ComfyUI + a per-batch LLM — CPU stages call it over HTTP) as
> re-shaped by **[ADR 0015](docs/decisions/0015-runner-first-orchestration.md)**: a **Python
> conductor** (stage manifests → DAG, cache, retries, status) orchestrates everything under a
> WSL2 systemd timer; one `DATA_ROOT` holds everything; **kind/Argo is a deferred deployment
> profile** kept honest by a CI-built shared image.

- **Orchestration:** the Python conductor (runner-first, ADR 0015); Argo/kind = deferred profile
- **GPU plane (host):** ComfyUI owns the GPU — FLUX / LTX / ESRGAN / RIFE / GFPGAN; no GPU-in-kind
- **Script:** Ollama + Qwen2.5-14B (hook-first, real-data for finance/business)
- **Visuals:** real-footage-first (Pexels/Pixabay/Mixkit/Coverr/Videvo) + FLUX.1-schnell fill
  + LTX-Video / Ken Burns + Real-ESRGAN/RIFE + GFPGAN/CodeFormer
- **Voice:** Kokoro-82M (Apache-2.0)
- **Subtitles:** WhisperX (word-level alignment)
- **Music:** YouTube Audio Library / Pixabay Music (commercial-safe)
- **Render:** ffmpeg + NVENC, finishing polish (grade/grain), per-platform native cuts
- **QC + distribution:** automated QC gate → YouTube / TikTok / Facebook / Instagram APIs
