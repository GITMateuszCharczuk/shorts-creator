# Content & Monetization Strategy

The business fundamentals behind the pipeline: what we make, where it earns, who clicks it,
and how it stays monetizable. Read alongside `DESIGN.md` (architecture/tools). Where the two
disagree, **this doc wins on strategy**, DESIGN wins on implementation.

> ⚠️ **Scope note:** this doc covers the full 3-niche / 4-platform vision. The **current build
> is a proof-of-concept** narrowed to **Finance + Business** on **YouTube + TikTok** (true crime
> dropped, FB/IG deferred). See **[POC.md](POC.md)** — authoritative on present scope.

> Figures below are grounded in 2026 market data (see Sources). RPMs vary by niche,
> geography, and season — treat them as directional.
>
> **⚠️ Corrected by research (see `research/01-business.md`, `research/04-limitations-and-risks.md`):**
> An earlier draft listed **Facebook Reels at $2–5 RPM** — that was *long-form in-stream*
> revenue, **not Reels**. Under Meta's Aug 2025 Content Monetization program, Reels pay
> ~**$0.02–0.20/1k**. **TikTok is the only meaningful short-form ad payer** ($0.20–$1.00,
> up to ~$2.50 in finance); YouTube Shorts and IG/FB Reels are pennies-to-zero. The honest
> takeaways: **Shorts/Reels ad-share is a funnel, not the income** — the real money is
> **long-form (10–50× RPM)** and **affiliate**; and **True Crime carries catastrophic
> defamation risk** ($17.5M verdict, May 2026) and should be dropped or heavily gated.
> The tables below are left as originally written; trust the research docs where they differ.

---

## 1. The core insight: YouTube Shorts is the *worst*-paying leg

Ad-share RPM, finance niche, per 1,000 views:

| Platform | Finance RPM | Direct ad rev-share? | Monetization threshold |
|---|---|---|---|
| **Facebook Reels** | **$2–5** | ✅ in-stream ads | 5k followers + 60k watch-min/60d |
| **TikTok Creator Rewards** | **$1–6+** | ✅ | 10k followers + 100k views/30d, **videos ≥60s** |
| YouTube Shorts | $0.01–0.12 | ✅ (shared pool) | 1k subs + 10M Shorts views/90d (or 4k watch-hrs) |
| Instagram Reels | ~$0 (bonuses only) | ❌ | invite-only bonuses |

**Implication:** the money is on **Facebook Reels + TikTok**, ~20–50× YouTube Shorts.
YouTube = reach + funnel + the eventual long-form upgrade path. Instagram = audience/reach
only (no real ad money). We still post everywhere (free distribution), but **optimize for
FB/TikTok economics**.

---

## 2. Channels & niches (3 channels, one pipeline)

All three sit in the **high-RPM money cluster** and share an automation-friendly,
data/narrative-driven format.

| Channel | Niche | Why | RPM tier | Production recipe |
|---|---|---|---|---|
| **C1** | **Finance / investing** | Highest RPM on every platform; real-data originality is easy | $9–21 (YT long), $2–6 (Reels/TikTok) | live market data → original charts → explainer |
| **C2** | **True crime / dark mysteries** | High RPM + high retention; strong hooks; overlaps history/horror interest | $8–12 | narrative + cinematic stock + AI-fill atmosphere |
| **C3** | **Business / entrepreneurship** | High RPM, same audience as finance, affiliate-friendly | high | case-study/explainer + clean corporate visuals |

The pipeline parameterizes per channel via `profiles/<channel>.yaml` (visual style, voice,
music mood, hook templates, data sources).

---

## 3. Format & clickability

- **Length: target 60–90s** (not 30s). Required for TikTok payouts; allows real substance
  (lowers "low-effort" signal); future-proofs for YouTube mid-rolls.
- **Hook-first.** Shorts/Reels are swipe-fed — the **first 1–2 seconds** decide watch vs
  swipe. The script LLM's #1 deliverable is a scroll-stopping hook + a retention curve, NOT
  just narration. Generate **multiple hook variants** and let analytics pick winners.
- **Retention is the ranking signal** (watch-through, swipe-away, rewatches, shares). Real
  footage + tight pacing + payoff beat AI-slop that gets swiped.
- **Per-platform native renders** (see §5) — distinct cut per platform, no foreign
  watermarks.

---

## 4. Automation: "auto + safety-net" (chosen)

Full automation of **production and posting**, wrapped in guardrails so we don't trip the
demonetization profile. You are not editing videos; the safety-net runs automatically.

1. **Originality from real data** *(strongest defense).* Finance/business: pull live data
   (Alpha Vantage / Yahoo Finance / FRED, free) → auto-generate **original charts** + framed
   analysis. Real numbers + own visuals = "original insight," not a regurgitated template.
2. **Variation engine.** Rotate formats, hook styles, layouts, voices, music, pacing —
   parameterized so no two videos look stamped from one mold.
3. **Automated QC gate.** Second-pass LLM fact/sanity + hallucination flag; claims/profanity
   filter; render-integrity checks (dead audio, black frames). Auto-reject before posting.
4. **Phased volume ramp.** NOT 15/day on day one (that screams "farm"). Start ~1–2/day/
   channel, prove quality + compliance, then scale toward the 5/day/channel target.
5. **Distinct channel identities** so the 3 channels don't pattern-match as one farm.
6. **Weekly human spot-audit** (~5 min, sample review) — catches drift without per-video work.

---

## 5. Compliance (the existential stuff)

**YouTube "inauthentic content" policy (July 15 2025).** Demonetizes mass-produced,
templated, low-variation, AI-narration-without-context content — **channel-wide**. AI is
allowed only when it **adds original value + variation**. Mitigated by §4.1–4.2 (real data +
variation) and §4.6 (spot-audit). This is why "zero-safeguard full-auto" was rejected.

**Finance/business is YMYL** (Your Money or Your Life = highest scrutiny):
- Mandatory **"educational, not financial advice"** disclaimer on every finance/business video.
- **No specific buy/sell/price-target calls.** Education, news, explainers, history only.
- **On-screen source citations** (authenticity + value).
- Ban get-rich-quick / misleading claims (demonetization *and* legal exposure).
- Accuracy pass — hallucinated finance facts are fatal.

**Duplicate / reused content (cross-posting).** TikTok's July 2025 rule penalizes reposts
with only superficial changes (crop/watermark/mirror) — 30–90 day credibility penalty.
Platforms can't see each other, but each detects **foreign watermarks** and **within-platform
dupes**. So: **render a distinct native cut per platform** — no watermarks, platform-specific
caption style / hook / sound / length. Never push the identical file to all four.

**Copyright / licensing.** Unchanged from DESIGN §6: commercial-safe stock, TTS, music only.

---

## 6. Honest earnings expectation

- Ad-share is a **volume + time** game. Thresholds first: TikTok (10k followers + 100k
  views/30d), FB (5k followers + 60k watch-min/60d), YT (1k subs + 10M Shorts views/90d).
  Expect **months** of sub-threshold grind before meaningful payout.
- Once monetized, finance/business across FB+TikTok is the realistic earner; YouTube Shorts
  ad-share alone would be pennies.
- **Biggest upgrade lever later:** add **long-form** companion videos (2–3× RPM, easier
  watch-hours path) and/or **affiliate** (finance/business convert well). Ad-share-only caps
  the ceiling.
- The pipeline is a **discovery engine**; treat early months as audience-building, not income.

---

## 7. Feedback loop (don't fly blind)

Pull per-video analytics (retention %, swipe-away, view velocity, watch-time) from each
platform back into the system; rank hooks/formats; bias generation toward winners. Without
this, quality never compounds. (Build after the core pipeline works — see DESIGN milestones.)

---

## Sources
- YouTube Shorts monetization & RPM: vidIQ, unkoa, virvid (2026)
- YouTube inauthentic-content policy (Jul 2025): Fliki, SubSub, Yahoo Finance
- TikTok Creator Rewards (≥60s, RPM): postlinkapp, fluxnote, TikTok Support
- Facebook/Instagram Reels monetization: fluxnote, artha.link, Meta Help
- Cross-posting / duplicate-content penalties: napolify, Socialync (2025–26)
