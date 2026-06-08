# ADR 0004 — PoC commercial posture & account-safety

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0001](0001-lightened-runtime-architecture.md),
  [ADR 0002](0002-recency-and-novelty-ledger.md),
  [ADR 0003](0003-resilience-concurrency-observability.md).
- **Touches:** spec Ch.1 (DoD), Ch.2 (scope), Ch.4 (`05b`, `06`, `script.json`), Ch.5
  (contracts), Ch.8 (QC gate + human gate), Ch.9 (posting posture).
- **Origin:** the business lens of the five-specialist review, plus an explicit owner decision
  to add an always-on automated account-safety gate.

## Context

The review's business critique was that the system is engineered well enough to reach "done"
while validating nothing **commercial**, and that fully-unattended publishing of **YMYL**
(finance/business) content is the riskiest possible posture for **account survival** — the
research explicitly recommended a human at the *publish* step during ramp, and platform
enforcement (demonetization / termination) plays out over weeks at volume, often irreversibly.
The owner reviewed four proposed posture changes and an additional account-safety idea, and
accepted all of them.

## Decision

1. **Reframe the definition of done (documentation-only).** The DoD proves the **engineering
   loop** — unattended, quality-bar, real-posting, 1–2 week stability. It **deliberately does
   not validate commercial viability** (reach, retention, revenue). "Done" must not be read as
   "this makes money."

2. **Human-at-publish during the ramp.** During the **initial ramp only**, a person approves
   each video before Stage `06` posts — *in addition to* the automated gate. The fully
   **unattended 1–2 week run happens after** the ramp, once the automated gate (Decision 3) and
   a track record have earned the removal of the human. This protects the accounts the project
   spends weeks building.

3. **An always-on automated account-safety gate (hardens Stage `05b`).** Stage `05b` is
   strengthened from a generic QC pass into an explicit **takedown/demonetization-risk filter**
   that runs on **every** video, **including after** the human gate is removed. It blocks
   (→ quarantine) unless **all** hold: YMYL "educational, not financial advice" **disclaimer
   present**; **no buy/sell/price calls or guaranteed-return claims**; **sources cited**;
   **AI-content disclosure flag set**; profanity/unsafe-claims clear; and a **repetitious-content
   check** against the novelty ledger. This is the **durable** account protection; the
   ramp-only human gate is belt-and-suspenders on top of it.

4. **At least one genuinely public account per platform.** Alongside the private-first accounts,
   run **≥1 public** account per platform so the PoC earns a **minimum reach/retention signal**
   instead of zero. Public posting is gated by Decisions 2 + 3 and, where required (YouTube),
   the compliance audit; TikTok public stays within unaudited limits (`SELF_ONLY`/cap) until its
   audit clears. The `public`/`private` choice remains a single per-platform config flag
   (ADR 0001 / Ch.9).

5. **Design affiliate in now (dormant-capable).** `script.json` gains optional affiliate
   field(s) — link, CTA copy, and a required disclosure line — that Stage `06` emits into the
   description when enabled. It may ship **disabled**, but is architected now so the
   best-return/effort revenue lever needs no contract retrofit later.

## Consequences

**Positive**
- The PoC now produces a real-world signal (public accounts) without betting the accounts on
  unsupervised YMYL posting (human ramp + always-on safety gate).
- Account-survival risk is mitigated by a *durable* automated control, not just a temporary
  human one.
- The top near-term monetization path is built into the contract at near-zero cost.

**Negative / costs**
- The ramp is **not** fully unattended — accepted; the unattended-run DoD is satisfied *after*
  the ramp.
- Public posting raises policy exposure — the reason Decisions 2 + 3 gate it.
- A small amount of contract/QC design work now (affiliate fields, the strengthened gate's
  checks).

## Open (tracked)

- **Ramp exit criteria** — how many clean human-approved batches before the human gate is removed.
- **Numeric QC thresholds** for the safety gate (shared open item with ADR 0003).
- How many public vs private accounts, and per-niche.
- Affiliate program selection + per-niche disclosure wording (kept disabled until decided).
