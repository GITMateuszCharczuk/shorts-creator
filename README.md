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
strikes, runs locally on `kind` with a single NVIDIA GPU.

## Docs
- **[docs/POC.md](docs/POC.md)** — ⭐ **authoritative current scope.** The deliberately narrow,
  deeply-engineered first slice we are building now (2 niches, 2 platforms). Read this first.
- **[docs/STRATEGY.md](docs/STRATEGY.md)** — content & monetization fundamentals (niches,
  platforms, earnings, automation policy, compliance). The *why* (full vision).
- **[docs/DESIGN.md](docs/DESIGN.md)** — architecture, tools, pipeline stages (the *how*).
- **[docs/OPTIONS.md](docs/OPTIONS.md)** — tooling decision matrix.
- **[docs/REVIEW.md](docs/REVIEW.md)** — architecture review (corpus + per-service findings,
  applied fixes, and open decisions to resolve before/during implementation).

> **Current focus:** a proof-of-concept narrowed to **Finance + Business** on **YouTube Shorts +
> TikTok**, posting private-first. The blurb above and STRATEGY/DESIGN describe the broader
> 3-niche / 4-platform vision; **[POC.md](docs/POC.md) wins on what's being built now.**

## Status
Pre-implementation (planning). No pipeline code yet. Active scope = **[docs/POC.md](docs/POC.md)**.

## Stack at a glance
- **Orchestration:** Argo Workflows on kind (GPU-in-kind), artifacts via MinIO
- **Script:** Ollama + Qwen2.5-14B (hook-first, real-data for finance/business)
- **Visuals:** real-footage-first (Pexels/Pixabay/Mixkit/Coverr/Videvo) + FLUX.1-schnell fill
  + LTX-Video / Ken Burns + Real-ESRGAN/RIFE + GFPGAN/CodeFormer
- **Voice:** Kokoro-82M (Apache-2.0)
- **Subtitles:** WhisperX (word-level alignment)
- **Music:** YouTube Audio Library / Pixabay Music (commercial-safe)
- **Render:** ffmpeg + NVENC, finishing polish (grade/grain), per-platform native cuts
- **QC + distribution:** automated QC gate → YouTube / TikTok / Facebook / Instagram APIs
