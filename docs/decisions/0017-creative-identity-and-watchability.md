# ADR 0017 — Creative identity & watchability: voice, visual signature, POV

- **Status:** Accepted (2026-06-10)
- **Builds on:** [ADR 0005](0005-editorial-quality-layer.md) (persona D9, hook D3, audio D6),
  [ADR 0006](0006-algorithm-fit-and-format-tuning.md) (series D9, end-card D8),
  [ADR 0007a](0007a-layout-template-design.md) (the energy-curve→param hook, §5 — deferred there,
  activated here), [ADR 0008](0008-output-parity-hardening.md) (the honest ceilings + fallback
  ladder), [ADR 0014](0014-content-automation-best-practice-alignment.md) (original-insight as
  survival).
- **Touches:** spec Ch.1 (ceiling mitigation), Ch.2 (persona), Ch.4 (00b/01a/02 rows), Ch.10
  (M3 row, decided-since, open #13); plans M2 (01a preferences), M3 (voice gate, persona fields,
  mascot, energy dynamics), M4 (series-aware rotation).
- **Origin:** a watchability review of the *output* (not the pipeline): the machine is excellent;
  the **creative identity is underdetermined**. Verdict: usable yes, entertaining not yet — four
  ceilings (neutral TTS, stock-cliché visuals, LLM explainer-sameness, no trend participation),
  of which the first three are addressable now. The pipeline mass-produces whatever taste it is
  given; these decisions set the taste.

## Decision

1. **The voice A/B is pulled forward from "post-M1, non-blocking" to an M3 gate — expressiveness
   is the selection criterion.** The flat TTS read is the single largest entertainment limiter.
   At M3 (where the audio layer lands), Kokoro is A/B'd against the most *expressive* open
   candidates (Orpheus / Chatterbox — judged on prosody/emotion control and hook delivery, **not**
   on size or speed), driven by the same `speech_segments` prosody contract; the winner becomes
   the channel voice. **If no open model clears the bar, a hosted expressive voice (ElevenLabs-
   class) is a recorded, deliberate exception to the no-recurring-cost constraint** — a single
   consistent branded voice is also a brand asset; the decision (and its cost) goes to the
   operator, not made silently.

2. **Data-viz is the visual identity, not a fallback.** The branded animated chart/counter/reveal
   is the one visual no competitor template-farm has — so lean in: formats *prefer* a `DataVizSlot`
   or numeric `TextCard` treatment wherever a number exists; **stock is biased abstract/textural
   over literal** (kill the coin-jar/skyline/pointing-at-charts cliché — `01a` queries carry an
   `abstract` style bias and literal-cliché terms are denylisted); a **clean branded "screen/app
   mockup" card** showing the number is preferred over stock people. Target identity: *"the
   finance channel with the cleanest animated data."*

3. **The persona is an opinionated character, not a tone setting.** ADR 0005 D9's "does the
   channel have a personality" criterion gets concrete, *required* profile fields: a **named
   stance list** (positions the channel argues from, e.g. "incentives over hustle-culture"), a
   **catchphrase** (used in the end-card/CTA rotation), and **recurring segments** (named series,
   D5). 00b writes *from the stances* — a take the persona would argue, not a neutral summary —
   which also feeds the ADR 0014/0016 original-insight gate something to be original *with*.

4. **The hook doubles down: text-first pattern-interrupt is the DEFAULT first frame.** The
   designed typographic hook card (ADR 0008's *floor*) becomes the *default*: a bold claim as
   frame 1, with stock/AI media behind-or-after only when it demonstrably beats the card. Hook
   variant count N is raised (config; judged hard by the 00b judge + floor) — the first 1.5s is
   ~60% of the outcome and is exactly where strong *writing + design* must carry what the voice
   cannot.

5. **Series are activated for habit formation (ADR 0006 D9 → used, not just supported).** Each
   niche profile defines **≥1 recurring series** ("Daily market in 30s", "Myth-buster Monday");
   the M4 batch planner's rotation is **series-aware** (a series slot schedules its format +
   title pattern on its cadence); the end-card leverages it ("don't miss Part 2 / tomorrow's
   30s"). Habitual return viewership compounds better than chasing the virality this design has
   structurally opted out of.

6. **A brand mascot enters the brand kit.** A simple, consistent animated brand character/mark
   (a `BrandOverlay`/end-card element, channel-styled per ADR 0005 D10's pattern) as a cheap
   proxy for the missing face — identity and recognition without the avatar risk.

7. **The energy curve actually drives dynamics (activates ADR 0007a §5's deferred hook).** The
   treatment's `energy_curve` (ADR 0005 D1) modulates, per beat: **voice rate** (a multiplier on
   the `speech_segments` prosody rate), **music intensity** (the 04 mood/energy pick + duck
   depth), and **cut/animation pacing** (the resolve step scales animation `dur`/overshoot with
   beat energy). A video gets *dynamics* — build, peak, land — instead of a flat read. Deterministic
   (the curve is in the script; the mapping is pure), so golden tests still hold.

**Recorded for later, not now:** an AI avatar / talking-head layer is the eventual ceiling-breaker
on connection — deferred (large add, its own slop/uncanny risk); the mascot (D6) is the interim.
Trend participation stays declined (ADR 0008's accepted trade).

## Consequences

**Positive** — the three levers that actually decide watchability (voice, visual signature, POV)
become decisions instead of defaults; everything lands inside existing seams (TTS backend swap =
config per ADR 0010; queries/persona/series = data; energy mapping = pure functions), so the cost
is mostly *taste work*, not engineering.

**Negative / costs** — the voice A/B becomes an M3 gate (schedule risk if no open model clears the
bar → the paid-voice decision lands on the operator); abstract-stock bias narrows an already
finite pool (the fallback ladder + data-viz absorb it); persona stances need an editorial pass per
niche (a human, once); the energy mapping adds three small tuning surfaces.

## Open (tracked)

- The voice A/B rubric (what "clears the bar" means: hook delivery, emphasis, naturalness ×
  per-segment rate control) + the paid-voice cost ceiling if invoked.
- The stance lists + catchphrases per niche (an editorial authoring task, M3 Part D).
- Mascot design (one asset, M3 brand kit).
- Energy→rate/intensity/pacing mapping constants (seeded at M3, tuned against the ramp's labels).
