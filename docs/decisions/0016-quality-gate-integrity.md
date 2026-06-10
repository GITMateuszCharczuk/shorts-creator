# ADR 0016 — Quality-gate integrity: independent judge, script-time floor, per-cut coverage

- **Status:** Accepted (2026-06-10)
- **Builds on:** [ADR 0005](0005-editorial-quality-layer.md) (best-of-N + the 05c gate),
  [ADR 0008](0008-output-parity-hardening.md) (the 05x vision pass feeding both gates),
  [ADR 0009](0009-content-integrity-and-account-robustness.md) (judge independence — open until
  now), [ADR 0014](0014-content-automation-best-practice-alignment.md) (original-insight as a
  survival property), [ADR 0010](0010-implementation-conventions-and-extensibility-seams.md) D3
  (the per-stage judge-backend seam this finally uses).
- **Touches:** spec Ch.4 (00b, 05x, 05b, 05c rows), Ch.5 (`vision.schema`), Ch.10; the M1 plan
  (00b floor) and M3 plan (05x/05c rework).
- **Origin:** the same architecture re-review as ADR 0015. Four gate findings interlock: (1) ADR
  0014 made "original insight" *channel-survival*, while the judge scoring it was still the same
  Qwen-14B that wrote the script — a self-judge bias ADR 0009 records as an **open weakness**;
  (2) best-of-N *selects* but has no floor, so an all-mediocre batch still burns the full GPU lane
  before quarantining post-render; (3) the gates run **once** but **two platform cuts ship** —
  nothing said which cut gets judged; (4) the M3 draft had quietly collapsed scoring *into* the
  VLM call, conflating ADR 0008's "vision pass observes, gates judge" split (and leaving 05c's
  `capability: llm` declaring a backend it never called).

## Decision

1. **The 05c judge is an independent, non-Qwen-lineage model — pinned now, not "preferred."** The
   judge backend resolves per-stage (ADR 0010 D3) to a small instruct model from a **different
   model family** (e.g. Gemma- or Mistral-family, permissive license, 7–9B Q4 — fits the 16 GB
   card alone under never-co-resident, swapped in at the post-render slot where FLUX/LTX are
   already evicted; a CPU endpoint stays the fallback per ADR 0009 #4). The final model pick
   happens at M3 bring-up **against the calibration set (D2)**; what is decided *here* is that
   shipping 05c with the author-model as judge is **not acceptable** — ADR 0009 #4 closes from
   "recorded weakness" to "decided mechanism."

2. **The ramp's human approvals become the calibration set — captured, not discarded.** Every
   human approve/reject during the human-at-publish ramp (ADR 0004 D2) is recorded into that
   video's `feature_record` alongside the judge's scores. The ramp was already being paid for;
   this turns it into the **human-labeled calibration floor** ADR 0009 wanted, for free, from the
   first ramp week. The 05c floor is re-anchored against these labels before the unattended phase.

3. **A script-time floor at 00b — quarantine before the GPU spends.** Best-of-N continues to
   *select* with the resident model (ranking its own N outputs is the low-bias use of a
   self-judge), but the winner must additionally **clear a provisional floor** or the video
   quarantines **at script time** — before stock-fetch, diffusion, render, or the VLM pass spend
   anything. The authoritative floor remains 05c on the rendered output; 00b's floor is the cheap
   first line. Quarantine-at-script costs seconds; quarantine-at-render costs the whole GPU lane.

4. **Per-cut gate coverage is decided, not implied.** The **05x VLM pass runs once, on the YouTube
   cut** — the public leg, where the stakes live. The platform cuts share all *content*; they
   differ in **geometry + CTA verb**, which are deterministic properties of each cut's
   `render_manifest`. So `05b` adds **per-cut geometric assertions** — every region (caption band,
   `cta_bump`, `citation`, injected §6 regions) must project inside that platform's safe rect — run
   for **every** cut as pure rectangle math, no VLM. One VLM pass + N cheap geometric passes
   replaces the false choice between "double the VLM budget" and "ship the TikTok cut ungated."

5. **Observations cross the 05x boundary; verdicts do not.** Restores ADR 0008's split: 05x emits
   `vision.json` = structured **per-keyframe observations** (artifacts, garbled text, occlusion,
   composition notes) **+ visual sub-scores** (`coherence`, `pacing`) — what a vision model can
   actually assess. `05c`'s independent judge (D1) scores the *text-judgeable* criteria (`hook`,
   `original_insight`, `payoff`) from script + treatment + observations, then merges with the
   visual sub-scores under the ADR 0005/0014 rubric weights and applies the floor — making 05c's
   `capability: llm` true again. `05b` reads the artifact/legibility/occlusion observations for its
   checks. **VLM serving is pinned to an OpenAI-compatible chat-completions endpoint with image
   content** (e.g. Ollama's `/v1/chat/completions` with a vision model) — no invented `/judge`
   route.

## Consequences

**Positive**
- The criterion that keeps the channel monetizable (ADR 0014) is no longer scored by a model
  structurally inclined to approve its own work, and its floor is anchored to human labels the
  ramp produces anyway.
- All-bad batches die at script time — the most expensive failure mode (render-then-quarantine)
  becomes the rare case instead of the default path.
- Both shipped cuts are gated; the VLM budget stays at one pass per video.
- The 05x/05b/05c responsibilities match ADR 0008 again, and every stage's declared capability is
  one it actually uses.

**Negative / costs**
- One more model on disk + one more swap in the post-render slot (judge ↔ VLM) — bounded, and the
  ADR 0009 CPU-endpoint fallback stands if the swap proves costly in the M4 throughput
  reconciliation.
- The provisional 00b floor is a new tuning knob seeded by guess until D2's labels accumulate;
  set it permissive initially (it exists to catch *all-bad*, not to be the quality bar).

## Open (tracked)

- The judge **model pick** + prompt, decided at M3 bring-up against the D2 calibration labels.
- The **00b provisional floor** and **05c floor** values (re-anchored from D2's labels before the
  unattended phase).
- Whether `05b`'s geometric per-cut checks live in 05b or as a 05-render post-assertion (decide in
  M3/M5 wiring).
