# ADR 0008 — Output-parity hardening: vision-QC, format/length fit, asset fallback & honest limits

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0005](0005-editorial-quality-layer.md) (the QC gates + treatment),
  [ADR 0006](0006-algorithm-fit-and-format-tuning.md) (the two length lanes),
  [ADR 0007](0007-format-aware-layout-templates.md) (format layouts + the compositor).
- **Touches:** spec Ch.1 (honest limits), Ch.4 (00b, 01a, 05b, 05c), Ch.6 (lane support +
  content scaling), Ch.8 (the shared vision pass), Ch.9 (trending-audio trade-off), Ch.10;
  ARCHITECTURE.
- **Origin:** a skeptical "will it look human / where are the gaps" review of the spec. Found
  three fixable holes and a set of inherent ceilings the spec was silently over-claiming past.

## Context

After ADRs 0005–0007 the **structural** craft is strong — the output will read as a competent
*faceless* channel. But the review surfaced that several quality guarantees are thinner than
written, and a few human-parity ceilings were unacknowledged:

- **The `05c` creative-QC judge (and `05b`'s aesthetic checks) can't actually see the video.** As
  specced, `05c` is a *text* LLM scoring "visual↔script coherence" and "pacing" of the *assembled
  video* — but a text model only sees the script + asset manifest, **not the rendered frames**. The
  gate that's meant to *enforce* "genuinely good" judges *intent*, not *output*. Likewise `05b`'s
  "morphing hands / garbled AI text" checks (ADR 0005 D8) are visual by nature and need pixels.
- **Format × length-lane × layout were designed in separate passes and never cross-checked.** A
  10-item `ranked_list` cannot live in a 20–35s reach video (~2s/item is unwatchable); some formats
  are intrinsically long. No compatibility rule exists.
- **Format-aware fetch (ADR 0007) concentrates stock scarcity exactly where it shows most.** A
  `ranked_list` needs ~10 *distinct, relevant, deduped* clips from *finite* free libraries; "no
  good match for item 7" has no defined fallback, so the most prominent format is the most likely
  to degrade to mismatched/generic b-roll. The hook's `first_frame_visual` has the same exposure.
- **Inherent ceilings** (faceless + small-TTS connection limit; no trend-audio jacking because of
  the strike-safe music rule; LLM+YMYL humor/hot-take/lived-experience limits) were not stated, so
  the spec implicitly over-promised "indistinguishable from human."

## Decision

1. **One vision pass, feeding both QC gates (`05b` + `05c`).** Add a **vision-language model over
   sampled keyframes** (the hook frame, the end-card frame, and a few per-beat frames) plus the
   script + asset manifest. It runs **once** and serves both gates: `05b` reads it for
   **artifact/legibility/safe-zone** defects (morphing hands, garbled on-screen text, occluded
   captions), `05c` reads it for **visual↔script coherence, hook strength, pacing feel**. Candidate:
   **Qwen2.5-VL** (Apache-2.0 — stays on the spine). It is another **GPU citizen** under the
   **never-co-resident rule** (ADR 0001/0003): it runs in the post-render slot when FLUX/LTX are
   already evicted. This converts the quality bar from "judges intent" to "judges output."

2. **Format ↔ length-lane compatibility + content scaling (formats library).** Each format declares
   **`lane_support`** (`reach`, `monetization`, or `both`) and a **content-scaling rule** so its
   payload sizes to the target length:
   - `surprising_stat`, `myth_buster`, `news_reaction` → **reach or both** (naturally short).
   - `explainer`, `cautionary_tale`, `head_to_head` → **monetization** (need room to land).
   - `ranked_list`, `how_to_steps` → **both, scaled**: e.g. **top-3 / 3-steps** in the reach lane,
     **top-7–10 / 5+ steps** in the monetization lane — 00b sizes the item count to the lane.
   The batch-mix selector (ADR 0006 D2) only picks format×lane pairs that are declared compatible.

3. **An asset fallback ladder for every layout media zone (and the hook frame).** Per region, an
   **ordered, deterministic** fallback so a prominent slot never ships a mismatched generic clip:
   **ranked stock (01a) → targeted AI generation (01b) → a branded data-viz/typographic card
   (01e/compositor)**. The terminal fallback is a **clean on-brand card**, never an irrelevant
   stock clip. The hook's `first_frame_visual` uses the same ladder with a **designed typographic
   hook card** as its guaranteed floor — the most important frame can degrade gracefully but never
   to generic. Cross-video dedup (ADR 0005 D5) still applies at every rung.

4. **Honest known-limits — recorded, not hidden.** The DoD bar is "a human would call it genuinely
   good," **not** "indistinguishable from a top personality creator." State the ceilings explicitly:
   - **Faceless + small-TTS connection ceiling** — no on-camera presence, bounded vocal emotion;
     this reads as a strong *faceless* channel, a notch below charismatic hosts. (By design.)
   - **No trending-audio jacking** — the strike-safe music rule (Ch.9) structurally blocks riding
     trending commercial sounds, a real reach cost on TikTok. **Accepted trade-off** (account safety
     over trend reach); revisit only if a licensed trending-audio path appears.
   - **Bounded humor / hot-takes / lived experience** — LLM scripting under YMYL stays
     educational/third-person; relatability is capped. (By design.)
   - **No automated community engagement** — an unattended faceless pipeline cannot reply to
     comments, so it cannot contribute the creator-reply portion of the first-hours engagement
     velocity that ADR 0006 weights. **Accepted ceiling** for the unattended PoC (ADR 0014 D4);
     revisit if a safe automated-reply path appears.

## Consequences

**Positive**
- The quality gate finally evaluates the *rendered video*, so "genuinely good" is enforceable in
  fact, not just intent — and `05b`'s visual checks become real instead of aspirational.
- The compatibility matrix kills a whole class of broken output (a 10-item list crammed into 25s).
- The fallback ladder guarantees the most-visible regions stay on-brand even when stock fails.
- Honest limits keep the project from over-claiming and set the right success bar.

**Negative / costs**
- The VLM is **another GPU model** — more VRAM pressure and one more serialized pass; combined with
  best-of-N + `05c` + data-viz + the compositor, the **end-to-end throughput budget must finally be
  reconciled** (it has been re-opened four times and never summed; the overnight 2–4/day window is
  probably still fine, but this is now a required measurement, not an assumption).
- `lane_support` + scaling adds config surface; the fallback ladder adds branching to 01a/05.

## Open (tracked)

- The **VLM choice + sampling strategy** (how many frames, which timestamps) and its VRAM/throughput
  cost; whether `05b` and `05c` truly share one inference or need two prompts.
- The **per-format `lane_support` + content-scaling** values.
- The **end-to-end throughput reconciliation** across all of ADR 0005–0008 on the real box.
- Whether to revisit any **accepted ceiling** (esp. trending audio) in a later phase.
