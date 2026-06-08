# ADR 0010 — Implementation conventions & extensibility seams (M0)

- **Status:** Accepted (2026-06-08)
- **Builds on:** every prior ADR — this one decides *how the code is shaped* so the design they
  describe stays cheap to extend. Especially [ADR 0001](0001-lightened-runtime-architecture.md)
  (stage = pure-fn-of-inputs topology), [ADR 0003](0003-resilience-concurrency-observability.md)
  (idempotency/resumability), [ADR 0009](0009-content-integrity-and-account-robustness.md)
  (persisted seed — the precondition for stage caching).
- **Touches:** spec Ch.5 (contracts), Ch.10 (milestones — M0 conventions); ARCHITECTURE
  (`shared/`, `stages/`, `schemas/`).
- **Origin:** a "what do we set up *now* to make development easier later" review, taken while the
  repo is still **docs-only (zero code)** — the cheapest possible moment to fix conventions, before
  the first stage hard-codes them.

## Context

The spec's north star is **"extend by configuration, not rewrite."** That is only true if the code
has the right *seams* from the first commit. The project will provably grow along known axes — more
niches, more platforms (FB/IG carry-forward), more formats, and a long list of model A/B swaps
(LTX↔Wan, Kokoro↔Orpheus, FLUX↔SDXL, Qwen-14B↔32B) — plus a deferred analytics loop that needs
historical data it can only get by logging from day one. None of that is speculative scale; each
maps to a commitment already in the spec. Retrofitting these seams after ~15 stages exist is
expensive; defining them at M0 is nearly free.

This ADR records the **implementation conventions** to lock in at M0. It deliberately does **not**
add runtime capability — no new stage, model, or platform — it shapes how those get added later.

## Decision

1. **Schemas are *versioned* contracts, enforced.** Every schema carries a `schema_version`; a
   **validation harness** checks each stage's inputs/outputs at the boundary and **fails loud**;
   a **golden-fixtures set** (a known-good `job → script → assets → … → final` chain) is committed
   and used by tests. *Why now:* the schemas are the architecture — ~15 stages and 10 ADRs all
   bind to `script.schema`, which already carries reserved/optional fields (embeddings, hook
   variants, affiliate, `{value, source_ref}`). Versioning + fixtures is what lets the contract
   evolve without silently breaking downstream stages.

2. **A thin Stage SDK; the DAG is generated from stage metadata.** One base contract —
   `run(ctx)` reads declared inputs + `job.json`, writes declared outputs + status — with the
   shared plumbing (`job.json` IO, provenance, structured logging, retry/quarantine signaling,
   **seed access**) living in `shared/`. Each stage **declares its inputs/outputs/resources as
   metadata**. *Why now:* adding or reordering a stage (e.g. the 05x/05b/05c cluster) becomes "write
   a function + declare deps," not "edit the function *and* the workflow YAML and hope they agree."
   **For the PoC, ship hand-written Argo templates plus the metadata manifest, with a test that
   asserts the templates match the manifest (drift-catcher) — do *not* build a DAG generator yet.**
   The fixed ~15-stage *concurrent* topology of ADR 0011 (lane-fork, the confirm-VRAM gate between
   00b/01b, per-video `continueOn` sub-DAGs) would make a generator more complex than the ~15
   templates it emits; the generator is deferred (see open items) until the topology actually churns.

3. **Adapter interfaces for the three pluralities, defined before the first concrete one.**
   - **`DistributionAdapter`** (`publish` / `confirm_posted` / `allowed_visibility`) — the base owns
     the **ledger write protocol** (intent→confirm, ADR 0003 D1); each **adapter owns confirm /
     reconcile**, because recovery is platform-specific (YouTube `insert` has no idempotency token →
     search recent uploads; TikTok → poll `publish_id`) — that logic cannot fully live in the base.
     `allowed_visibility` returns the **set of visibilities legal given current audit state** (so 06
     degrades to SELF_ONLY/private as *data*, not a code branch — ADR 0009 D3), rather than a coarse
     boolean.
   - **Model capability backends** (`generate_image(prompt, seed)`, `img2vid(…)`, `tts(…)`,
     `vlm_judge(…)`, `llm(…)`) — splits today's single host client into per-capability interfaces
     so every A/B swap on the open list is a **config swap**, not stage surgery. Backend choice
     resolves **per-stage** (00b can run Qwen-32B while 05b runs 14B), and the **judge backend can
     point at a separate CPU/small-model endpoint** so an independent non-Qwen judge (ADR 0009 D4) is
     a config swap, not a VRAM fight under never-co-resident.
   - **`LayoutEngine`** (`render(format_layout, structured_data, brand_kit) → frames`) — abstracts
     the still-unpicked composition engine (Playwright/Motion-Canvas/Remotion, ADR 0007). Note all
     three candidates share the **same DOM/CSS paradigm**, so this seam is honestly a **license
     hedge** (deferring the Remotion paid-license question) more than a true engine-portability
     layer — cheap insurance given the license is genuinely unresolved.

4. **An offline dev harness + content-addressed stage cache.** Because the topology is already
   thin HTTP clients → host (ADR 0001), `HOST_GPU_ENDPOINT` can point at **fake backends that
   return fixtures**, letting the **entire DAG run on a laptop / in CI with no GPU**. Paired with a
   **content-addressed cache keyed on `(stage, input_hash, seed)`** — sound precisely because the
   seed is now persisted (ADR 0009) — re-runs skip completed work and a developer can iterate on
   one stage without re-running upstream. **For generative stages the key also includes the
   model + graph version** (FLUX/LTX aren't guaranteed bit-reproducible across driver/model
   versions; without this the cache could silently serve stale frames) — or those stages are
   cache-exempt until reproducibility is verified on the box. *Why now:* built in from the start it's
   almost free; bolted on later it means rewriting every stage's IO. Biggest dev-velocity multiplier.

5. **A typed config-resolution layer; profiles & formats are validated config.** One resolver with
   explicit precedence — **global defaults → niche profile → batch overrides → per-platform** —
   replaces scattered `if platform == …` conditionals (per-platform CTA verbs, phase-dependent lane
   mix, per-platform music/render deltas all already exist). `profile.schema.json` and
   `format.schema.json` make "add a niche / add a format" a **validated data file** with a loader/
   registry — delivering the "data, not code" promise concretely. **Two honest caveats:** (a) a niche
   is fully data, but a **format is data-driven only within the existing region/data-shape
   vocabulary** — a genuinely new structural shape needs a new LayoutEngine template *and* a new
   `script.schema` per-beat field shape (ADR 0007 D3), i.e. a code change, so don't oversell formats
   as pure config; (b) to keep the promise from rotting, the **M0 golden-fixtures CI asserts no stage
   source branches on `platform ==` / `niche ==`** (all such values resolve through the layer) and
   that adding a profile/format fixture flows end-to-end through the fakes — turning "data-driven"
   from aspiration into a CI-enforced property.

6. **Emit the feedback-loop data contract now, even though the loop is deferred.** Define a
   **stable per-video record** (chosen format / seed / hook-variant + judge scores + a reserved
   metrics slot) and write it from the first run. *Why now:* the analytics loop is post-PoC, but it
   can only start *warm* if history exists — and you cannot retroactively log what you didn't
   capture. Extends the ledger/reserved-field pattern already in ADRs 0002/0005 into a first-class,
   stable event shape.

## Explicitly out of scope (deferred, by design)

Multi-account orchestration, horizontal scale-out, cloud-GPU autoscaling, and any web UI. The
single-host SPOF is acceptable for the PoC (ADR 0003). The adapter seams above are what make those
*possible later without pre-building them* — don't build for 30/day before shipping 2/day.

**Honest scope of "scales later":** the adapter seams cover **models, distribution, and layout** —
*not* the artifact bus or the GPU transport. So **single-node → a bigger single node is config**,
but **true multi-node is a topology change, not a config swap**: the file-path artifact bus on one
RWO host-mounted PVC would need an RWX/object store (the MinIO deliberately removed in ADR 0001),
and the host-process GPU plane reached over the kind Docker-bridge gateway would need a networked
GPU transport + a cross-node lease. Those reintroductions are the known cost of going multi-node;
nothing here pre-builds them, but the claim is "extends," not "scales horizontally for free."

## Consequences

**Positive**
- The spec's "extend by configuration" goal becomes a property of the code, not an aspiration.
- The pipeline is developable and testable **without the GPU host** — unlocks real CI.
- New platforms/models/formats are drop-in; the analytics loop starts with data.

**Negative / costs**
- More upfront scaffolding before the first `final.mp4` (harness, SDK, interfaces, fakes) — a
  slower M0 in exchange for a faster M2→M5 and cheaper post-PoC growth.
- The fakes are a maintenance surface: they must track the real backends' contracts or CI gives
  false confidence (mitigated by the shared schema/fixtures from D1).

## Open (tracked)

- Stage-metadata format + the DAG generator (hand-written Argo templates vs generated).
- Cache backend + eviction/TTL for the content-addressed store; where the key boundary sits for
  non-deterministic-but-seeded stages.
- Fidelity bar for the fake backends (fixture replay vs lightweight real models in CI).
- Whether the feedback record lives in the ledger or a separate metrics store.
