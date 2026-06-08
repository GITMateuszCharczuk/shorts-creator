# ADR 0009 — Content integrity, platform-scoped licensing & real-account robustness

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0002](0002-recency-and-novelty-ledger.md) (freshness/ledger),
  [ADR 0003](0003-resilience-concurrency-observability.md) (idempotency/resumability),
  [ADR 0004](0004-poc-commercial-posture-and-account-safety.md) (posture + safety gate),
  [ADR 0005](0005-editorial-quality-layer.md) (best-of-N + judge),
  [ADR 0008](0008-output-parity-hardening.md) (vision QC).
- **Touches:** spec Ch.1, Ch.4 (00a, 00b, 02, 03, 04), Ch.5 (job/script schema), Ch.6, Ch.8, Ch.9,
  Ch.10; ARCHITECTURE.
- **Origin:** a second skeptical pipeline review focused past the architecture, on
  content-correctness, licensing scope, and brand-new-account survival. Found nine gaps; this ADR
  records the decisions for all of them.

## Context

ADRs 0001–0008 made the pipeline reliable, varied, and visually competent. A correctness-and-
real-world review surfaced gaps the editorial layer doesn't cover — most importantly that the
**facts** in a YMYL finance video are only ever checked by an LLM grading an LLM, and that several
"free/safe" assumptions (music licensing, TikTok public posting, deterministic re-runs) don't hold
on inspection.

## Decision

### Content integrity (the core)

1. **Deterministic numeric grounding (#1).** Every figure cited in `script.json` carries a
   **provenance pointer into `data.json`** (`{value, source_ref}`). A cheap deterministic check —
   not an LLM — rejects/repicks any script that cites a number with **no matching source field** or
   a value that doesn't match within tolerance. The LLM fact/sanity pass (05b) stays, but it is no
   longer the *only* line of defence on numbers. This closes the worst YMYL failure: a confidently
   hallucinated statistic that an LLM judge waves through.

2. **Seed discipline makes idempotency real (#4).** A **per-video seed** (and per-generative-stage
   derivation) is generated once and **persisted in `job.json`**; `00b` best-of-N, FLUX, and LTX
   consume it. Without this, "idempotent, resumable, pure function of inputs" (ADR 0003) is false
   for the generative stages — a retried stage produces a *different* take, and a mid-pipeline
   resume can stitch assets from two takes. Seeds also make quarantine triage reproducible.

3. **Captions force-align to the known script, not a fresh transcription (#5).** Stage 03 already
   *has* the exact narration text; it must **force-align WhisperX to that text**, not free-transcribe
   the Kokoro audio and risk corrupting the exact YMYL tokens that matter (`401(k)`, tickers,
   `$1.5M`). Transcription-from-scratch is demoted to a fallback only if alignment fails.

4. **Judge independence + calibration (#6).** Best-of-N picker, 05c quality gate, and the 05x VLM
   are all the model grading itself — biased and uncalibrated. Mitigation: prefer a **different
   model family for the judge** where practical, and seed the quality floor against a **small
   human-labeled calibration set** rather than an absolute score. To keep this affordable under
   "never co-resident," the independent judge should run on a **separate CPU / small-model endpoint**
   (different family, no GPU contention with the diffusion plane) — so adopting it is a config swap
   via the per-stage judge backend (ADR 0010 D3), not a VRAM fight. Recorded as a **known weakness**
   either way — the floor is a guess until analytics + labels exist.

### Licensing & posture honesty

5. **Music sourcing is per-platform (#2).** "Strike-safe" is **platform-scoped**: the YouTube
   Audio Library grant is oriented to YouTube content, and TikTok pushes non-personal accounts to
   its **Commercial Music Library**. So Stage 04's music source becomes a **per-platform** choice
   (TikTok draws from a TikTok-cleared set / its Commercial Music Library), and each library's
   cross-platform terms are verified before use — not assumed from one shared pool.

6. **The TikTok public signal is audit-gated — say so (#3).** An unaudited TikTok app can only post
   **SELF_ONLY**, so the "≥1 genuinely public account per platform" minimum-signal goal (ADR 0004
   D4) is **unobtainable on TikTok until its audit clears** — the very audit dependency ADR 0004
   set out to decouple from. The posture is corrected to be honest: the minimum public reach/
   retention signal **leans on YouTube (unlisted→public works immediately)**; the TikTok public
   signal is **best-effort, audit-gated, and may not land within the PoC**. The DoD must not imply
   a guaranteed TikTok public signal.

### Real-account & external-dependency robustness

7. **Account provisioning + warming (#7).** Brand-new accounts posting API-driven daily YMYL
   content is a flag pattern. Accounts get a **provisioning step** (profile, bio, avatar, niche
   signals) and a **warming period** before the automated cadence ramps — folded into the existing
   phased ramp (ADR 0004 D2), not a new mechanism.

8. **External-API budgeting + caching (#8).** Free tiers are tight (Alpha Vantage ~25 req/day;
   Pexels/Pixabay hourly caps) and best-of-N × N-candidates-per-beat × batch can exhaust them.
   `00a`/`01a` get **request budgeting + a local cache** (dedup identical queries within a batch,
   cache market pulls), and a tripped budget is a **first-class WARN/degrade**, not a silent
   throttle or hard fail.

9. **News corroboration for `news_reaction` (#9).** A single RSS item can be rumor, satire, or
   wrong. Before `news_reaction` commits a fresh story, require **corroboration across ≥2 reputable
   sources** (or a source-reliability weighting); an uncorroborated item degrades to a lower-
   confidence treatment or is skipped via the starvation ladder (ADR 0002).

## Consequences

**Positive**
- Numbers are grounded in fetched data, not vibes — the YMYL bar gets a deterministic floor.
- Re-runs are genuinely reproducible; the idempotency claim becomes true.
- Captions stop corrupting the exact terms that matter; music stops being platform-illegal.
- The PoC stops over-promising a TikTok public signal it may not be able to produce.

**Negative / costs**
- More schema surface (`number→source_ref`, `seed`), a deterministic verifier seam, per-platform
  music config, and a warming step — all config/plumbing, no architectural change.
- A second judge model (if adopted) is another model to host; may stay single-model with the
  weakness recorded for the PoC.

## Open (tracked)

- Numeric-match **tolerance rules** + how strictly to bind narrative phrasing to raw figures.
- Whether to actually run a **separate judge model** in the PoC or just record the bias.
- The **human-labeled calibration set** for the quality floor.
- Per-platform **music libraries** + verified cross-platform terms.
- **Warming duration** + provisioning checklist; per-API **budget numbers** + cache TTLs;
  the **corroboration threshold** + reputable-source list per niche.
