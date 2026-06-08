# ADR 0005 — Editorial quality layer & production-craft hardening

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0001](0001-lightened-runtime-architecture.md),
  [ADR 0002](0002-recency-and-novelty-ledger.md),
  [ADR 0003](0003-resilience-concurrency-observability.md),
  [ADR 0004](0004-poc-commercial-posture-and-account-safety.md).
- **Touches:** spec Ch.1 (DoD), Ch.4 (00b, 01a, **new 01e**, 02, 03, 04, 05, 05b, **new 05c**),
  Ch.5 (contracts + profiles), Ch.6 (hook/treatment/best-of-N), Ch.7 (throughput), Ch.8 (gates),
  Ch.9 (editorial voice). New stages `01e` (data-viz) and `05c` (creative-QC).
- **Origin:** a four-specialist **output-quality** review (retention, visual craft, audio, creative
  direction). All four independently reached the same diagnosis.

## Context

The runtime is hardened (0003) and the posture is set (0004), but a quality-focused review found
the design answers *"does the pipeline run and stay safe?"* far better than *"are the videos any
good?"* The reviewers converged on one structural diagnosis:

> **Every stage has an owner for correctness and safety; no stage owns quality, coherence, or
> point of view.** Each stage validates its own schema, yet nothing checks that the visuals say
> what the words say, that the music's energy matches the hook, or that the video has a point —
> the sum is worse than the parts.

This collides head-on with the **DoD's own promise** (Ch.1): "a human spot-check would call it
genuinely good, not AI slop." The only gate (05b) was scoped by ADR 0004 to **safety only**, so
the "genuinely good" bar had **no enforcement mechanism** — it was left to faith. The review also
found the production stages (visuals, captions, voice, music) specified as one-line tool
invocations, omitting exactly the craft decisions that separate a professional Short from an "AI
slideshow" — the precise slop signature the research says is now an account-survival risk.

## Decision

### Editorial quality layer (the missing "owner of the whole")

1. **A `treatment` artifact, emitted by 00b, that every downstream stage renders against.** A
   compact creative brief: one-line thesis/"so-what", the angle, tone, a **per-beat visual
   motif** (intended shot + why, not just a keyword), and an **energy curve**. This replaces the
   three independent lossy lookups (beat→keyword→stock, mood-string→track) with one coherent
   through-line. **Highest-leverage change in the layer.**

2. **Best-of-N + an LLM-as-judge creative-QC.** 00b generates **N** treatments/scripts and a
   judge rubric (hook strength, says-something-non-obvious, visual↔script coherence, payoff
   lands) **selects the winner** — *until the deferred analytics loop exists, the judge is the
   picker*. The same judge powers a **new `05c` creative-QC gate** that scores the assembled
   video against a **quality floor**; below floor → **quarantine, not auto-post**. `05c` is the
   **quality** gate; `05b` remains the **safety** gate — two distinct gates. This is what makes
   the DoD's "genuinely good" clause enforceable.

3. **The hook is a first-class composite object, not a spoken line.** Variants are **selected**
   (by the judge), not blind-picked; the hook carries `{spoken, on_screen_text,
   first_frame_visual_spec, target_duration ≤2s}` and downstream stages treat **frame 1** as a
   designed pattern-interrupt (it is also the TikTok cover frame). All variants + the chosen one
   + their scores are **persisted to the ledger** (the "reserved field" pattern) to seed the
   future feedback loop from day one.

### Production-craft specs (turn one-liners into real stages)

4. **Pacing & assembly contract (Stage 05).** Promote render from "ffmpeg concat" to an editorial
   engine: **word-timed cuts** (reuse the WhisperX timestamps already produced for captions), a
   **visual-change-rate** target (no slideshow), **per-clip color *matching* before** the global
   grade (a blanket LUT over mismatched exposures fixes nothing), a **brand-overlay** system, and
   a **deliberately chosen thumbnail/cover frame**.

5. **Stock relevance engineered + a data-viz stage.** Stage 01a adds **candidate ranking**
   (image-text similarity, e.g. CLIP) against the beat + **cross-video dedup** (no coin-jar clip
   in every video). A **new Stage `01e` data-viz** turns `data.json` numbers into **branded
   animated charts/counters** — deterministic, artifact-free, license-free, and the natural
   on-screen citation surface; it fills the beats stock can never match (the core finance visual,
   currently absent).

6. **Audio performance layer (Stages 02 / 04).** A **text-normalization + pronunciation-lexicon**
   pass so finance tokens (`$1.5M`, `401(k)`, `FOMC`, `Q3`, `ETF`) are spoken correctly;
   **per-beat prosody markup** (emphasis / pause / pace, with a deliberate hook delivery) driving
   Kokoro; a **closed music mood/energy taxonomy tied to each format** + a curated library +
   anti-repeat; a **transition-SFX layer** (whoosh on cut, tick per list item, riser+impact on
   reveal); **per-platform LUFS** targets.

7. **Caption design (Stage 03).** A real style spec — brand font, ≤N words on screen, heavy
   stroke/shadow, **emphasis-word styling** (00b tags the punch word), animation, and
   **per-platform vertical safe zones** (TikTok UI occludes different regions than YouTube).
   Caption position/timing becomes a genuine per-platform render-differentiation lever
   (closes part of the Ch.10 open item).

8. **Expanded QC coverage (Stage 05b).** The safety gate adds **aesthetic/artifact** checks —
   morphing hands, LTX temporal warp, garbled AI text → quarantine or fall back to Ken Burns on a
   clean still (open-source 16 GB img2vid produces these *by expectation*, not rarely) — and
   **audio-defect** checks (dead-air before the hook, loudness within the platform window,
   synth-duration matches script).

### Identity

9. **Channel persona / editorial voice in `profiles/*.yaml`.** A recurring POV the 00b model
   writes **in**, not just **about** — so variety comes from *what the channel thinks*, not only
   *which of 8 templates it filled*. Template-rotation gives combinatorial variety but **voice
   uniformity**; at 2–4/day for weeks that reads as a content farm (a YouTube-enforcement risk,
   not just an aesthetic one). "Does the channel have a personality" becomes an explicit
   acceptance criterion.

### Engagement overlay (follow-up addition)

10. **Animated engagement-CTA bump (Stage 05, per-platform).** A short (~2–3s) branded animation
    — `Like` + a **platform-specific** second verb (`youtube → Subscribe` + bell, `tiktok → Follow`,
    `instagram → Follow`) — pops in **once** at a **constrained-random mid-roll slot** and animates
    out. The asset is a **brand-kit element** (channel-styled, not a generic sticker, ADR 0005 D9);
    the verb/icon mapping is the natural **per-platform render delta** (so the YT and TikTok cuts
    differ for a real reason, not a penalized re-encode). "Constrained" is deliberate: the slot is
    drawn from an **eligible window** — **never** the hook (first ~3s pattern-interrupt) or the
    outro, and skipping data-viz / emphasis-caption beats — so placement *varies* (a fixed 0:15
    bump is itself a content-farm tell) without ever stepping on the moments that carry the video.
    The draw is **seeded from `video_id`** so re-renders reproduce it (the pipeline is
    reproducible-by-design), and the chosen slot + variant are **persisted to the ledger** (same
    reserved-field pattern as the hook variants, D3) since placement timing is a future-A/B knob.
    `05b` **whitelists** the channel's own CTA (it is not a *foreign* watermark) but still verifies
    it sits in the **platform-safe zone** (not occluding TikTok's right-rail UI or the caption band).

Moving the ramp's human review *earlier* (to the treatment, where edits are cheap and steer
everything) was proposed and **declined for now**: the human stays at **publish** per ADR 0004.
The automated **best-of-N judge + `05c` creative-QC** are the early-quality owners instead; the
human remains the final publish veto. (Re-openable if the automated judge proves too lenient.)

## Consequences

**Positive**
- The "genuinely good" half of the DoD finally has an owner (the treatment) and an enforcer
  (creative-QC) — it stops being faith.
- Best-of-N converts cheap overnight GPU into materially better median output without any new
  feedback infrastructure.
- The finance niche gets its signature visual (animated data-viz) and loses its top slop tells
  (mismatched stock, mispronounced numbers, monotone VO, generic karaoke captions).

**Negative / costs**
- Throughput: best-of-N adds N−1 LLM passes (cheap — model already resident), `05c` adds a judge
  pass, `01e` adds a CPU stage. The ~25 min/video baseline (ADR 0003) is **re-opened** and must
  be re-measured.
- Real scope growth: two new stages, a treatment contract, a judge rubric, craft specs, a brand
  kit + persona per niche. This is the deliberate "more thought and love" the review asked for.
- The judge is itself a small-model component; its calibration is a new tuning surface.

## Open (tracked)

- The **quality-floor value + rubric weights**, and **N** for best-of-N.
- The **relevance model** (CLIP variant) and **data-viz tech** (matplotlib/Plotly→frames vs
  Remotion/Lottie).
- Curated **music + SFX libraries**, the **pronunciation lexicon**, and **per-platform LUFS**
  values.
- **Persona definitions** per niche; the **brand kit** (palette/font/logo/lower-thirds, **+ the
  engagement-CTA animation**) per niche.
- The **engagement-CTA** specifics: the eligible-window bounds, whether it may fire more than once,
  and whether a stronger end-card belongs alongside the mid-roll bump.
- Whether to revisit the **human-at-treatment** checkpoint if the automated judge proves lenient.
