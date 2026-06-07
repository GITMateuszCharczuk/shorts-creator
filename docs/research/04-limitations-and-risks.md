# 04 — Limitations, Risks & Legal

> **Scope:** This is a skeptical risk register for `shorts-creator` — a free, self-hosted pipeline that **fully automatically generates AND posts** AI-narrated short-form video (60–90s) to YouTube Shorts, TikTok, Facebook Reels and Instagram Reels across three niches (Finance, True Crime, Business), via each platform's official posting API, aiming at ad-share revenue. Operated by a solo developer in "auto + safety-net" mode.
>
> **Bottom line up front:** The core product thesis — *fully-automated, AI-generated, multi-platform, multi-niche posting for ad revenue* — sits at the exact intersection of the things every major platform spent 2025 building enforcement machinery to suppress. Several risks below are not "if" but "when," and at least three are potentially **fatal to the project as specified**. Read the register, then the detail.

---

## Summary Risk Register

| # | Risk | Likelihood | Impact | Net |
|---|------|-----------|--------|-----|
| R1 | YouTube "inauthentic / mass-produced" demonetization (channel-wide) | **High** | **Severe** (kills primary revenue) | 🔴 |
| R2 | Platform ToS / API does not permit unattended bot posting → API access revoked or account banned | **Med–High** | **Severe** | 🔴 |
| R3 | True-crime defamation / privacy liability (real people, real cases) | **Med** | **Catastrophic** (6–7 figure judgment) | 🔴 |
| R4 | TikTok "unoriginal content" + duplicate cross-post penalties (Sep 15 2025 rule) | **High** | **High** (reach throttled, points, demonetized) | 🟠 |
| R5 | Meta unoriginal-content demonetization + 2025 ban-wave exposure | **High** | **High** | 🟠 |
| R6 | AI-disclosure / labeling non-compliance → strikes / removal | **Med** | **Med–High** | 🟠 |
| R7 | Finance niche = YMYL + securities/finfluencer regulation (disclaimers do **not** shield) | **Med** | **High** | 🟠 |
| R8 | Business niche = FTC deceptive earnings / get-rich-quick claims | **Low–Med** | **High** | 🟠 |
| R9 | Music / stock / AI-output licensing — Content ID claims, no copyright in AI output | **Med** | **Med** | 🟡 |
| R10 | API quota ceilings throttle throughput (YouTube = ~6 uploads/day default) | **High** | **Med** | 🟡 |
| R11 | Single 16 GB GPU compute ceiling / quality ceiling of free AI | **High** | **Med** | 🟡 |
| R12 | Economic: months of zero revenue, never crossing monetization thresholds | **High** | **High** | 🟠 |
| R13 | Operational: solo maintainer, channel ban = total loss of that asset | **Med** | **High** | 🟠 |
| R14 | Multi-account / multi-channel behavior flagged as coordinated/bot | **Med** | **High** | 🟠 |

🔴 = potentially project-fatal · 🟠 = serious · 🟡 = manageable

---

## Platform Policy Risks

### R1 — YouTube "inauthentic / mass-produced content" demonetization
**Likelihood: High · Impact: Severe**

On **15 July 2025** YouTube updated its YouTube Partner Program rules, renaming the old "repetitious content" policy to **"inauthentic content"** to explicitly cover **mass-produced and repetitive** videos — "content that looks like it's made with a template with little to no variation across videos, or content that's easily replicable at scale" ([Social Media Today](https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/); [YouTube Help](https://support.google.com/youtube/answer/1311392?hl=en)). A templated, fully-automated pipeline producing many near-identical AI-narrated clips is a textbook target. YouTube says AI-*assisted* content remains monetizable, but "fully automated, repetitive videos that offer no unique perspective may be demonetized" ([Fliki](https://fliki.ai/blog/youtube-monetization-policy-2025)).

This is the single most dangerous policy risk because demonetization is assessed **at the channel level** and YPP is the primary revenue source. A precedent already exists: in Feb 2025 YouTube **terminated** the "True Crime Case Files" channel — millions of views — for AI-fabricated stories ([Tubefilter](https://www.tubefilter.com/2025/02/14/youtube-true-crime-case-files-ai-crime-channel-terminated/)).

**Mitigation:** Force genuine per-video variation (unique scripts, structure, original angle/commentary, real research). Add a clear human-perceptible editorial perspective. Treat AI as a *production aid*, not the author. Keep volume modest per channel; do not template visibly. Accept that this risk can never be fully eliminated for an auto-generation product — it is structural.

### R4 — TikTok unoriginal / duplicate-content penalties
**Likelihood: High · Impact: High**

From **15 September 2025** TikTok stepped up enforcement against **Unoriginal Content**, with penalties including **violation points, commission freezes, and reduced visibility** ([BigSeller](https://www.bigseller.com/blog/articleDetails/3778/tiktok-unoriginal-content.htm)). TikTok's definition explicitly captures "pseudo-original" content — superficial edits (cropping, mirroring, watermarks, minor edits) over an unchanged core ([Napolify](https://napolify.com/blogs/news/tiktok-duplicate-penalty)). Crucially for a multi-platform poster: **a visible watermark or logo means content "does not count as original"** ([TikTok Creator Academy](https://www.tiktok.com/creator-academy/article/tiktok-originality-policy)). Cross-posting the same video to TikTok that carries a YouTube/Meta watermark is a direct hit.

**Mitigation:** Never cross-post the identical render; generate platform-specific cuts. Strip all watermarks/source logos before TikTok upload. Vary hooks, framing and captions per platform. Stagger posting.

### R5 — Meta (Facebook/Instagram) unoriginal-content crackdown
**Likelihood: High · Impact: High**

Effective **15 July 2025**, Meta announced reduced distribution and monetization exclusion for accounts that "improperly reuse someone else's videos, photos or text posts repeatedly," and for low-effort/AI-generated reposts with little transformation ([TechCrunch](https://techcrunch.com/2025/07/14/following-youtube-meta-announces-crackdown-on-unoriginal-facebook-content/); [Plagiarism Today](https://www.plagiarismtoday.com/2025/07/16/facebook-to-fight-unoriginal-content/)). Penalties: exclusion from in-stream ads, bonuses, Reels Play, plus **reduced distribution on everything shared** ([RouteNote](https://routenote.com/blog/meta-cracks-down-on-unoriginal-content/)). In H1 2025 Meta actioned **500,000+ accounts** for spammy behavior ([RouteNote](https://routenote.com/blog/meta-cracks-down-on-unoriginal-content/)).

**Mitigation:** Same as R4 — originality, transformation, no recycled stock/AI loops, platform-unique edits. Note Reels publishing via API requires an **Instagram Business** account (Creator accounts are not supported for content publishing) ([Meta Docs](https://developers.facebook.com/docs/instagram-platform/content-publishing/)).

### R6 — AI disclosure / labeling requirements
**Likelihood: Med · Impact: Med–High**

- **YouTube:** must label "realistic altered or synthetic content" that could mislead viewers; enforced from early 2025 ([Subscribr](https://subscribr.ai/p/youtube-ai-disclosure-rules)).
- **TikTok:** mandatory AI-generated label; integrated **C2PA Content Credentials in Jan 2025** to auto-detect and label AI content; reportedly issues **immediate strikes (not warnings)** for unlabeled AI content and removed 51,618 synthetic videos in H2 2025 ([Influencer Marketing Hub](https://influencermarketinghub.com/ai-disclosure-rules/)).
- **Meta:** auto-labels C2PA-tagged AI media across IG/FB ([Influencer Marketing Hub](https://influencermarketinghub.com/ai-disclosure-rules/)).
- **EU AI Act (Reg. 2024/1689):** mandatory disclosure of AI-generated content enforced from **2 Aug 2026** ([Influencer Marketing Hub](https://influencermarketinghub.com/ai-disclosure-rules/)).

Because TikTok can auto-detect via embedded credentials and strikes immediately, *failing* to self-label is riskier than labeling. The secondary risk is **audience backlash** — disclosed AI content (especially AI narration over stock) underperforms and erodes trust in the YMYL niches.

**Mitigation:** Auto-apply the AI-content flag in every API publish call on every platform; embed C2PA where tooling allows; treat disclosure as non-negotiable default-on.

---

## Automation / ToS Risks — CRITICAL

### R2 — Does each platform's ToS actually allow fully-automated, unattended bot posting?
**Likelihood: Med–High · Impact: Severe**

This is the make-or-break question. Official posting APIs exist on all four platforms, but each comes with approval gates, audits and ToS conditions that an unattended bot can violate:

- **YouTube Data API v3 (`videos.insert`):** technically supports automated upload. But the default project quota is **10,000 units/day** and an upload costs **1,600 units** — i.e. **~6 uploads/day max** by default ([Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost); [Phyllo](https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota)). Quota increases require an application asserting ToS compliance, and "any hint of abuse or terms violations" leads to automatic denial; Google may revoke quota at any time for non-compliance ([labnol](https://www.labnol.org/youtube-quota-request-201016)). Mass-automated upload of templated content is exactly what triggers denial/revocation.

- **TikTok Content Posting API:** requires app approval for the `video.publish` scope via **manual review (typically 2–6 weeks)**; **unaudited** clients can only post in **SELF_ONLY (private)** mode and to ≤5 users / 24h. To make posts public, the app must pass an **audit verifying ToS compliance** ([TikTok Dev Get Started](https://developers.tiktok.com/doc/content-posting-api-get-started); [zernio](https://zernio.com/blog/tiktok-posting-api)). Direct Post does support scheduled/unattended publishing — but only after audit, and the audit scrutinizes exactly the kind of automation this project does.

- **Meta Graph API (Reels):** publishing capped at roughly **25–100 API posts / rolling 24h per IG account** (Reels/Stories share the bucket); requires an Instagram **Business** account and `instagram_business_content_publish` (scopes changed Jan 27 2025) ([CreatorFlow](https://creatorflow.so/blog/instagram-api-rate-limits-explained/); [Meta Docs](https://developers.facebook.com/docs/instagram-platform/content-publishing/)). Meta App Review approves the use-case; behavior inconsistent with the declared use-case risks app/account action.

The honest assessment: the **official APIs permit programmatic posting**, but none of them were designed to bless *unattended, fully-autonomous, mass content generation* — and all four spent 2025 tightening exactly against it. Approval is conditional and revocable; the audit/review step is a gate the project may simply fail. Operating outside the official APIs (scraping/headless automation) is a flat ToS violation and a fast path to ban.

**Mitigation:** Use **only** official APIs; never headless/unofficial automation. Pass the TikTok audit and Meta App Review honestly (declare the real use-case). Keep volumes far below quota ceilings. Keep a human in the loop at the publish step during ramp (the "safety-net" gate) so behavior does not look purely robotic. Assume API access can be pulled and design so it is not a single point of failure.

### R14 — Multi-account / coordinated-behavior flags
**Likelihood: Med · Impact: High**

Three niches × four platforms = up to 12 accounts driven from one machine/IP. Platforms flag **multiple accounts from one IP**, identical posting cadence, and bot-like timing ([multilogin](https://multilogin.com/blog/tiktok-account-suspended/)). Instagram "actively scans for automation signatures," and a large **2025 ban wave (May–Aug)** swept up many accounts via automated moderation ([antiban.pro](https://medium.com/@antiban.pro/instagram-ban-wave-2025-causes-ai-moderation-errors-and-how-to-recover-your-account-9639a063c9c2)).

**Mitigation:** One business identity per channel where allowed; avoid sharing IPs/fingerprints across accounts in ways that read as a click-farm; randomize/stagger cadence; warm accounts slowly (phased ramp). Do not chase volume.

---

## Legal Risks

### R3 — True Crime: defamation, privacy, real people
**Likelihood: Med · Impact: Catastrophic**

This is the highest-*severity* legal exposure. In **May 2026** a Nashville YouTuber was hit with a **$17.5M defamation verdict** over a true-crime video about the Kiely Rodni case — jurors found statements provably false and damaging to the family ([WHSV](https://www.whsv.com/2026/05/19/youtuber-hit-with-175m-verdict-defamation-case-over-kiely-rodni-true-crime-video/)). Other channels have faced defamation/harassment claims from victims' families ([WSMV](https://www.wsmv.com/2023/09/29/nashville-youtuber-sued-defamation-over-true-crime-video/)). An **AI** pipeline writing scripts about **real, named people and real crimes**, with no human fact-check, is uniquely dangerous: AI hallucination → false factual assertions → defamation per se. YouTube terminated an AI true-crime channel for fabricated content ([Tubefilter](https://www.tubefilter.com/2025/02/14/youtube-true-crime-case-files-ai-crime-channel-terminated/)). Platform liability shields (Section 230) protect the *platform*, not the *creator*.

**Mitigation (do not skip any):** Mandatory human legal/fact review before *every* true-crime publish — this niche cannot run unattended. Cover only adjudicated/public-record facts; avoid naming uncharged/acquitted individuals; never accuse of crimes not convicted; respect victims' families and privacy; avoid graphic/violent content (also a demonetization trigger). Strongly consider **dropping or radically de-risking the True Crime niche** — the asymmetry (pennies of revenue vs. seven-figure liability) is the worst in the project. Carry media-liability insurance if proceeding.

### R7 — Finance: YMYL + securities / finfluencer regulation
**Likelihood: Med · Impact: High**

Finance is classified **YMYL** and draws enhanced scrutiny. Critically: **"This is not financial advice" disclaimers do NOT shield you** — regulators (SEC/FINRA/FCA) look at the substance of the activity, not the label, and you "cannot contract out of securities licensing laws" ([wolf.financial](https://wolf.financial/blog/youtube-compliance-rules-financial-services-marketing); [Securities Lawyer 101](https://www.securitieslawyer101.com/2025/regulation-of-financial-influencers/)). In 2025 the SEC signaled crypto influencers giving personalized advice must register as advisers; FINRA settled finfluencer actions over unbalanced/exaggerated posts; the FCA ran a 2025 enforcement week with arrests ([sources above](https://www.securitieslawyer101.com/2025/regulation-of-financial-influencers/)). AI-generated finance content risks giving specific, unsubstantiated, or misleading recommendations at scale.

**Mitigation:** Keep content strictly **educational/general**, never personalized recommendations or specific buy/sell/price calls. Human review of factual/numerical claims. Avoid crypto "alpha." Include disclaimers *and* — more importantly — keep the substance non-advisory. Avoid touting specific securities.

### R8 — Business: FTC deceptive earnings / get-rich-quick
**Likelihood: Low–Med · Impact: High**

In Jan 2025 the FTC proposed an **Earnings Claim Rule** and Business Opportunity Rule changes enabling **civil penalties + consumer refunds** for deceptive money-making/earnings claims, requiring **written substantiation** for any earnings claim ([FTC](https://www.ftc.gov/news-events/news/press-releases/2025/01/ftc-proposes-rule-changes-new-rule-deter-deceptive-earnings-claims-multilevel-marketers-money-making)). The FTC actively refunds victims of bogus "get-rich-quick kits" ([FTC](https://www.ftc.gov/news-events/news/press-releases/2025/06/ftc-sends-more-2-million-consumers-harmed-scammers-pitching-bogus-money-making-coaching-programs)). AI "business" content that implies easy income is squarely in scope.

**Mitigation:** No income/earnings promises, no "get rich quick" framing, no selling courses/coaching off the back of claims. If any earnings figure appears, hold substantiation. Keep content informational.

### R9 — Copyright / licensing of music, stock & AI outputs
**Likelihood: Med · Impact: Med**

- **AI output has no copyright protection:** the US Copyright Office (Jan 29 2025 report) held that purely prompt-generated output is **not copyrightable**; protection needs material human creative contribution ([Copyright Office](https://www.copyright.gov/ai/); [Barnes & Thornburg](https://btlaw.com/en/insights/alerts/2025/copyright-office-says-ai-generated-works-based-on-text-prompts-are-not-protected)). Consequence: the project **cannot assert exclusive rights** in its AI-generated visuals/audio — others may freely copy them, undermining any moat and complicating Content ID claims.
- **AI music / training-data risk:** YouTube began retroactively enforcing stricter copyright verification in 2025; AI models can reproduce training-data melodies, triggering Content ID claims/takedowns/demonetization. "Stock loops + stock AI music is the fastest path to demonetization" ([Outlierkit](https://outlierkit.com/resources/ai-generated-music-youtube-monetization-2026/); [Miraflow](https://miraflow.ai/blog/can-you-monetize-videos-ai-music-2026)).
- **Stock licensing:** "royalty-free" ≠ "free for commercial/monetized use" — license terms vary and many free assets exclude monetization or require attribution.

**Mitigation:** Use only assets with explicit **commercial monetization rights**; keep license records per asset. Run every track through YouTube's copyright checker pre-publish. Prefer licensed/PRO-cleared or genuinely original music. Accept that AI visuals are unprotectable and design around it.

---

## Technical Limitations

### R11 — Single 16 GB GPU + quality ceiling
**Likelihood: High · Impact: Med**

A single 16 GB GPU caps which local models run (larger video/diffusion and TTS models may not fit or run slowly), limiting **throughput** and **quality**. Current free/open AI video and voice quality is below the bar audiences and YouTube's "inauthentic" filter now expect — generic AI narration over stock footage is precisely what R1/R4/R5 penalize. VRAM contention means generation is serialized, bounding daily output well below platform quotas anyway.

**Mitigation:** Build a robust QC gate that **quarantines** low-quality/failed renders before publish (the "auto + safety-net" design). Batch overnight; cache; use efficient/quantized models. Set realistic per-day output (a handful of strong videos > many weak ones — which is also the R1 mitigation). Plan a graceful upgrade path if revenue ever justifies a bigger GPU or paid API.

### R10 — API quota / throughput ceilings (already detailed in R2)
**Likelihood: High · Impact: Med**

Recap: YouTube ~6 uploads/day default; IG ~25–100/day; TikTok audit-gated. These ceilings, plus GPU limits, mean the pipeline is **throughput-bound at the low end** — which is good for R1/R4/R5 but bad for the "scale to revenue" thesis.

---

## Economic Risks

### R12 — Low/zero revenue for months; threshold and algorithm dependency
**Likelihood: High · Impact: High**

- **Monetization thresholds:** YouTube Partner Program needs **1,000 subscribers + 4,000 watch hours (or 10M Shorts views/90 days)**; a new channel typically takes **6–18 months** to hit 1,000 subs ([YouTube Help](https://support.google.com/youtube/answer/72851?hl=en); [StudioBinder](https://www.studiobinder.com/blog/youtube-monetization-requirements/)). So **zero ad revenue for many months** is the *expected* case, not the worst case.
- **Shorts RPM is tiny:** **$0.01–$0.07 per 1,000 views**; at a mid $0.04 RPM you need **~2.5M Shorts views/month to earn ~$100** ([Mediacube](https://mediacube.io/en-US/blog/youtube-shorts-rpm); [Miraflow](https://miraflow.ai/blog/youtube-shorts-rpm-2026-real-ranges-by-niche)). Finance RPM runs higher, comedy/lifestyle lower.
- **Single-point-of-failure on policy:** revenue depends entirely on platform algorithms and monetization policy, which (see R1, R4, R5) changed adversely **three times in mid-2025 alone**. A single policy update can zero the income overnight.

**Mitigation:** Treat revenue as a **long-shot, long-horizon** outcome; do not fund the project on expected income. Diversify across platforms and niches (already planned) to avoid one-policy wipeout. Track cost-to-run vs. revenue honestly; have a kill criterion (e.g., if no channel monetizes within N months, stop). Lean into Finance's higher RPM where legally safe.

---

## Operational Risks

### R13 — Solo maintainer; channel ban = asset loss
**Likelihood: Med · Impact: High**

A solo developer is a single point of failure for maintenance, monitoring, the weekly human spot-audit, the true-crime legal review (R3) and finance review (R7). If a channel is **banned/terminated** (plausible per R1, R2, R3, R5, R14), that account, its subscriber base, watch-hours and monetization status are typically **lost permanently** — and bans can cascade to linked Google/Meta accounts. Recovery/appeals are slow and often fail.

**Mitigation:** Separate, isolated identities per platform/niche so one ban doesn't sink the others. Keep local backups of all content and metadata so a banned channel can be partially reconstituted elsewhere. Document runbooks so the "safety-net" audits actually happen on schedule. Phased ramp (start tiny, prove compliance, expand) limits blast radius. Define explicit incident handling: on suspension, halt automation, audit, appeal, and do not spin up evasion accounts (which deepens R14).

---

## Synthesis — the three risks that should change the design

1. **R1 + R2 together (platform demonetization + ToS/API automation gate)** are the project's central existential tension: the product *is* "mass-produced AI content posted by a bot," and that is precisely what every platform's 2025 enforcement was built to catch. The "auto + safety-net" model with genuine per-video originality and human-in-the-loop publishing during ramp is the only credible path — and even then, success is not assured.
2. **R3 (True Crime defamation)** is catastrophically asymmetric — a single $17.5M-style verdict dwarfs any conceivable ad revenue, and AI scripting about real people maximizes the hazard. **Recommend dropping or heavily gating this niche.**
3. **R12 (economics)** means the realistic baseline is *months of zero revenue and pennies-per-thousand-views thereafter*, fully dependent on volatile platform policy. The project should be justified as a learning/portfolio exercise, not an income plan.

---

## Sources

- YouTube channel monetization policies — https://support.google.com/youtube/answer/1311392?hl=en
- YouTube Clarifies Changes to Monetization Rules (inauthentic content) — https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/
- YouTube Monetization Policy Update July 2025 (Fliki) — https://fliki.ai/blog/youtube-monetization-policy-2025
- YouTube Partner Program eligibility — https://support.google.com/youtube/answer/72851?hl=en
- YouTube monetization requirements 2026 (StudioBinder) — https://www.studiobinder.com/blog/youtube-monetization-requirements/
- YouTube Shorts RPM 2026 (Mediacube) — https://mediacube.io/en-US/blog/youtube-shorts-rpm
- YouTube Shorts RPM ranges (Miraflow) — https://miraflow.ai/blog/youtube-shorts-rpm-2026-real-ranges-by-niche
- YouTube Data API quota calculator — https://developers.google.com/youtube/v3/determine_quota_cost
- YouTube API limits & quota (Phyllo) — https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota
- Requesting YouTube API quota increase (labnol) — https://www.labnol.org/youtube-quota-request-201016
- TikTok Content Posting API — Get Started — https://developers.tiktok.com/doc/content-posting-api-get-started
- TikTok posting API limits & audit (zernio) — https://zernio.com/blog/tiktok-posting-api
- TikTok duplicate-content penalty (Napolify) — https://napolify.com/blogs/news/tiktok-duplicate-penalty
- TikTok unoriginal content enforcement Sep 15 2025 (BigSeller) — https://www.bigseller.com/blog/articleDetails/3778/tiktok-unoriginal-content.htm
- TikTok Originality Policy (Creator Academy) — https://www.tiktok.com/creator-academy/article/tiktok-originality-policy
- Meta Graph API content publishing docs — https://developers.facebook.com/docs/instagram-platform/content-publishing/
- Instagram API rate limits (CreatorFlow) — https://creatorflow.so/blog/instagram-api-rate-limits-explained/
- Meta unoriginal content crackdown (TechCrunch) — https://techcrunch.com/2025/07/14/following-youtube-meta-announces-crackdown-on-unoriginal-facebook-content/
- Meta cracks down on unoriginal content (RouteNote) — https://routenote.com/blog/meta-cracks-down-on-unoriginal-content/
- Facebook to fight unoriginal content (Plagiarism Today) — https://www.plagiarismtoday.com/2025/07/16/facebook-to-fight-unoriginal-content/
- AI disclosure rules by platform (Influencer Marketing Hub) — https://influencermarketinghub.com/ai-disclosure-rules/
- YouTube AI disclosure rules (Subscribr) — https://subscribr.ai/p/youtube-ai-disclosure-rules
- AI true-crime channel terminated (Tubefilter) — https://www.tubefilter.com/2025/02/14/youtube-true-crime-case-files-ai-crime-channel-terminated/
- $17.5M true-crime defamation verdict (WHSV) — https://www.whsv.com/2026/05/19/youtuber-hit-with-175m-verdict-defamation-case-over-kiely-rodni-true-crime-video/
- Nashville YouTuber sued for defamation (WSMV) — https://www.wsmv.com/2023/09/29/nashville-youtuber-sued-defamation-over-true-crime-video/
- Finfluencer / securities regulation 2025 — https://www.securitieslawyer101.com/2025/regulation-of-financial-influencers/
- YouTube compliance for financial services (wolf.financial) — https://wolf.financial/blog/youtube-compliance-rules-financial-services-marketing
- SEC finfluencer recommendation — https://www.sec.gov/files/sec-iac-finfluencer-recommendation-11222024.pdf
- FTC proposes deceptive earnings claim rules (Jan 2025) — https://www.ftc.gov/news-events/news/press-releases/2025/01/ftc-proposes-rule-changes-new-rule-deter-deceptive-earnings-claims-multilevel-marketers-money-making
- FTC refunds to get-rich-quick scam victims — https://www.ftc.gov/news-events/news/press-releases/2025/06/ftc-sends-more-2-million-consumers-harmed-scammers-pitching-bogus-money-making-coaching-programs
- US Copyright Office — Copyright and AI — https://www.copyright.gov/ai/
- Copyright Office: AI prompt-based works not protected (Barnes & Thornburg) — https://btlaw.com/en/insights/alerts/2025/copyright-office-says-ai-generated-works-based-on-text-prompts-are-not-protected
- AI music monetization (Outlierkit) — https://outlierkit.com/resources/ai-generated-music-youtube-monetization-2026/
- Monetizing AI music videos (Miraflow) — https://miraflow.ai/blog/can-you-monetize-videos-ai-music-2026
- Instagram 2025 ban wave (antiban.pro) — https://medium.com/@antiban.pro/instagram-ban-wave-2025-causes-ai-moderation-errors-and-how-to-recover-your-account-9639a063c9c2
- TikTok account suspension guide (multilogin) — https://multilogin.com/blog/tiktok-account-suspended/
