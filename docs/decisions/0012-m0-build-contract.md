# ADR 0012 — M0 build contract & acceptance criteria

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0010](0010-implementation-conventions-and-extensibility-seams.md) (the M0
  conventions this makes concrete), with primitives referenced from
  [ADR 0003](0003-resilience-concurrency-observability.md) (status/ledger),
  [ADR 0009](0009-content-integrity-and-account-robustness.md) (seed),
  [ADR 0011](0011-performance-and-optimization.md) (cache).
- **Touches:** spec Ch.5 (contracts) + Ch.10 (M0 milestone); ARCHITECTURE §7.
- **Origin:** the implementation-readiness review found M0 well-*motivated* but not yet *buildable* —
  every concrete primitive (`input_hash`, the stage `ctx`, adapter signatures, the fixture
  mechanism, status enum, deliverable ordering, "done" conditions) was prose or open, so an engineer
  told "do M0" would stall immediately.

## Context

ADR 0010 decided the M0 *conventions* (versioned schemas, Stage SDK, adapters, offline harness +
cache). But "design a schema" and "implement the cache" need a few small **contracts-of-the-
contracts** pinned first, or two engineers will invent incompatible ones. This ADR fixes those
primitives and gives M0 a testable definition of done and an order to build in.

**Scope note (resolves the apparent contradiction).** Ch.5 calls the schemas "the first committed
code artifact" while ADR 0010 frames M0 as "conventions" — these are the **same statement**: M0's
job is to turn the Ch.5 **prose contracts** into **executable artifacts** (JSON Schema + typed
Protocols + harness + fakes). The prose is the *input*; the typed files are the *output*. This ADR
does **not** pre-author every field of the 11 schemas — that authoring *is* the M0 work — it pins
only the primitives the schemas and SDK all depend on.

## Decision

1. **`input_hash` (the cache key).** For a stage, `input_hash = sha256(` canonical-JSON of
   `{ declared_input_digests: {name: sha256(bytes)} (sorted), resolved_config: <canonical JSON of
   the config the resolver produced>, stage_version }` `)`. For **generative** stages the tuple also
   includes `model_id + graph_version` (ADR 0010 D4). The cache key is `(stage, input_hash, seed)`.
   `job.json` *status* fields are excluded from the hash (they mutate within a run).

2. **The Stage `ctx` interface.** A stage is `def run(ctx) -> StageResult`. `ctx` exposes:
   `ctx.read_input(name) -> Path`, `ctx.write_output(name) -> Path`, `ctx.job` (parsed `job.json`),
   `ctx.seed`, `ctx.config` (the resolved per-stage config), `ctx.log` (structured logger),
   `ctx.backend(capability)` (model/distribution/layout adapters), and `ctx.quarantine(reason)` /
   `ctx.degrade(reason)` for the failure paths. Inputs/outputs are by **declared name** (mapped to
   PVC paths by the SDK), never hard-coded.

3. **Stage metadata (manifest, not generator).** Each stage ships a small declarative manifest —
   `{ id, inputs[], outputs[], compute: cpu|gpu, capability?, resources? }`. The Argo templates are
   **hand-written**; a CI **drift-catcher** asserts templates ⟷ manifests agree (ADR 0010 D2). No
   generator in M0.

4. **`job.json` status enum.** Per-stage status ∈ `pending | running | done | quarantined | failed`;
   updates are **section-scoped atomic writes** (write-temp + rename), one writer per
   `<video-id>/` subtree (ADR 0003 D6).

5. **`schema_version`.** A **semver string** on every schema and every instance. The validation
   harness **fails** on a major-version mismatch and **warns** on a minor mismatch.

6. **Adapter Protocols (typed).** Ship Python `Protocol`/ABC stubs with full type hints, e.g.
   `DistributionAdapter.publish(render: Path, meta: PostMeta) -> PostReceipt`;
   `.confirm_posted(video_id, platform) -> PostReceipt | None`;
   `.allowed_visibility(audit_state) -> set[Visibility]`. Model backends:
   `generate_image(prompt, seed) -> Path`, `img2vid(image, seed) -> Path`, `tts(text) -> Path`,
   `llm(prompt) -> str`, `vlm_judge(frames, script) -> Judgment`. `LayoutEngine.render(render_manifest)
   -> Frames` (refined by ADR 0007a §2; resolve merges layout/data/brand kit/timings/seed into the
   manifest). The base owns the ledger write protocol; adapters own confirm/
   reconcile (ADR 0010 D3).

7. **Fakes + golden fixtures.** A fake backend resolves a request to a fixture by
   `(capability, input_hash)` → a file under `tests/fixtures/`. M0 ships **one golden video's full
   chain** (`data → script → assets → … → posts`) so the GPU-free DAG has a deterministic input.

8. **M0 deliverable ordering.** (1) primitives above + `schema_version` harness skeleton →
   (2) the 11 JSON Schemas + golden fixtures → (3) the `ctx`/Stage SDK + stage manifests →
   (4) the adapter Protocols + fakes → (5) the content-addressed cache → (6) CI wiring the full
   fake DAG GPU-free.

## M0 acceptance checklist (the testable "done")

- [ ] Every schema has `schema_version`; the harness **rejects** a fixture with a wrong-typed field,
      a missing required field, and a major-version mismatch (each a failing test).
- [ ] The 11 schemas validate the golden-fixture chain end to end.
- [ ] `pytest` runs all stages `00a → … → 06` against the **fakes with no GPU**, producing the
      golden `posts` record; CI is green on a GPU-less runner.
- [ ] Re-running an unchanged stage is a **cache hit** (no recompute); changing a declared input or
      seed is a **miss**.
- [ ] A stage authored against the SDK needs **zero** `platform ==` / `niche ==` branches (the
      CI assertion from ADR 0010 D5 passes).

## Out of scope (still open)

Authoring every field of all 11 schemas to final (that is the M0 work, guided by this contract); the
**cache backend** substrate (file vs sqlite); the **fake-fidelity bar** (fixture replay vs a tiny
real model in CI). These remain in the spec's open-items list.

## Consequences

- M0 becomes a buildable milestone with an unambiguous start (the primitives), a sequence, and a
  pass/fail gate — instead of a design brief.
- Small risk of over-fixing a primitive before implementation teaches us better; each is cheap to
  revise and `schema_version` makes contract changes explicit.
