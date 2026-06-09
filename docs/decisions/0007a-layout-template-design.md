# ADR 0007a — Layout template design: region model, primitive & animation library, the two exemplars

- **Status:** Accepted (2026-06-09)
- **Elaborates:** [ADR 0007](0007-format-aware-layout-templates.md) — this is the design that
  fills ADR 0007's tracked open items for the layout layer. It does **not** re-open any ADR 0007
  decision; it makes them buildable.
- **Resolves (from ADR 0007 / spec Ch.10 open #8):** the **per-format region-spec model** + the
  **shared animation/transition library** (the design + **2 of 8** exemplar templates built:
  `ranked_list`, `head_to_head`; the other 6 are authored later as data — see §11); **target fps**
  (**30**); **GPU-accelerated Chromium vs pure-CPU** (**CPU raster + NVENC encode**). A **throughput
  re-measurement method** is specified (§9), to be *run* on the real box in M2.
- **Leaves open (unchanged from ADR 0007):** the **engine/license lock** (MIT-clean Playwright/
  Motion-Canvas vs Remotion-solo) stays deferred to the **M2 visuals milestone**. This design is
  written **engine-neutrally** and sits entirely on the `LayoutEngine` adapter (ADR 0010), so the
  engine pick is an implementation of the contract below, not a change to it.
- **Touches:** spec Ch.4 (05, 01a, 01e), Ch.5 (`layout.schema.json` + the typed beat contract),
  Ch.6 (the `layout` recipe), Ch.7 (throughput), Ch.10 (M2/M3 + open #8/#9).

## Context

ADR 0007 decided *that* every format owns a layout; it left *how a layout is expressed* open. That
choice is load-bearing: it decides whether "adding a format is **data, not a code change**"
(Ch.6) actually holds, and how the shared-with-01e animation library is structured. Three models
were weighed:

- **Per-format React/components** — most expressive per template, but adding/retiring a format
  becomes a **code** change (violates the data-not-code rule) and 8 hand-written components drift in
  safe-zone/brand handling.
- **Pure-data DSL** — maximally config-driven, zero per-format code, but the expressive ceiling is
  low: complex animation/transition encodes into an awkward home-grown DSL and reinvents the engine
  badly.
- **Hybrid: data regions + a closed primitive/animation library** *(chosen)* — a format's `layout`
  is declarative **data**; a single generic renderer interprets it using a **closed** library of
  composable primitives + a **named** animation/transition library. New **format = data**; a new
  **kind** of primitive/animation = a code change to the library. This is the only model that keeps
  ADR 0007's data-not-code rule enforceable while leaving room for real motion design.

## Decision

### 1. Hybrid model, on the `LayoutEngine` adapter

A format's `layout` is **declarative data**. One generic renderer — the `LayoutEngine`
implementation (ADR 0010) — interprets it; it contains **no per-format logic**. It iterates beats,
places regions, mounts primitives, and runs animations/transitions by name. The 8 layouts are data
files; the renderer + library are the only code, shared verbatim with **01e data-viz** (a chart is
just a `DataVizSlot` primitive in a region — this is why ADR 0007 made the engine shared).

### 2. The composition engine & data flow — render is `pure(manifest)`

```
00b treatment + typed per-beat layout data ─┐
01a media (per layout media zones)          ├─►  resolve  ─►  render_manifest.json  ─►  LayoutEngine
01e data-viz components                      │   (pure)         (fully bound)            paints frames
03 WhisperX word timings                     │                                            @30fps (CPU)
brand kit + profile (safe-zones, palette) ───┘                                                │
seeded slots (CTA bump D10, loop+end-card 0006)                                    frames ─► ffmpeg
                                                                                    NVENC ─► renders/<platform>.mp4
```

A **resolve step** (deterministic, pure) merges the format `layout` + typed per-beat data + word
timings + brand kit + the seeded slots into a flat, fully-bound **`render_manifest.json`**.
**Everything stochastic/seeded is decided here** (consuming the persisted `job.json` seed, ADR
0009), so the render is a **pure function of the manifest** → reproducible by construction. The
`LayoutEngine` then paints frames; **per-platform deltas are manifest deltas, not code paths**
(youtube/tiktok/instagram differ only in safe-zone insets and the CTA verb/icon — same renderer,
three manifests, the "distinct native cuts" of ADR 0005 D4).

### 3. The region-spec schema (`layout.schema.json`)

A **region** is the atomic unit. Each carries:

| field | meaning |
|---|---|
| `name` | region id, e.g. `bg_media`, `rank_badge`, `item_title`, `citation` |
| `bbox` | `{x,y,w,h}` in **safe-zone-relative units** (0–1 of the platform-safe rect) — so per-platform insets reflow automatically and one layout serves all 3 platforms |
| `z` | z-order (paint order) |
| `bind` | the **typed beat-field** that feeds it (`item.title`, `side_a.media`, `verdict.text`) — references the 00b per-beat contract (`script.schema.json`, Ch.5) |
| `primitive` | which library component renders it (closed set — §4) |
| `enter` / `exit` | a **named** animation + params `{delay,dur,easing}` from the closed library (§5) |
| `style` | **token refs** into the brand kit (font role, palette role, stroke) — never raw values, so the brand kit (ADR 0005 D9) stays the single source of truth |

**Two beat-composition patterns** cover all 8 archetypes:
- **beat-template** — one repeating region set reused per beat (`ranked_list`: one item card per
  rank, with an inter-beat transition).
- **fixed-scene** — regions persist across the beat arc (`head_to_head`: side_a/side_b/verdict).

A new `schemas/layout.schema.json` (sibling of `format.schema.json`, Ch.5) validates region names,
bbox bounds (within 0–1; z-conflicts flagged), animation names ∈ the library, and — at resolve
time — that **every `bind` field exists in that format's typed beat contract**. Authoring errors
**fail loud before render**, not as a garbled frame. This is what makes "add a format = data" safe.

### 4. The primitive library (closed set)

`MediaZone` · `TextCard` · `RankBadge` · `KaraokeCaption` · `DataVizSlot` · `CitationChip` ·
`BrandOverlay` · `CTABump`. A new **kind** of primitive is a code change to this library; *using*
one is data. `DataVizSlot` is the 01e renderer reused verbatim.

### 5. The animation / transition library (closed set)

Each animation is **one parameterized function of frame index** `t ∈ [0,dur]`, implemented **once**
in the `LayoutEngine`, referenced by name + params. Two kinds:

- **Region enter/exit:** `fade · tick-in · slide-in · count-up · riser-reveal · pop · karaoke`
  (`karaoke` is driven by the WhisperX word timings — ADR 0005 D4; `count-up` for numeric stats /
  data-viz).
- **Inter-beat transitions:** `cut · crossfade · swipe · slide-stack · whip`.

Each animation/transition **emits a synchronized SFX cue marker** into the manifest (whoosh on
swipe, tick per item, impact on reveal) — the ADR 0005 D6 / Stage 04 transition-SFX layer. Audio
and motion are **bound at resolve time**, not guessed downstream.

### 6. Inherited standard regions

The resolve step **injects** these into every layout, so a format declares only its *distinctive*
regions and consistency is guaranteed (DRY across the 8): `caption` (03 karaoke band) ·
`brand_lower_third` + logo bug (D9) · `citation` chip (YMYL on-screen cite, Ch.9) · `cta_bump`
(seeded mid-roll, D10, verified inside the safe rect by 05b) · loop-bridge + `end_card` (ADR 0006).

### 7. The two exemplar templates

Distinctive regions only (the §6 standard regions are injected). bbox in safe-zone-relative units.

**7a · `ranked_list` — beat-template (countdown)**

```
pattern: beat-template (one item per beat, N items, descending to #1)
inter_beat_transition: swipe(dir=left)                         # SFX cue: whoosh
escalation: final item (#1) overrides transition → riser-reveal  # SFX cue: impact
```

| region | bbox (0–1 safe) | z | primitive | bind | enter | style |
|---|---|---|---|---|---|---|
| `bg_media` | 0,0,1,1 | 0 | MediaZone | `item.media` | fade(dur=6) | — |
| `rank_badge` | 0.06,0.06,0.22,0.12 | 3 | RankBadge | `item.rank` | tick-in(delay=2) | palette.accent |
| `item_title` | 0.06,0.74,0.88,0.12 | 2 | TextCard | `item.title` | slide-in(dir=up,delay=4) | font.display |
| `item_stat` | 0.06,0.86,0.88,0.08 | 2 | TextCard | `item.stat` | count-up(delay=8) | font.numeric |

The rank badge `tick-in` fires the per-item tick SFX; numeric stats animate with `count-up`; the
#1 swaps the swipe for `riser-reveal` — the payoff escalation, **no special-case code** (just data
on the last beat).

**7b · `head_to_head` — fixed-scene (split-screen verdict)**

```
pattern: fixed-scene (side_a / side_b persist; verdict resolves at climax)
inter_beat_transition: whip                                    # between rounds; SFX cue: whoosh
```

| region | bbox (0–1 safe) | z | primitive | bind | enter | style |
|---|---|---|---|---|---|---|
| `side_a_media` | 0,0,1,0.5 | 0 | MediaZone | `side_a.media` | slide-in(dir=down) | — |
| `side_b_media` | 0,0.5,1,0.5 | 0 | MediaZone | `side_b.media` | slide-in(dir=up) | — |
| `vs_badge` | 0.38,0.44,0.24,0.12 | 4 | RankBadge | `static:"VS"` | pop(delay=6) | palette.accent |
| `side_a_label` | 0.06,0.06,0.6,0.08 | 2 | TextCard | `side_a.label` | fade | font.display |
| `side_b_label` | 0.06,0.86,0.6,0.08 | 2 | TextCard | `side_b.label` | fade | font.display |
| `stat_bars` | 0.1,0.40,0.8,0.20 | 3 | DataVizSlot | `round.metrics` | count-up(stagger) | palette.dataviz |
| `verdict` | 0.1,0.42,0.8,0.16 | 5 | TextCard | `verdict.text` | riser-reveal(delay=climax) | font.display |

`stat_bars` is the **01e DataVizSlot reused verbatim** — head_to_head's comparison bars *are*
data-viz in a region, the concrete payoff of the shared engine. `verdict` resolves at the climax.

Both inherit (untouched) the §6 standard regions and **reflow per-platform from the same data** via
the safe-zone insets (ADR 0005 D7).

### 8. Parameters

- **fps = 30.** Platform-native for TikTok/Reels/Shorts; karaoke word-cuts, rank ticks, riser
  reveals and the CTA bump read smoother than at 24 (motion-graphics frames are exactly where 24
  juddered). Cost is ~25% more frames to paint than 24 — paid on the CPU, not the GPU (next).
- **Chromium rasterization → CPU (7800X3D).** Headless-Chromium **GPU** raster inside the container
  is flaky **and non-deterministic** (driver-dependent pixel diffs), which would break the
  reproducible-by-design value (ADR 0009) and the golden-frame test (§10). CPU raster is
  pixel-identical across runs/machines, and ADR 0007 §4 already sizes the 16 threads for it. The
  GPU stays reserved for the model stages (never-co-resident, Ch.7).
- **Encode → NVENC (5070 Ti).** The genuine GPU use in Stage 05 is the **encode**, not the paint:
  CPU paints a PNG frame sequence → ffmpeg `h264_nvenc`/`hevc_nvenc` per platform. We hash on the
  **frame PNGs** (deterministic), not the mp4, so encoder variability never threatens the golden
  tests. This resolves ADR 0007's "how much GPU-Chromium helps" open item: **none — CPU raster is
  chosen for determinism; the GPU's render-time job is the encode.**

### 9. Throughput re-measurement method (to run in M2)

Stage 05 cost ≈ `frames (= duration_s × 30) × per-frame CPU paint + NVENC encode`. Measure, on the
real box, both duration classes — **reach** (20–35s → 600–1050 frames) and **monetization**
(61–90s → 1830–2700 frames) — × 3 platform cuts, using the two exemplars as fixtures. Deliverables:
per-stage wall-clock; confirmation that **Stage 05 (CPU+NVENC) overlaps the GPU model stages** —
the compositor for video *N* runs on the 7800X3D + NVENC while the GPU does diffusion for video
*N+1*, so it is **nearly free on the critical path** and *helps* the REVIEW T1 / ADR 0011 lane-fork
rather than re-opening it; and the revised end-to-end per-video figure folded into the **single
reconciliation** required by Ch.7 / open #9 (vs the ADR 0003 ~25 min baseline).

### 10. Determinism & testing

- **Render is `pure(manifest)`** — all seeded choices resolved upstream → identical manifest yields
  identical frames.
- **Golden-frame CI test:** render a committed fixture manifest, hash **sampled** frames (first /
  mid / last + the CTA-bump frame + the #1-reveal frame), compare to golden hashes. CPU raster is
  what makes this stable across machines. Plugs into the M0 golden-fixtures chain (ADR 0010).
- **Schema + bind validation** (§3) at the layout-author boundary and at resolve time.
- **Safe-zone assertion:** automated check that no region bbox (including the injected caption /
  CTA) projects outside the platform-safe rect for any of the 3 platforms.
- **Human spot-check:** the engine's studio/preview for authoring; each render emits a **contact
  sheet** (thumbnail grid of key beats) for fast review. Folds into 05x/05c, which already judge the
  rendered pixels (ADR 0008).
- **Fixtures = the two exemplars** — they double as the test fixtures for the renderer + library.

### 11. Scope — 2 of 8 now, 6 as data later

`ranked_list` + `head_to_head` are built now (a beat-template and a fixed-scene — the two patterns,
proving both the renderer and the library breadth). The remaining 6 archetypes (`myth_buster`,
`explainer`, `news_reaction`, `cautionary_tale`, `surprising_stat`, `how_to_steps`) are authored in
**M3** as **pure data** against the validated `layout.schema.json` — **no new code** unless one
needs a genuinely new primitive or animation, which is the only thing that should ever touch the
library again.

## Consequences

**Positive**
- ADR 0007's "add a format = data, not code" rule is now **enforceable** (schema + resolve-time
  bind validation), not aspirational.
- The renderer is engine-neutral on the `LayoutEngine` adapter, so the deferred engine/license lock
  (M2) is a contract implementation, not a redesign.
- Determinism is structural (`pure(manifest)` + CPU raster + PNG-hash goldens), satisfying ADR
  0009 reproducibility for the render stage.
- Stage 05 overlaps the GPU stages — a throughput *help*, not a new tax.

**Negative / costs**
- The closed library is a real up-front build (8 primitives + 12 named animations/transitions) —
  the M2/M3 visual-path cost ADR 0007 already flagged; this design scopes it but doesn't shrink it.
- A new schema (`layout.schema.json`) + the resolve step join the M0/contract surface.
- Only 2 of 8 templates are designed here; the other 6 carry authoring (not engineering) risk that
  the two patterns generalize — mitigated by choosing one of each pattern as the exemplars.

## Open (tracked) — narrows ADR 0007 open #8

- **Engine + license lock** (MIT-clean Playwright/Motion-Canvas vs Remotion-solo) — **unchanged**,
  deferred to M2.
- **The other 6 region specs** — authored as data in M3 (§11).
- **Run the throughput method** (§9) on the real box and fold into the Ch.7 / open #9 reconciliation.
- **Per-primitive style-token vocabulary** + the easing set — pinned with the brand kit (ADR 0005
  D9 residue, open #6).
