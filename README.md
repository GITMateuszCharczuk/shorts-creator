# shorts-creator

A free, self-hostable, Kubernetes-native (Kind-compatible) pipeline that automatically
produces and publishes YouTube Shorts across five categories: **history, geopolitics,
moving story, tech news, horror story**.

The pipeline: pick a category → build visuals (real stock footage + AI fill + GPU
motion/upscale) → AI narration (TTS) → synced animated subtitles → mood-matched music →
render a 9:16 video → optionally upload to YouTube.

**Design constraints:** no recurring cost, commercial/monetization-safe licensing, no
copyright strikes, runs locally on `kind` with a single NVIDIA GPU.

## Status
Pre-implementation. The full blueprint lives in **[docs/DESIGN.md](docs/DESIGN.md)** —
architecture, tool choices, licensing matrix, YouTube constraints, milestones, and open
risks.

## Stack at a glance
- **Orchestration:** Argo Workflows on kind, artifacts via MinIO
- **Script:** Ollama (Llama 3.1 / Qwen 2.5)
- **Visuals:** Pexels/Pixabay stock + FLUX.1-schnell + LTX-Video / Ken Burns + Real-ESRGAN/RIFE
- **Voice:** Kokoro-82M (Apache-2.0) / Piper
- **Subtitles:** WhisperX (word-level alignment)
- **Music:** YouTube Audio Library / Pixabay Music (commercial-safe)
- **Render:** ffmpeg
- **Upload:** YouTube Data API v3
