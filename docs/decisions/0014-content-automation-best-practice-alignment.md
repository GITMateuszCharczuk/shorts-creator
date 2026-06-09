# ADR 0014 — Content-automation best-practice & 2026 policy alignment

- **Status:** Accepted (2026-06-09)
- **Builds on:** [ADR 0004](0004-poc-commercial-posture-and-account-safety.md) (account safety /
  posture), [ADR 0005](0005-editorial-quality-layer.md) (the QC gates + treatment + persona),
  [ADR 0006](0006-algorithm-fit-and-format-tuning.md) (algorithm-fit / cadence),
  [ADR 0008](0008-output-parity-hardening.md) (honest ceilings).
- **Touches:** spec Ch.1 (DoD clause 2 + honest ceilings), Ch.2 (cadence), Ch.4 (00b, 05c, 06),
  Ch.6 (posting schedule), Ch.10.
- **Origin:** a best-practice audit of the design against **current (June 2026)** content-automation
  practice and, critically, the **2026 platform-enforcement climate**. The design already implements
  most short-form craft best practices by name (ADRs 0005/0006/0008); this ADR records the three
  gaps the audit found and folds the fixes in.

## Context

The audit confirmed the pipeline matches established best practice on hook-first design, completion/
loop optimization, two-lane length, designed captions + safe zones, audio craft, keyword threading,
save/share CTAs, real-footage-first visuals, per-platform native cuts, the dual QC gates, account
warming, and persona/voice. Three things were **under-weighted or missing** relative to 2026 norms:

1. **The "inauthentic / mass-produced content" enforcement risk has become existential, and the
   design treats its defenses as craft rather than survival.** YouTube renamed its "repetitious
   content" policy to **"inauthentic content"** (2025-07-15) to explicitly cover *mass-produced* and
   *repetitive* output, and in **January 2026 ran its largest enforcement wave to date — 16 channels
   terminated (~4.7B lifetime views, ~35M subscribers, ~$10M/yr ad revenue erased).** The named
   trigger profile: AI content built from **generic templates** that gives "the impression of mass
   production **without adding original insight or perspective**," frequently at high upload volume.
   Our profile (faceless + AI + template-rotated + 2–4/day) is adjacent to that profile. ADR 0005 D9
   already flagged content-farm voice-uniformity as a YouTube risk; the 2026 data sharpens it from a
   stylistic concern into a **monetization-survival requirement**, and reveals that `05c` as specced
   (hook strength / coherence / payoff) does **not** explicitly test the dimension YouTube enforces
   on: *original, authentic insight*. A correct-but-generic market summary passes our gate and fails
   the policy.

2. **No posting-time / scheduled-publish lever.** ADR 0006 D3 notes first-hours engagement velocity
   is a ranking signal, but the pipeline posts whenever the overnight batch finishes — leaving a free
   reach lever (publishing into a per-platform peak-audience window) unused.

3. **Community / early-engagement velocity is structurally unaddressed and unrecorded.** A faceless,
   unattended pipeline cannot reply to comments — a real contributor to the first-hours velocity
   ADR 0006 itself weights. This belongs in the honest-ceiling ledger (ADR 0008 D4) rather than being
   silently absent.

*(TikTok's 2026 rules were also reviewed: AI **script/hook/caption/overlay** assistance is exempt
from the synthetic-media label; the label is required for AI that produces **realistic depictions of
real people/places/events** — so our FLUX photoreal stills are the genuine trigger, while TTS +
charts + licensed stock may be exempt. Unlabeled-but-caught content suffers ~73% reach suppression;
proper labeling costs ~5–8% reach with zero account risk. Our blanket "disclose on every call"
(ADR 0004/0009) is therefore the **safe** choice and is **kept unchanged** for unattended ops; a
later phase may disclose more granularly to recover the 5–8%. No decision needed now.)*

## Decision

1. **`05c` gains an enforceable "original insight / authentic perspective" criterion, and the DoD
   makes it explicit (amends ADR 0005 D2 + spec Ch.1 clause 2).** The creative-QC rubric adds a
   first-class criterion — *"does this say something non-obvious, with a specific point of view, that
   a generic template fill would not?"* — scored against a floor, **fed by the treatment's thesis +
   the persona** (ADR 0005 D1/D9) so it judges perspective, not just polish. Below floor →
   **quarantine, not post**, exactly like the other criteria. The DoD's "genuinely good, not AI slop"
   clause is reworded to name **original insight** as part of the enforced bar, because under the 2026
   inauthentic-content policy this is a **monetization-survival** property, not an aesthetic one.

2. **Cadence is enforcement-sensitive; quality-density beats volume (amends spec Ch.2).** The daily
   count is treated as an **enforcement-risk knob**, not just a throughput dial. The ramp **starts at
   the low end (~1/day/niche)** and only widens once the channel has an established track record of
   original-insight output passing D1; the spec already frames cadence as "start small, prove
   compliance," and this makes the *reason* (the inauthentic-content policy) and the *direction*
   (fewer, denser, more distinctly-original uploads beat more) explicit. The format/template rotation
   that gives combinatorial variety is **necessary but not sufficient** — the persona/treatment layer
   that injects a *view* is the actual defense and must not be value-engineered down.

3. **A per-platform scheduled-publish window (amends ADR 0006, Stage 06).** Stage 06 gains an
   optional **`publish_window`** config (per platform, per niche) so a finished render is **held and
   posted into a peak-audience slot** rather than at batch-completion time. It is config resolved
   through the normal precedence layer (ADR 0010 D5) — global default → niche → platform — and is a
   no-op (post-immediately) when unset, so it does not complicate M0. The exactly-once ledger
   (ADR 0003 D1) already makes a deferred post safe.

4. **Record the community-engagement ceiling (amends ADR 0008 D4 + spec Ch.1 honest ceilings).** Add
   a fourth accepted ceiling: **no automated comment/community engagement** — the pipeline cannot
   contribute the creator-reply portion of first-hours engagement velocity. Accepted by design for an
   unattended PoC; flagged so it is a known limit, not a silent gap.

## Consequences

**Positive**
- The gate that enforces "genuinely good" now also enforces the exact property platforms terminate
  channels for lacking — aligning our quality bar with account survival, at no infra cost.
- A free reach lever (publish timing) is captured behind config, not code.
- The honest-ceiling ledger stays honest; volume is no longer an unexamined dial.

**Negative / costs**
- The "original insight" criterion is a **judge-calibration surface** (like the rest of `05c`) and is
  the hardest thing for an LLM-judge to score reliably — it leans on the human-labeled calibration set
  already open in ADR 0009/0005. Risk: a lenient judge passes generic output; mitigated by the
  conservative low-cadence start (D2) and the human-at-publish ramp (ADR 0004 D2).
- Lower starting cadence trades PoC throughput/sample-size for enforcement safety — deliberate.

## Open (tracked)

- The **`05c` original-insight rubric weight + floor**, and its share of the human-labeled
  calibration set (folds into ADR 0005/0009 open items).
- The **`publish_window` defaults** per platform/niche (need real audience data — revisit when the
  deferred analytics loop lands).
- The **cadence ramp schedule** — what track-record signal widens it, and the ceiling count.
- Whether a later phase adopts **granular AI-disclosure** (recover the ~5–8% TikTok reach) once
  per-asset disclosure can be decided safely without a human.
