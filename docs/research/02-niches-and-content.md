# 02 — Niches & Content Strategy

**Project:** shorts-creator (faceless, automated short-form pipeline → YouTube Shorts, TikTok, Facebook Reels, Instagram Reels)
**Niches in scope:** Finance, True Crime, Business
**Date:** 2026-06-07
**Status:** Research / candid assessment

---

## TL;DR (read this first)

- **Finance** has the best monetization in the business (long-form RPM $15–25+, top of every niche ranking) but is YMYL-regulated, saturated, and the Shorts→long-form funnel is where the real money is. ([OutlierKit](https://outlierkit.com/blog/most-profitable-youtube-niches), [vidIQ](https://vidiq.com/blog/post/most-profitable-youtube-niches/))
- **True Crime** is huge in demand and audience-sticky, but it is the **riskiest** of the three: chronic demonetization, graphic-content ad rules, and defamation exposure when you name real people. ([YouTube Ad Guidelines](https://support.google.com/youtube/answer/6162278?hl=en), [Change.org petition](https://www.change.org/p/youtube-stop-demonetizing-true-crime-content-on-youtube))
- **Business** is the safest middle path — strong RPM, lower legal sensitivity than the other two — but it has the highest "get-rich-quick" credibility trap and is heavily flooded with AI listicle slop.
- The single biggest cross-cutting threat to this entire project is the **2026 AI-slop crackdown**: YouTube wiped ~4.7B views off 16 AI channels and named "AI slop" as an enforcement target. ([OutlierKit AI Slop](https://outlierkit.com/resources/youtube-ai-slop-crackdown-2026/), [Search Engine Journal](https://www.searchenginejournal.com/youtubes-ai-slop-problem-and-how-marketers-can-compete/567297/)) A faceless auto-pipeline is structurally close to what they're hunting. **This is an existential design constraint, not a footnote.**

---

## Cross-niche monetization baseline

RPM = what *you* keep after YouTube's ~45% cut; CPM = what advertisers pay. Tier-1 audiences (US/UK/CA/AU) pay 5–8× tier-3 markets. ([vexub](https://vexub.com/blog/top-10-highest-rpm-youtube-niches), [Lenos](https://www.lenostube.com/en/youtube-cpm-rpm-rates/))

| Niche | Long-form RPM (US) | Shorts RPM (US) | Ad-buyer demand | Legal/policy risk |
|---|---|---|---|---|
| Finance / investing | $15–25, top tier to $29+ | ~$0.05–0.30 | Very high (fintech, banks, brokers) | High (YMYL) |
| Business / make-money | $18–35 RPM cited for "make money online" | ~$0.10–0.30 | High | Medium (FTC/get-rich-quick) |
| True Crime / legal | $8–12 (legal advice $15–28) | low + frequent demon. | Medium, ad-shy | High (graphic/defamation) |

Sources: [OutlierKit niches](https://outlierkit.com/blog/most-profitable-youtube-niches), [vidIQ](https://vidiq.com/blog/post/most-profitable-youtube-niches/), [vexub](https://vexub.com/blog/top-10-highest-rpm-youtube-niches), [Influencer Marketing Hub](https://influencermarketinghub.com/youtube-shorts-rpm/).

**Critical caveat for a Shorts-first pipeline:** Shorts RPM is 50–100× *lower* than long-form per view. YouTube's CEO stated in May 2025 that Shorts revenue per watch-hour now equals long-form in the US, but that is *per watch-hour*, not per view — Shorts are watched in seconds. ([Influencer Marketing Hub](https://influencermarketinghub.com/youtube-shorts-rpm/), [Vozo](https://www.vozo.ai/blogs/youtube/profitable-faceless-youtube-niches)) **Honest read: ad-share on Shorts alone, even in finance, is a volume-and-scale game. The realistic monetization path is Shorts as a top-of-funnel feeding long-form / cross-platform, not Shorts as the sole revenue source.**

---

## Niche deep-dive 1 — FINANCE

**Saturation & break-in.** Crowded at the top (Mark Tilbury, Graham Stephan-style explainers), but the niche is broad enough that micro-sub-niches (e.g., "ISA/401k mechanics," "one stat per day," "money psychology") still have room. A faceless channel *can* break in because finance rewards clarity over personality — narration-first explainers travel well without a face. ([Social Media Examiner](https://www.socialmediaexaminer.com/viral-short-form-video-formats-for-2025/), [Clipwise](https://www.clipwise.ai/blogs/50-profitable-faceless-youtube-channel-ideas-that-actually-work))

**Winning formats.**
- **Single-concept explainer** ("How compound interest actually works") — narration + animated chart + B-roll.
- **Data/chart reveal** — a surprising statistic animated on screen (e.g., "$100/mo from age 25 vs 35").
- **Myth-bust / "the bank doesn't want you to know"** framing (use carefully — see risk).
- **Listicle** ("3 accounts everyone should have") — proven viral formula (WatchMojo-style). ([Social Media Examiner](https://www.socialmediaexaminer.com/viral-short-form-video-formats-for-2025/))

**RPM by sub-niche.** Personal finance & investing is the single highest-RPM category on YouTube ($25–50 RPM long-form per some 2026 datasets; CPM $15–22). "Make money online" overlaps with business and is similarly premium. Budgeting/credit pulls slightly lower CPM than investing/wealth. ([vexub](https://vexub.com/blog/top-10-highest-rpm-youtube-niches), [OutlierKit finance](https://outlierkit.com/blog/youtube-rpm-finance-niche))

**Audience.** Skews working-age adults with disposable income / intent to invest — exactly why advertisers (brokers, fintech, banks) pay up. They engage with concrete, actionable, number-driven content and reject vague hype.

**Content sourcing (automation feasibility — strong).** Real market data is API-accessible: Financial Datasets (27,000+ tickers, 30+ yrs), Finnhub (free real-time tier), Twelve Data, EODHD (60+ exchanges), Financial Modeling Prep. ([Financial Datasets](https://www.financialdatasets.ai/), [Finnhub](https://finnhub.io/), [Twelve Data](https://twelvedata.com/stocks), [EODHD](https://eodhd.com/financial-apis/)) **Watch commercial-use terms** — most free tiers restrict commercial redistribution; budget for a paid tier or use clearly-licensed data. Charts can be generated programmatically (matplotlib/plotly) — fully license-clean, ideal for an automated pipeline.

**Niche risks.** Finance is **YMYL** ("Your Money or Your Life") — held to heightened E-E-A-T scrutiny by Google and watched by regulators. ([Search Engine Land YMYL](https://searchengineland.com/guide/ymyl), [Workshop Digital](https://www.workshopdigital.com/blog/why-ymyl-content-is-important/)) A "this is not financial advice" disclaimer is standard but does **not** fully insulate you — creators are not fiduciaries and speculative/tailored advice can create liability and conflict-of-interest exposure, especially if monetized. ([Wolfpack Wealth](https://www.wolfpackwealth.net/post/videos-social-media-posts-are-not-financial-advice), [Wolf Financial](https://wolf.financial/blog/youtube-compliance-rules-financial-services-marketing)) **Design rule: educational/general only, no specific buy/sell calls, no promises of returns, disclaimer on every video.**

---

## Niche deep-dive 2 — TRUE CRIME

**Saturation & break-in.** Demand is enormous and still rising — TikTok reported a ~250% YoY jump in true-crime hashtags (as of 2023) and #truecrime/#crimetok are massive. ([FluxNote](https://fluxnote.io/blog/best-ai-video-strategy-for-true-crime-creators-in-2026)) But this also means it is **intensely saturated and now flooded with AI true-crime generators** specifically marketed for faceless TikTok/Shorts output. ([revid.ai](https://www.revid.ai/tools/ai-true-crime-video-generator), [virvid](https://virvid.ai/ai-true-crime-tiktok-video-generator)) Break-in is possible on *underreported/forgotten cases* and strong narrative voice, but you are competing against a wall of identical AI dark-ambient clips — differentiation is hard.

**Winning formats.**
- **Case recap with cliffhanger structure** — narration over evocative (non-graphic) B-roll, dark ambient music.
- **"Unsolved / you've never heard of this case"** — curiosity-gap framing.
- **Timeline reveal** — facts dripped to keep an open loop.
- **Series/multi-part** to build a returning audience (true-crime fans binge — ~7 hrs/week with the genre). ([Sounds Profitable](https://soundsprofitable.com/article/the-truth-about-true-crime/))

**RPM.** Mid-tier: true-crime documentaries cited around $8–12 RPM, below finance/business; legal-advice-adjacent content is higher ($15–28). ([vexub](https://vexub.com/blog/top-10-highest-rpm-youtube-niches), [OutlierKit niches](https://outlierkit.com/blog/most-profitable-youtube-niches)) **The bigger problem is not the RPM ceiling — it's frequent demonetization dropping effective RPM toward zero.**

**Audience.** Skews strongly female (~62% of listeners; women ~2× as likely as men to follow true crime), concentrated 25–44, over-indexes among less-formally-educated and Hispanic/Black audiences, and is highly engaged/loyal. ([Pew Research](https://www.pewresearch.org/short-reads/2023/06/20/true-crime-podcasts-are-popular-in-the-us-particularly-among-women-and-those-with-less-formal-education/), [Rephonic](https://rephonic.com/blog/podcast-audience-gender-skew/), [Sounds Profitable](https://soundsprofitable.com/article/the-truth-about-true-crime/)) High loyalty = good retention/return rates, but a less premium ad audience than finance.

**Content sourcing (automation feasibility — mixed/risky).** Facts come from public record (court documents, police reports, news archives, Wikipedia). This is *available* but **dangerous to automate**: AI can fabricate or mis-attribute facts about real, often living, people. Visuals are the bind — actual crime-scene/victim imagery is both a copyright and an ad-policy minefield, so you must use abstract/atmospheric B-roll or licensed stock, never the real graphic material.

**Niche risks (the heaviest of the three).**
- **Demonetization:** Content where the focus is blood/violence/injury "without context" is not ad-suitable; news/educational/documentary *context* can earn limited ads, but enforcement is inconsistent and many true-crime creators report blanket demonetization. ([YouTube Ad Guidelines](https://support.google.com/youtube/answer/6162278?hl=en), [Change.org](https://www.change.org/p/youtube-stop-demonetizing-true-crime-content-on-youtube))
- **Graphic content rules:** No gore, crime-scene, or accident imagery where the focus is the violence/outcome. ([TubeBuddy](https://www.tubebuddy.com/blog/youtube-advertiser-friendly/))
- **Defamation / victims' families:** Naming real (especially living, or not-convicted) people with unverified claims is a real legal exposure, and there are strong ethical concerns about retraumatizing victims' families. For an *automated* pipeline that can hallucinate, this is the scariest combination.
- **Recommendation:** if pursued at all, restrict to **resolved, well-documented, historical cases**, mandatory human spot-audit of every script for factual/defamation review, no graphic visuals, and treat demonetization as the base case (lean on cross-platform/TikTok rather than YouTube ad-share).

---

## Niche deep-dive 3 — BUSINESS

**Saturation & break-in.** Crowded with "business model breakdown" and "marketing hack" content, but broad. Faceless works extremely well here (voiceover + motion graphics, no personality needed). ([Clipwise](https://www.clipwise.ai/blogs/50-profitable-faceless-youtube-channel-ideas-that-actually-work)) Break-in via specific, verifiable case studies rather than generic hustle advice.

**Winning formats.**
- **Business model breakdown** ("How [company] makes money") — narration + simple infographics.
- **Brand/company story** (rise, fall, pivot).
- **Listicle** ("Top 10 eCommerce trends 2026," "5 marketing hacks"). ([Social Media Examiner](https://www.socialmediaexaminer.com/viral-short-form-video-formats-for-2025/))
- **One-stat insight** — a striking business statistic with context.

**RPM.** Strong — "make money online & business" cited $18–35 RPM, digital marketing CPM $12–18. Among the most premium categories alongside finance because of the advertiser pool. ([vexub](https://vexub.com/blog/top-10-highest-rpm-youtube-niches), [vidIQ](https://vidiq.com/blog/post/most-profitable-youtube-niches/))

**Audience.** Entrepreneurs, professionals, aspirational earners — high purchasing intent, which is why CPMs are high. Engage with concrete numbers, named companies, and "how it actually works" framing; reject vague motivation.

**Content sourcing (automation feasibility — strong, safest).** Public case studies, company filings/annual reports, news, market reports. Charts/infographics generated programmatically. Lower factual-defamation risk than true crime (you're describing public companies and public business facts), and lower regulatory risk than finance — **this is the easiest niche to source cleanly for automation.**

**Niche risks.** **Accuracy** — wrong numbers about real companies erode trust fast and could draw complaints. **"Get-rich-quick" flag** — overpromising income ("make $10k/month doing X") triggers both viewer distrust and FTC-style scrutiny / advertiser-unfriendly labeling. Avoid earnings claims, hustle-bro hype, and unsubstantiated "secrets." ([YouTube Ad Guidelines](https://support.google.com/youtube/answer/6162278?hl=en))

---

## Cross-cutting content craft

### Hooks — the first 1–2 seconds
You have ~2 seconds before a swipe; the algorithm explicitly measures **intro retention** (% past the first ~3s), and strong creators hit 70%+. ([Aiken House](https://www.aikenhouse.com/post/viral-video-hooks-strategies-for-short-form-success), [Plang Phalla](https://plangphalla.com/the-first-3-seconds-that-decide-hook-science-for-reels-shorts-in-2025/)) The hook is *visual + text + audio combined*, not just the spoken line. ([JoinBrands hooks](https://joinbrands.com/blog/hooks-that-make-your-videos-go-viral/))

Proven patterns ([OpusClip](https://www.opus.pro/blog/tiktok-hook-formulas), [Aiken House](https://www.aikenhouse.com/post/viral-video-hooks-strategies-for-short-form-success)):
- **Curiosity gap / open loop:** "Nobody tells you this about your savings account…"
- **Pattern interrupt:** unexpected visual or motion in frame 1.
- **Bold claim / contrarian:** "Your credit score is lying to you."
- **Direct address + stakes:** "If you're under 30, this changes your retirement."
- **Number/data shock:** open on the surprising stat already on screen.
- Always **front-load the payoff tease in on-screen text** (most viewers are on mute).

### Retention tactics
- **Fast pacing + visual movement** throughout; no static frames. ([StackInfluence](https://stackinfluence.com/video-content-optimization-in-2025/))
- **Open loops** that resolve only at the end (especially true crime).
- **Pattern interrupts** every few seconds — cut, zoom, new graphic, sound change.
- **Captions are mandatory:** 85% of social video is watched on mute; captioned Shorts rank ~23% higher and are ~33% more relevant to silent viewers. ([Visla](https://www.visla.us/blog/listicles/video-marketing-trends-for-2026/), [CRKLR](https://crklr.com/news/how-to-optimise-youtube-shorts-for-seo/))
- **Deliver value continuously** — don't backload everything to the end.

### Length, cadence, timing
- **Length:** 40s+ Shorts are ~33% more engaging than very short ones; the project's 60–90s target is well-aligned, provided pacing holds retention. Optimize for watch-time *percentage* over raw length. ([Adobe Express](https://www.adobe.com/express/learn/blog/best-times-to-post-youtube-shorts), [Ordinal](https://www.tryordinal.com/blog/best-time-to-post-on-youtube-shorts))
- **Cadence:** sweet spot is **2–3 Shorts/day** at staggered times — more uploads = more algorithm test slots. ([Ventress](https://ventress.app/blog/youtube-posting-frequency-guide-2025/)) *(Reconcile with the project's phased-ramp safety net — start lower, ramp up.)*
- **Timing:** evenings 6–9pm and midday 12–3pm windows; weekends strong (some data shows ~60% more views, Saturday ~4pm peak). But the algorithm weights watch-time % far above timing. ([Buffer](https://buffer.com/resources/best-time-to-post-on-youtube/), [PostEverywhere](https://posteverywhere.ai/blog/best-time-to-schedule-youtube-shorts))

### Titles / thumbnails per platform
| Platform | Discovery model | Title/caption strategy | Thumbnail |
|---|---|---|---|
| YouTube Shorts | Search + feed (YouTube is search-driven) | Keyword-rich title; **hashtags in description (3–5), not title** | Custom thumbnail matters (esp. for the funnel to long-form) |
| TikTok | Algorithmic feed + growing search | Descriptive keyword caption + on-screen text; limited metadata | No real thumbnail control; first frame = the "cover" |
| Instagram Reels | Algorithmic feed + search | Keyword caption aligned with niche bio/name; hashtags | Choose a strong cover frame |
| Facebook Reels | Algorithmic feed | Similar to Reels; broader/older audience | Cover frame |

Sources: [StackInfluence](https://stackinfluence.com/video-content-optimization-in-2025/), [Hashtag Tools](https://hashtagtools.io/blog/youtube-shorts-hashtags-title-vs-description-2026), [Hike SEO](https://www.hikeseo.co/post/youtube-shorts-vs-tiktok), [Logie](https://logie.ai/news/reels-shorts-tiktok-search-are-the-new-seo-how-to-rank-in-2026/). **Implication for native per-platform renders:** YouTube needs the keyword title + description hashtags + thumbnail; TikTok/Reels need the value baked into on-screen text and the opening frame.

### The "AI slop" problem — the project's biggest risk
This is no longer a quality nicety; it's an enforcement and trust crisis:
- **YouTube wiped ~4.7B views off 16 AI-slop channels (35M subs)** and the CEO named "AI slop" as a 2026 enforcement target, building on July 2025's inauthentic/mass-produced content policy. ([OutlierKit AI Slop](https://outlierkit.com/resources/youtube-ai-slop-crackdown-2026/), [Search Engine Journal](https://www.searchenginejournal.com/youtubes-ai-slop-problem-and-how-marketers-can-compete/567297/), [MilX](https://milx.app/en/news/why-youtube-just-suspended-thousands-of-ai-channels-and-how-to-protect-yours))
- **TikTok mandates AI labels; Meta blocks monetization for repackaged content.** ([Wikipedia: AI slop](https://en.wikipedia.org/wiki/AI_slop))
- **Viewers detect & reject it:** generic robotic TTS, mismatched stock B-roll, no real insight, repetitive structure. Investigations found ~21% of Shorts served to fresh accounts were pure AI slop and ~40% of kids' recommendations appeared to be slop — fueling backlash. ([OutlierKit AI Slop](https://outlierkit.com/resources/youtube-ai-slop-crackdown-2026/))

**How this pipeline avoids being slop (mandatory design constraints):**
1. **Real, verified information** — genuine data/cases/case-studies, not generated filler. A fact the viewer couldn't get from a generic AI video is the moat.
2. **Quality TTS + human-grade scripts** — avoid the tell-tale robotic monotone; vary pacing.
3. **Coherent, relevant visuals** — charts tied to the actual numbers, not random stock.
4. **A consistent point of view / editorial voice per channel** — slop has none.
5. **Disclose AI use where required** (TikTok labels, C2PA provenance YouTube has joined) and lean into the project's **human spot-audit** safety net — this is exactly the defense against being swept up in mass-suspensions. ([MilX](https://milx.app/en/news/why-youtube-just-suspended-thousands-of-ai-channels-and-how-to-protect-yours))

### Short-form trends for 2026
- **AI fatigue → authenticity premium:** audiences crave "unmistakably real" content; raw/genuine beats polished-but-hollow. ([OpusClip 2026](https://www.opus.pro/blog/short-form-video-trends-reshaping-creator-marketing-2026), [Visla](https://www.visla.us/blog/listicles/video-marketing-trends-for-2026/))
- **Search-as-discovery:** Shorts/Reels/TikTok increasingly behave like search engines — keyword optimization matters more. ([Logie](https://logie.ai/news/reels-shorts-tiktok-search-are-the-new-seo-how-to-rank-in-2026/))
- **Captions are baseline**, not optional. ([Visla](https://www.visla.us/blog/listicles/video-marketing-trends-for-2026/))
- **Micro-niching + consistency** rewarded; micro-creators get higher engagement. ([Benchmark](https://www.benchmarkemail.com/blog/short-form-video-marketing-trends/))
- **Repurposing one core asset into many cuts** (5:3:1 ratio) — directly supports the project's multi-platform render model. ([Envato](https://elements.envato.com/learn/video-marketing-trends))
- **Slightly longer short-form** (40s–90s) gaining as platforms reward watch-time. ([Adobe Express](https://www.adobe.com/express/learn/blog/best-times-to-post-youtube-shorts))

---

## Recommendation for shorts-creator

1. **Lead with Business and Finance; treat True Crime as optional/high-caution.** Business is the cleanest to automate safely; Finance has the best money but needs strict YMYL discipline; True Crime carries demonetization + defamation risk that fights against full automation.
2. **Don't bank on Shorts ad-share alone** — design Shorts as a funnel into long-form / cross-platform reach.
3. **Treat anti-slop as a first-class requirement**: verified data, real editorial voice, quality TTS, coherent visuals, AI disclosure, and mandatory human spot-audit. This is the difference between this project earning revenue and being mass-suspended.

---

## Sources

- OutlierKit — Most Profitable YouTube Niches: https://outlierkit.com/blog/most-profitable-youtube-niches
- OutlierKit — Finance Niche RPM: https://outlierkit.com/blog/youtube-rpm-finance-niche
- OutlierKit — AI Slop Crackdown 2026: https://outlierkit.com/resources/youtube-ai-slop-crackdown-2026/
- vidIQ — Most Profitable YouTube Niches: https://vidiq.com/blog/post/most-profitable-youtube-niches/
- vexub — Top 10 Highest RPM Niches: https://vexub.com/blog/top-10-highest-rpm-youtube-niches
- Lenos — YouTube CPM & RPM Rates 2026: https://www.lenostube.com/en/youtube-cpm-rpm-rates/
- Influencer Marketing Hub — YouTube Shorts RPM: https://influencermarketinghub.com/youtube-shorts-rpm/
- Vozo — Profitable Faceless Niches: https://www.vozo.ai/blogs/youtube/profitable-faceless-youtube-niches
- FluxNote — AI Video Strategy for True Crime: https://fluxnote.io/blog/best-ai-video-strategy-for-true-crime-creators-in-2026
- revid.ai — AI True Crime Generator: https://www.revid.ai/tools/ai-true-crime-video-generator
- virvid — AI True Crime TikTok Generator: https://virvid.ai/ai-true-crime-tiktok-video-generator
- Pew Research — True Crime Podcast Demographics: https://www.pewresearch.org/short-reads/2023/06/20/true-crime-podcasts-are-popular-in-the-us-particularly-among-women-and-those-with-less-formal-education/
- Rephonic — Podcast Audience Gender Skew: https://rephonic.com/blog/podcast-audience-gender-skew/
- Sounds Profitable — Truth About True Crime: https://soundsprofitable.com/article/the-truth-about-true-crime/
- YouTube — Advertiser-Friendly Content Guidelines: https://support.google.com/youtube/answer/6162278?hl=en
- TubeBuddy — Advertiser-Friendly Tips: https://www.tubebuddy.com/blog/youtube-advertiser-friendly/
- Change.org — Stop Demonetizing True Crime: https://www.change.org/p/youtube-stop-demonetizing-true-crime-content-on-youtube
- Search Engine Land — YMYL Guide: https://searchengineland.com/guide/ymyl
- Workshop Digital — YMYL Finance/Healthcare: https://www.workshopdigital.com/blog/why-ymyl-content-is-important/
- Wolfpack Wealth — Not Financial Advice: https://www.wolfpackwealth.net/post/videos-social-media-posts-are-not-financial-advice
- Wolf Financial — YouTube Compliance for Financial Services: https://wolf.financial/blog/youtube-compliance-rules-financial-services-marketing
- Financial Datasets — Stock Market API: https://www.financialdatasets.ai/
- Finnhub — Stock APIs: https://finnhub.io/
- Twelve Data — Stock Market Data APIs: https://twelvedata.com/stocks
- EODHD — Financial APIs: https://eodhd.com/financial-apis/
- Social Media Examiner — Viral Short-Form Formats 2025: https://www.socialmediaexaminer.com/viral-short-form-video-formats-for-2025/
- Clipwise — Profitable Faceless Channel Ideas: https://www.clipwise.ai/blogs/50-profitable-faceless-youtube-channel-ideas-that-actually-work
- JoinBrands — Hooks That Go Viral: https://joinbrands.com/blog/hooks-that-make-your-videos-go-viral/
- OpusClip — TikTok Hook Formulas: https://www.opus.pro/blog/tiktok-hook-formulas
- OpusClip — Short-Form Trends 2026: https://www.opus.pro/blog/short-form-video-trends-reshaping-creator-marketing-2026
- Aiken House — Viral Video Hooks: https://www.aikenhouse.com/post/viral-video-hooks-strategies-for-short-form-success
- Plang Phalla — First 3 Seconds: https://plangphalla.com/the-first-3-seconds-that-decide-hook-science-for-reels-shorts-in-2025/
- StackInfluence — Video Content Optimization 2025: https://stackinfluence.com/video-content-optimization-in-2025/
- Buffer — Best Time to Post on YouTube: https://buffer.com/resources/best-time-to-post-on-youtube/
- Adobe Express — Best Times to Post Shorts: https://www.adobe.com/express/learn/blog/best-times-to-post-youtube-shorts
- PostEverywhere — Best Time to Schedule Shorts: https://posteverywhere.ai/blog/best-time-to-schedule-youtube-shorts
- Ordinal — Best Time to Post Shorts: https://www.tryordinal.com/blog/best-time-to-post-on-youtube-shorts
- Ventress — Posting Frequency Guide 2025: https://ventress.app/blog/youtube-posting-frequency-guide-2025/
- Hashtag Tools — Shorts Hashtags Title vs Description: https://hashtagtools.io/blog/youtube-shorts-hashtags-title-vs-description-2026
- Hike SEO — Shorts vs TikTok: https://www.hikeseo.co/post/youtube-shorts-vs-tiktok
- Logie — Reels/Shorts/TikTok Search SEO: https://logie.ai/news/reels-shorts-tiktok-search-are-the-new-seo-how-to-rank-in-2026/
- CRKLR — Optimise Shorts for SEO: https://crklr.com/news/how-to-optimise-youtube-shorts-for-seo/
- Search Engine Journal — YouTube AI Slop Problem: https://www.searchenginejournal.com/youtubes-ai-slop-problem-and-how-marketers-can-compete/567297/
- MilX — AI Slop / Channel Suspensions: https://milx.app/en/news/why-youtube-just-suspended-thousands-of-ai-channels-and-how-to-protect-yours
- Wikipedia — AI Slop: https://en.wikipedia.org/wiki/AI_slop
- Visla — Video Marketing Trends 2026: https://www.visla.us/blog/listicles/video-marketing-trends-for-2026/
- Benchmark — Short-Form Trends 2026: https://www.benchmarkemail.com/blog/short-form-video-marketing-trends/
- Envato Elements — Video Marketing Trends: https://elements.envato.com/learn/video-marketing-trends
