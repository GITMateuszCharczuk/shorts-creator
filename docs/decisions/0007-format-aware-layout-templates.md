# ADR 0007 — Format-aware layout templates & the composition engine

- **Status:** Accepted (2026-06-08)
- **Builds on:** [ADR 0005](0005-editorial-quality-layer.md) (the treatment + per-beat visual
  motif this gives structure to; the data-viz renderer left open), [ADR 0006](0006-algorithm-fit-and-format-tuning.md)
  (per-format length/loop), and the format library in spec Ch.6.
- **Touches:** spec Ch.4 (01a, 05), Ch.5 (script/treatment contract + formats library), Ch.6
  (the `layout` field), Ch.7 (throughput), Ch.9 (licensing of the engine), Ch.10 (milestones);
  ARCHITECTURE; `DESIGN.md`.
- **Origin:** the observation that **format reaches the words but not the picture** — 00b is
  format-aware, but 01a (stock), 03 (captions) and 05 (render) are format-blind, so a `ranked_list`
  and a `head_to_head` are *written* differently but *assembled identically*. That is the
  "chaotic / generic AI-slideshow" failure mode.

## Context

The format library (Ch.6) and the treatment (ADR 0005) shape **script content** and **per-beat
visual *motif*** (what to show). Nothing defines the **structural layout** — *where* things sit on
the 9:16 frame, *how* they animate, the montage rhythm. Stage 05 is still "ffmpeg concat + burn
centered karaoke captions," identical for every format. The polished, format-specific script is
therefore poured into a generic visual mould, which reads as generic — the exact slop signature
the whole quality layer (ADR 0005) is meant to kill.

A **format layout template** closes this: a per-format scene grammar of named frame regions +
animation + transitions. It **complements** the treatment rather than duplicating it —
*layout = the format-level skeleton, treatment = the per-beat content that fills it.* It also
*reduces* output chaos by constraining the otherwise-unbounded (random stock × arbitrary caption
placement × no transitions) into a known, on-brand structure per format.

Example — `ranked_list` repeating "item card":

```
  ┌─────────────────────────┐
  │   "#7"   (count badge)   │  rank — ticks in, SFX
  │  ITEM TITLE  @~30% height │  item-name region
  │  [ background media ]    │  media zone (Ken Burns / stock / AI)
  │  auto-caption @~60% height│  karaoke body text
  └─────────────────────────┘   transition: swipe between items
```

## Decision

1. **Layout templates are first-class format config — built for all 8 archetypes.** Each format in
   the `formats/` library gains a **`layout`** recipe: named frame regions (with %-height/safe-zone
   positions), the per-region media/text binding, an animation spec, and inter-beat transitions.
   `ranked_list`, `myth_buster`, `explainer`, `news_reaction`, `cautionary_tale`, `head_to_head`,
   `surprising_stat`, `how_to_steps` each get a bespoke layout (the user chose the **full set**, not
   a phased subset). New formats stay **data, not code** — a new `formats/<name>/layout` entry.

2. **Stage 05 becomes a format-aware compositor.** Render is promoted from an ffmpeg one-liner to
   a **template engine**: it selects the format's layout, binds the structured beat data into the
   regions, animates, and assembles — then still does the per-platform cuts, loop bridge, CTA bump
   + end-card, color grade, and encode.

3. **The 00b → 05 contract becomes structured, not prose.** `script.json` / the treatment emit
   **typed per-beat layout data** keyed to the format (e.g. `ranked_list` → an ordered
   `items[]` of `{rank, title, body, media_query, stat?}`; `head_to_head` → `{side_a, side_b,
   verdict, round[]}` with `side_*: {media_query, label}`, `verdict: {text}`, `round: {metrics}`),
   so each template has typed fields to bind. This is a real contract change (Ch.5). *(Field set
   pinned + extended by ADR 0007a §7b — `stat?`/`round[]`/sub-shapes added there.)*

4. **One composition engine, shared by 05 (layouts) and 01e (data-viz) — chosen for the
   5070 Ti + 7800X3D.** The technique is **headless-Chromium HTML/CSS templating**: the GPU is
   *idle during Stage 05* (the never-co-resident serialization, ADR 0001/0003, means the AI models
   are evicted before render), so the **7800X3D's 16 threads** rasterize frames in parallel while
   the **5070 Ti does NVENC** encode — a ~60s@30fps video (~1,800 frames) renders in minutes.
   - **Engine choice is constrained by our Apache/MIT commercial-safe spine (Ch.9).** **Remotion**
     is the most ergonomic for parameterized templates and is **free at solo/≤3-person scale**, but
     needs a **paid company license** beyond that — a liability against the spine. The **MIT-clean
     path** is **Playwright (Apache-2.0) + hand-rolled HTML/CSS templates** or **Motion Canvas
     (MIT)**. **Locked: Remotion** (2026-06-09), under its free solo/≤3-person terms — chosen for
     template ergonomics over the MIT-clean alternatives, **conditioned on the project staying
     ≤3 people**. This is a **tripwire, not a tax**: crossing 3 people (or Remotion's revenue
     thresholds) triggers a **paid company license (~$100/mo+)** and a re-evaluation against the
     MIT-clean path. Playwright/Motion-Canvas remain the documented fallback if that tripwire fires.
   - Encode via **`h264_nvenc` / `hevc_nvenc`** on the 5070 Ti (free at render time).

5. **Stage 01a stock-fetch becomes format-aware.** Media selection honours the layout's **media
   zones**: `ranked_list` needs N distinct item images (one per rank); `explainer` needs one strong
   concept clip; `head_to_head` needs an A and a B. This ties 01a to the format, not just to a flat
   per-beat keyword.

6. **Layouts inherit the existing render contracts.** Regions respect the **per-platform safe
   zones** (ADR 0005 D7 — for format videos the region *is* the caption placement), the **brand
   kit** (ADR 0005 D9 — fonts/palette/lower-thirds), the **loop bridge + CTA bump + end-card**
   (ADR 0005 D10 / ADR 0006), and **word-timed cuts** (ADR 0005 D4).

## Consequences

**Positive**
- Directly fixes the diagnosed chaos: every format now has a consistent, designed, on-brand
  audiovisual structure — the single biggest "looks professionally made vs AI-slideshow" lever.
- The structured contract makes 01a/03/05 *correct by construction* per format, instead of hoping
  generic assembly fits.
- One engine for layouts **and** data-viz (closes the ADR 0005 D5 renderer open item).

**Negative / costs**
- **The single largest build in the visual path.** Stage 05 goes from a one-liner to a real
  compositor, plus **8 bespoke layout templates** (regions, animation, transitions) — a genuine
  design+engineering effort, spread across the visuals/polish milestones.
- **New runtime dependency** (Node + headless Chromium) in the render image — CPU/GPU-encode only;
  it does **not** violate the never-co-resident GPU rule (GPU is free at render time).
- **Throughput re-opens again** (already re-opened by ADR 0005/0006): frame rasterization is new
  CPU cost; the per-video figure must be **re-measured**, NVENC offsetting the encode side.
- A **licensing decision** now sits on the critical path (engine choice vs the Apache/MIT spine).

## Open (tracked)

- ~~**Final engine** (MIT-clean Playwright/Motion-Canvas vs Remotion-solo) + the **license**
  call.~~ **Resolved (2026-06-09): Remotion**, under its free ≤3-person terms (D4) — the project
  is committed to staying ≤3 people, so the company-license cost does not apply. Playwright/
  Motion-Canvas stay on file as the fallback if that ≤3-person tripwire ever fires.
- ~~The **per-format region specs + a shared animation/transition library** (8 layouts).~~
  **Resolved in [ADR 0007a](0007a-layout-template-design.md):** the hybrid region model +
  `layout.schema.json`, the closed **primitive** library (`MediaZone`/`TextCard`/`Badge`/
  `KaraokeCaption`/`DataVizSlot`/`CitationChip`/`CTABump`/`BrandOverlay`) and **animation/
  transition** library (6 enter/exit + 4 transitions, feel via params+SFX), and **2 of 8** exemplar
  templates (`ranked_list`, `head_to_head`); the other 6 authored as data in M3.
- ~~**Target fps** (24/30)~~ **Resolved: 30** (0007a §8). The **re-measured throughput** has a
  specified **method** (0007a §9) to *run* on the box in M2, folded into the Ch.7 reconciliation.
- ~~How much **GPU-accelerated Chromium** (ANGLE/EGL) helps vs pure-CPU rasterization on this box.~~
  **Resolved: pure-CPU raster + NVENC encode** (0007a §8) — GPU-Chromium (and the pinned-driver
  middle path) rejected as non-deterministic; revisit only on a measured Stage-05 bottleneck.
