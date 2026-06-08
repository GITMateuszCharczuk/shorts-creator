# ADR 0002 — Recency-sourced content + a persistent novelty ledger

- **Status:** Accepted (2026-06-07)
- **Builds on:** [ADR 0001](0001-lightened-runtime-architecture.md) (the lightened runtime).
- **Touches:** `ARCHITECTURE.md` §3 (DAG), §5 (storage), §7 (layout); Stage `00a`/`00b`.

## Context

Two gaps surfaced after the runtime was locked:

1. **No freshness.** `00a` only fetched **numeric** market data (Alpha Vantage / Yahoo /
   FRED). Nothing seeded a video from *what is actually happening this week*, so output would
   skew evergreen/generic.
2. **No novelty memory.** Nothing recorded what had already been produced, so the pipeline
   would happily make the same topic repeatedly — which also trips YouTube/TikTok's
   **repetitious / inauthentic-content** policy (`research/04`, `STRATEGY §5`), a real
   demonetization risk for an automated channel.

Both must work *unattended and across runs*, which depends on the data volume being durable
(see Decision 4).

## Decision

1. **Expand `00a` from "data-fetch" to "research/ingest."** It now pulls, in one step:
   - **Numeric market data** (existing: Alpha Vantage / Yahoo / FRED), and
   - **Recent news** via **free RSS feeds** from reputable finance/business outlets,
     filtered to `published ≥ now − 3 days`.
   - Output `data.json = { market: {…}, news: [{title, url, source, published, summary}] }`.
   - **No paid news API** — keeps the no-recurring-cost constraint. (A free-tier news API is
     a later add if RSS coverage proves thin — recorded as open, not built.)
   - **Licensing/policy:** articles are **source facts and angles → original synthesis with
     on-screen citations** (already a YMYL requirement); we never republish article text and
     skip paywalled sources. Provenance for each cited source goes in `provenance.json`.
   - A fetch failure is a **first-class DAG state** (same as the numeric fetch), not a hidden
     error inside scripting.

2. **Persistent novelty ledger.** An append-only `history/ledger.jsonl` on the durable data
   volume. Each produced video appends:
   ```
   { id, date, niche, topic, title, hook, source_urls: [...], keywords: [...],
     embedding: null }     # embedding reserved for the post-M1 upgrade (Decision 3)
   ```

3. **Dedup in `00b script`, two tiers (ledger now, embeddings later).** Before committing a
   topic, `00b` queries the ledger and **rejects/repicks** a candidate if:
   - any `source_url` was already used, **or**
   - keyword/title overlap with records in a trailing window exceeds a threshold.

   This is the **keyword + source-URL** tier — no model, robust, debuggable. The ledger
   record reserves an `embedding` field so a **cosine-similarity** tier (small local
   embedding model, catches reworded dupes) layers on **post-M1 without schema rework**.
   This is the "both" choice: ship the cheap tier, design for the better one.

4. **Durability of the ledger (the enabling requirement).** The data volume is **host-backed
   via kind `extraMounts`**, so `runs/`, `quarantine/`, and `history/` live on the host disk
   and survive cluster recreation (`kind delete cluster`) and reboots. Dedup across runs is
   only possible because the ledger persists; a plain in-cluster PVC would be wiped on
   cluster rebuild. (Cross-ref `ARCHITECTURE.md §5`.)

## Consequences

**Positive**
- Content is tied to the last 3 days → genuinely current, less generic.
- The ledger prevents repeats *and* serves as the compliance lever against repetitious-content
  demotion — one mechanism, two wins.
- Citations + provenance from real articles strengthen the YMYL accuracy posture.

**Negative / costs**
- New failure surface: RSS feeds go stale/move/rate-limit → handled as a first-class `00a`
  DAG state with retry/backoff, but it is a moving part.
- Copyright discipline required: paraphrase + cite, never republish, skip paywalled.
- Topic-overlap threshold needs tuning; too strict starves the batch, too loose repeats.

## Open (tracked)

- **RSS source list** to curate per niche (finance vs business outlets).
- **Overlap threshold** default + how a starved batch behaves (widen window / relax / skip).
- **Embedding model** choice for the post-M1 similarity tier.
- Optional **free-tier news API** if RSS coverage is thin.
