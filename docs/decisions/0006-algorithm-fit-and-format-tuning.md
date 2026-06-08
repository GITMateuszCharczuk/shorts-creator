# ADR 0006 — Algorithm-fit & format tuning (length, loop, engagement signals, CTA)

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0004](0004-poc-commercial-posture-and-account-safety.md) (form vs metrics),
  [ADR 0005](0005-editorial-quality-layer.md) (the editorial quality layer it tunes).
- **Touches:** spec Ch.1 (length target), Ch.4 (00b/02/03/05/06), Ch.6 (format library), Ch.10;
  ARCHITECTURE.
- **Origin:** a follow-up scan of current (2026) short-form best-practice + algorithm data, plus a
  user request for a closing follow CTA. The data **contradicted a headline parameter** we'd
  carried since `STRATEGY.md` — worth a record, not a silent edit.

## Context

`STRATEGY.md`/`DESIGN.md` fixed a flat **60–90s** length, chosen deliberately for **TikTok
monetization eligibility** (Creator Rewards needs ≥1 min). Current data points the other way for
**reach**:

- Completion rate / watch-time is the **#1 ranking signal (~40–50% of the weight)**; the rough
  **viral-push bar is ~70% completion**.
- TikTok completion averages **~72% under 30s** vs **~54% at 30–60s**; top Shorts cluster
  **25–35s** (viral avg ≈ 33s), ~half of viral Shorts are **20–40s**. (But sub-15s under-performs
  — *40s+ is ~33% more engaging than very short*, per our own `research/02`.)
- **First 3s** decide it — 50–60% of drop-off is there.
- **Shares & saves now outweigh likes**; **engagement velocity** in the first hours is weighted.
- TikTok indexes **keywords** in the caption's first ~150 chars, in on-screen text in the first
  2–3s, and in the voiceover.
- **Seamless loops** push Average View Duration >100% via passive replays — a strong signal.

The flat 60–90s target is therefore fighting completion rate. This does **not** reopen ADR 0004
D1 (the PoC still does **not** chase view/revenue metrics) — but **form** (length, pacing, loop,
keywords, CTA) is craft we bake in regardless, so it is worth getting right now.

## Decision

1. **Per-format length range — supersedes the flat 60–90s.** Length becomes a **per-format**
   field in the `formats/` library (which already carries a "length target"). Punchy, hook-native
   formats (`news_reaction`, `surprising_stat`, `myth_buster`) target **~20–40s** for completion
   rate; depth formats (`explainer`, `ranked_list`, `how_to_steps`, `head_to_head`,
   `cautionary_tale`) may run to **~60s**. The ~60s lane **deliberately stays TikTok-monetization-
   eligible** (≥1 min where it matters) for the future revenue phase, so we optimize reach now
   without burning the monetizable format.

2. **Completion rate is the internal craft target (not a DoD metric).** The quality layer treats
   estimated completion / retention-curve shape as a first-class craft goal — the `05c` judge may
   weigh "would this hold to the end?" — with **~70% completion** as the aspiration. Per ADR 0004
   D1 this is a **craft target, not a success criterion**: we shape for retention, we don't gate
   "done" on measured views.

3. **Seamless loop construction (Stage 05).** Where the format allows, the final line/frame
   **bridges back to the hook** so the Short loops cleanly; replays inflate AVD and signal
   engagement. The loop must not be defeated by the end-card (D6).

4. **Engagement-signal-aware CTAs.** Because **shares + saves outweigh likes**, the spoken / on-
   screen CTA may be a **save/share** prompt where it fits ("save this," "send this to someone
   who…"), not only a like. The mid-roll **like+follow bump** (ADR 0005 D10) is unchanged.

5. **Search/FYP keyword placement.** 00b emits a **primary keyword** threaded three ways: the
   caption's **first ~150 chars** (Stage 06 metadata), **on-screen text in the first 2–3s**
   (Stage 03), and **spoken in the opening lines** (Stage 02) — so the video is discoverable, not
   just recommendable.

6. **Closing end-card CTA (the user's ask).** A short (~1.5–2.5s) branded **end-card** with a
   **FOMO follow** line — default **"Follow — the algorithm only shows us once"** /
   **"Follow or you won't see us again"** — platform-aware (`Subscribe` on YouTube, `Follow` on
   TikTok/IG). The phrase is a **config field in the brand kit**, rotatable / A-B-able, persisted
   to the ledger. It **complements** the mid-roll bump (ADR 0005 D10): the bump is a glanceable
   mid-roll nudge, the end-card is the closing ask. It is placed so it **does not inject dead air
   that breaks the loop** (D3) — an overlay on the last beat, or just before the loop-bridge.

7. **Series / multi-part capability.** A format may declare a **series** (Part N); 00b can plan a
   multi-part arc and the end-card can become "follow so you don't miss Part 2." Multi-part series
   compound traffic and give the FOMO CTA a concrete payoff.

## Consequences

**Positive**
- Shorter punchy videos lift completion rate *and* cut generation cost (less runtime to render) —
  it helps throughput, not just reach.
- Keyword discipline + loop + save/share framing align us with the signals that actually move
  distribution, at zero infra cost.
- The end-card gives the channel a consistent growth ask; series content compounds it.

**Negative / costs**
- Per-format length is another knob to tune; the loop-bridge and end-card add render logic that
  must not fight each other (or the caption safe-zones).
- We are acting on **third-party best-practice data**, not our own analytics — these are
  hypotheses to validate once the (deferred) feedback loop exists.

## Open (tracked)

- Exact **per-format second-ranges** and which formats must loop.
- The **end-card phrase library** + rotation policy; whether YouTube wants a different default.
- Whether `05c` should include a **predicted-completion** heuristic, and how to estimate it
  pre-publish.
- Revisit all of the above against **real** retention data when the analytics phase lands.
