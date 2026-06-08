# Architecture Review

> A skeptical review of the corpus (the planning docs as an information architecture) and the
> runtime/service architecture they specify. Conducted pre-implementation, when fixes are cheap.
> Findings marked **[applied]** were corrected in this pass; **[open]** items need a conscious
> decision (recorded as future ADRs) before they are settled.

---

## Verdict

The corpus is unusually strong for a pre-implementation project — clean layering (why → how →
tooling → evidence → scope), rigorous licensing, and a genuinely skeptical risk register. The
*thinking* is solid. The problems cluster in three areas:

1. **Doc drift** — contradictory relics from earlier iterations that actively mislead.
2. **Service decomposition** — one monolithic stage and a VRAM-lifecycle contradiction that fight
   the "never co-resident" rule.
3. **Unreconciled internal disagreements** — the technical research disagrees with `DESIGN.md` on
   two load-bearing decisions (per-video DAG vs stage-batching; the weight of the Argo/k8s stack)
   and those conflicts were never resolved.

None are fatal; all are cheaper to fix now than after code exists.

---

## Part 1 — Corpus (information) architecture

**Layering — good.** `README` (index) → `POC` (authoritative current scope) → `STRATEGY` (why) →
`DESIGN` (how) → `OPTIONS` (tooling matrix) → `research/01–05` (evidence) → `DEV-WORKFLOW` (process).
Clear separation, explicit precedence ("POC wins on scope", "STRATEGY wins on strategy").

### Finding C1 — No single decision-of-record; the "locked stack" drifted across three docs **[partially applied]**
The locked stack lives in `DESIGN §2`, `OPTIONS "Confirmed stack"`, and `POC §2`, and they fell out
of sync. Drift found and fixed in this pass:

| Drift | Location | Status |
|---|---|---|
| `OPTIONS §C` recommended "Qwen2.5 ⭐**7B**" while everything else says **14B** | OPTIONS.md | **[applied]** |
| `OPTIONS` "defaults" listed obsolete categories (`history, geopolitics, moving story, tech news, horror story`) | OPTIONS.md | **[applied]** |
| `OPTIONS` said "upload private draft only, **never auto-publish**" — contradicts auto+safety-net / private-first | OPTIONS.md | **[applied]** |
| `DESIGN` intro: "publishes YouTube Shorts for **five content categories**" | DESIGN.md | **[applied]** |
| `DESIGN §1` non-goal: "**Cross-posting to TikTok/Reels … out of scope**" — contradicts the entire multi-platform Stage 6 | DESIGN.md | **[applied]** |
| `DESIGN §6`: "celebrity news dropped, replaced with **tech news**" — categories that no longer exist | DESIGN.md | **[applied]** |

Root cause: decisions and their reversals (celebrity→tech-news→gone; FB-Reels-RPM correction;
true-crime drop) were patched inline instead of recorded, leaving fossils.

**Recommendation [open]:** adopt a lightweight **ADR log** (`docs/decisions/NNN-*.md`) as the single
place a decision and its supersessions live; have the DESIGN/OPTIONS tables *link* to ADRs rather
than restate them.

### Finding C2 — The most important contract is unspecified **[open]**
`job.json` is "the spine that threads through every stage" but exists only as prose; same for
`script.json`, `assets.json`, `provenance.json`. **These schemas are the architecture** — every
stage's interface. They should be the first committed code artifact (versioned JSON Schema), not
discovered during implementation.

### Finding C3 — OPTIONS.md was the stalest doc **[applied]**
It reads as authoritative tooling truth but carried the most relics. Given a scope banner and the
C1 corrections in this pass.

---

## Part 2 — Runtime / system architecture

**The good:** container-per-stage with `job.json` as a pure-function interface is the right
backbone (isolates conflicting CUDA/Python stacks, free retries/artifact-passing, extends by
config). The sm_120/CUDA-12.8 pinning discipline correctly named the #1 "works on my box" risk.
Real-footage-first as the *architectural* answer to the 16 GB img2vid quality ceiling is the single
best decision in the corpus.

### T1 — Per-video DAG vs stage-batching (throughput contradiction) **[open]**
`DESIGN §3` has a `CronWorkflow` submit *N per-video workflows*. But `research/03 §6.3/§9` says the
**#1 throughput multiplier is stage-batching** ("all scripts, then all images, then all clips for
the day's batch") precisely to amortize the minutes-per-video cost of swapping FLUX/LTX/Qwen in and
out of 16 GB. Per-video DAGs reload every model every video. Tolerable at the PoC's 2–4/day;
becomes the bottleneck if scaling toward the 15/day the research targets. **Choose consciously and
record why.** Recommendation: design stage-batched even at PoC scale — it's the architecture you keep.

### T2 — Always-on Ollama vs the "never co-resident" rule **[open — concrete bug]**
`DESIGN §4 Stage 0` runs **Ollama as a persistent Deployment+Service**, but `research/03 §5` and
`POC §4` mandate the LLM is **not resident while the video model runs**. A persistent Ollama
Deployment **pins VRAM** and violates that rule — Stage 1 (FLUX/LTX, ~12–14 GB) can collide with a
resident Qwen-14B. **Fix:** run the LLM as a per-batch Job (load → generate-all → exit), pin it to
CPU, or give it explicit eviction. Do not leave it as a persistent GPU resident.

### T3 — Infra complexity vs the PoC's reliability bar **[open]**
The PoC's definition of done *is* reliability, yet the platform is Argo + kind + NVIDIA
device-plugin (GPU-in-kind = the corpus's own "primary technical risk") + MinIO + PVC + sm_120 — a
large operational surface for 2–4 videos/day, single node, single GPU, solo maintainer. The corpus's
*own* research (`research/03 §7.1`) is ambivalent: *"for a single-node, single-GPU project the YAML
overhead is significant… Prefect is a legitimate lighter alternative."* Not an argument to drop Argo
(k8s-native extensibility serves the full vision), but the tension was never weighed explicitly.
**Record an ADR:** what is the k8s stack buying us at PoC scale vs. ComfyUI + a thin Python
orchestrator + host GPU?

### T4 — ComfyUI as generation backend: a strong research rec DESIGN ignores **[open]**
`research/03 §7.2` recommends **ComfyUI** as the de-facto generation backend (hosts FLUX/LTX/ESRGAN/
RIFE graphs, HTTP API) + custom Python for VRAM lifecycle. DESIGN describes bespoke per-stage
containers instead. Unmade decision with large implementation consequences.

### T5 — Two storage systems for a single node **[open]**
MinIO **and** a shared PVC. Defensible (artifact lineage + scratch), but `OPTIONS §L` lists
"PVC-only" as simpler. For a single-node PoC, MinIO may be complexity not yet paying its way.

---

## Part 3 — Per-service (stage) architecture

Each stage is "one container = one Argo template = pure function of inputs + `job.json`" — a sound
principle. Per-stage critique:

| Stage | Assessment | Key concern |
|---|---|---|
| **0 Script** | Mostly sound | **Embeds external data-fetch** (Alpha Vantage/Yahoo/FRED) inside scripting — a separate concern with its own rate limits/failure modes that finance originality depends on. **Split out a `data-fetch` step** so a fetch failure is a first-class DAG state. Plus T2. |
| **1 Visuals** | **Weakest decomposition** | One container bundles **4+ GPU model lifecycles** (stock-fetch + FLUX + LTX + ESRGAN/RIFE + GFPGAN). VRAM choreography is hidden inside an opaque container. **Decompose into 1a stock-fetch (CPU), 1b image-gen (FLUX), 1c img2vid (LTX), 1d upscale/restore** — one model each, clean load/unload, independent retry; this is also what *enables* stage-batching (T1). Highest-value service refactor. |
| **2 Voice** | Good | Light; CPU-viable. |
| **3 Subtitles** | Good | Clean dependency on `narration.wav`; large-v3 fits. |
| **4 Music** | Good | CPU; per-track provenance well-considered. |
| **5 Render** | **Underspecified linchpin** | "Distinct native cut per platform" is the whole anti-duplicate-content defense (R4), but *what differs* per platform (caption style/hook/length/sound) is hand-waved. Risk: it degenerates into a re-encode, which TikTok penalizes as a dupe. **Needs a concrete per-platform render spec.** |
| **5b QC gate** | **Most critical, least specified** | This *is* "auto + safety-net" — the human replacement. Pass/fail thresholds, the second-pass LLM's VRAM source (Ollama again → T2), the quarantine store, and the spot-audit workflow are all undefined. The linchpin of the safety model is a stub. |
| **6 Distribute** | **Missing idempotency** | Retries can **double-post**. For unattended-with-retries this is a real reliability bug — needs an idempotency key / posted-state ledger so a re-run never re-uploads. Per-platform quota/rate tracking and OAuth refresh-token rotation lifecycle are also undesigned. |

**Cross-cutting gaps (all services):** no defined `job.json`/provenance **schemas** (C2); no
**exactly-once** semantics on side-effecting stages; **observability** named but not designed
(logs→where? metrics?); **quarantine + spot-audit** mentioned but not built as a subsystem; **test
architecture** committed-to (`POC §6`) but not sketched (deterministic seams: schema validation,
music selection, render-arg construction, QC heuristics).

---

## Prioritized recommendations

**P0 — before any code (cheap now, expensive later):**
1. **Specify contracts** — `job.json` / `script.json` / `assets.json` / `provenance.json` as
   versioned JSON Schema. *(open)*
2. **Decompose Stage 1** into 1a–1d (one model per sub-stage). *(open)*
3. **Resolve T2** — LLM as per-batch Job or CPU, never a persistent GPU resident. *(open)*
4. **Drift-sweep** the relics + scope-banner OPTIONS. *(**applied** this pass)*

**P1 — decide consciously, record as ADRs:**
5. **T1** per-video vs stage-batched (recommend: batched).
6. **T3/T4** Argo+k8s vs lighter Prefect/ComfyUI host-GPU — justify the k8s surface against the
   reliability goal.
7. **Stage 6 idempotency** — promote to a first-class design element.

**P2 — specify the underspecified linchpins:**
8. Per-platform **render differentiation** spec (Stage 5).
9. **QC gate** concrete checks/thresholds + **quarantine/spot-audit** subsystem (Stage 5b).
10. ADR mechanism + observability/test architecture sketch.

---

## Status of this pass

- **Applied:** corpus drift-sweep (Findings C1, C3) — corrected the relics/contradictions in
  `DESIGN.md` and `OPTIONS.md`, added a scope banner to `OPTIONS.md`.
- **Open (recorded above, awaiting a conscious decision):** C2 (contract schemas), T1–T5, the
  Stage 0/1/5/5b/6 service-level items, and the ADR mechanism. These are design decisions, not
  factual corrections, so they were not silently applied.
