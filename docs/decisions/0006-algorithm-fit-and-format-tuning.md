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

And on the **monetization** side (the reason 60–90s existed):

- **TikTok Creator Rewards pays only on videos *over* 60s** — a sub-minute video earns **$0** no
  matter how viral; the recommended monetization band is **61–70s**. Eligibility itself needs
  **10k followers + 100k views / 30 days** (so audience growth has to come *first*).
- The **hybrid most monetizing creators run** is precisely two lanes: short clips (<30s) to grow
  reach + 1-min-plus originals to earn — and TikTok's 2026 algorithm is **actively promoting
  1–3 min content**, so the longer lane is not purely a revenue tax.
- The **pure-engagement sweet spot is 21–34s** (highest completion, shares, comments).

The flat 60–90s target is therefore fighting completion rate. This does **not** reopen ADR 0004
D1 (the PoC still does **not** chase view/revenue metrics) — but **form** (length, pacing, loop,
keywords, CTA) is craft we bake in regardless, so it is worth getting right now.

## Decision

1. **Per-format length — two deliberate lanes (supersedes the flat 60–90s as a *single* rule).**
   Length becomes a **per-format** field in the `formats/` library (which already carries a
   "length target"):
   - **Reach lane (~20–35s)** — punchy, hook-native formats (`news_reaction`, `surprising_stat`,
     `myth_buster`) optimized for **completion rate / attention** (the 21–34s band gets the
     highest completion, shares and comments). Below the TikTok payout bar, which is fine in the
     PoC (we don't chase revenue yet — ADR 0004 D1) — and it is the lane that *grows* the audience.
   - **Monetization lane (~61–90s, target 61–70s)** — depth formats (`explainer`, `ranked_list`,
     `how_to_steps`, `head_to_head`, `cautionary_tale`) kept **strictly over 60s** (a 60.0s video
     earns **$0** from Creator Rewards; the recommended band is 61–70s). TikTok's 2026 algorithm
     also actively promotes 1–3 min content, so this lane helps reach too, not only revenue.

   So we run *both*: short for views, **>60s** for monetization — chosen **per format**, not flat.

2. **Batch-mix target — phase-dependent; the PoC default is reach-heavy.** A configurable
   **rolling-window** target (not enforced inside one 2–4-video batch, which is too small to hit
   a ratio). The *eventual* hybrid is **~60% monetization-lane (≥61s)** / ~40% reach — but that
   tilt is only rational once it can pay, and in the PoC it cannot: TikTok public posting is
   **audit-gated to SELF_ONLY** (ADR 0009 D6 — Creator Rewards unreachable) and YouTube Shorts
   payout is **volume-led**, where >60s actively costs the completion rate this same ADR documents.
   So the **PoC-phase default is ~80% reach / 20% monetization** (ADR 0016-era re-review); the
   ~60% monetization tilt activates at **TikTok audit approval + YPP eligibility**, via the
   phase-dependent knob below. This is a **portfolio heuristic** — successful monetizing creators
   run exactly this
   hybrid (short clips for reach, 1-min+ originals for Rewards) — not a published constant, so it
   is a **config knob**, not a hard rule. It is also **phase-dependent**: pre-eligibility (under
   10k followers / 100k views-per-30-days) the mix should tilt *toward* the reach lane to *reach*
   the bar; once eligible, tilt to the ~60% monetization split. Enforced via the format-selection
   weights (ADR 0005/0006) at batch planning, recorded in `batch.json`.

3. **Completion rate is the internal craft target (not a DoD metric).** The quality layer treats
   estimated completion / retention-curve shape as a first-class craft goal — the `05c` judge may
   weigh "would this hold to the end?" — with **~70% completion** as the aspiration. Per ADR 0004
   D1 this is a **craft target, not a success criterion**: we shape for retention, we don't gate
   "done" on measured views. (Note the tension the mix manages: longer monetization-lane videos
   trade some completion for revenue eligibility — the loop/hook/pacing craft is what protects
   their retention.)

5. **Seamless loop construction (Stage 05).** Where the format allows, the final line/frame
   **bridges back to the hook** so the Short loops cleanly; replays inflate AVD and signal
   engagement. The loop must not be defeated by the end-card (D7).

6. **Engagement-signal-aware CTAs.** Because **shares + saves outweigh likes**, the spoken / on-
   screen CTA may be a **save/share** prompt where it fits ("save this," "send this to someone
   who…"), not only a like. The mid-roll **like+follow bump** (ADR 0005 D10) is unchanged.

7. **Search/FYP keyword placement.** 00b emits a **primary keyword** threaded three ways: the
   caption's **first ~150 chars** (Stage 06 metadata), **on-screen text in the first 2–3s**
   (Stage 03), and **spoken in the opening lines** (Stage 02) — so the video is discoverable, not
   just recommendable.

8. **Closing end-card CTA (the user's ask).** A short (~1.5–2.5s) branded **end-card** with a
   **FOMO follow** line — default **"Follow — the algorithm only shows us once"** /
   **"Follow or you won't see us again"** — platform-aware (`Subscribe` on YouTube, `Follow` on
   TikTok/IG). The phrase is a **config field in the brand kit**, rotatable / A-B-able, persisted
   to the ledger. It **complements** the mid-roll bump (ADR 0005 D10): the bump is a glanceable
   mid-roll nudge, the end-card is the closing ask. It is placed so it **does not inject dead air
   that breaks the loop** (D5) — an overlay on the last beat, or just before the loop-bridge.

9. **Series / multi-part capability.** A format may declare a **series** (Part N); 00b can plan a
   multi-part arc and the end-card can become "follow so you don't miss Part 2." Multi-part series
   compound traffic and give the FOMO CTA a concrete payoff.

10. **Per-platform scheduled-publish window (Stage 06, ADR 0014 D3).** Because first-hours engagement
    velocity is a ranking signal (Context), Stage 06 gains an optional **`publish_window`** — a
    per-platform, per-niche peak-audience slot a finished render is **held for and posted into**,
    rather than posting at batch-completion time. Resolved through the normal config precedence
    (global → niche → platform, ADR 0010 D5); **unset = post immediately**, so it is a no-op for M0.
    The exactly-once posted-state ledger (ADR 0003 D1) makes a deferred post safe. Default windows
    need real audience data and are an open item until the analytics loop lands.

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

- The **batch-mix ratio** (default ~60% monetization-lane) and its **rolling-window size**; the
  **pre-eligibility vs post-eligibility** tilt and what triggers the switch.
- Exact **per-format second-ranges** and which formats must loop.
- The **end-card phrase library** + rotation policy; whether YouTube wants a different default.
- Whether `05c` should include a **predicted-completion** heuristic, and how to estimate it
  pre-publish.
- Revisit all of the above against **real** retention data when the analytics phase lands.
