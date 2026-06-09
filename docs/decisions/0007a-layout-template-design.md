# ADR 0007a — Layout template design: region model, primitive & animation library, the two exemplars

- **Status:** Accepted (2026-06-09)
- **Elaborates:** [ADR 0007](0007-format-aware-layout-templates.md) — this is the design that
  fills ADR 0007's remaining open items for the layout layer. It does **not** re-open any ADR 0007
  decision; it makes them buildable. **Engine is Remotion** (ADR 0007 §4 D4, locked 2026-06-09 under
  the free ≤3-person terms); this design uses Remotion idioms (`<Composition>`, `<Sequence>`,
  `interpolate`/`spring`, Remotion Studio, `@remotion/renderer`) on top of the `LayoutEngine`
  adapter (ADR 0010), so a future tripwire-driven swap to the Playwright/Motion-Canvas fallback is
  an adapter re-implementation, not a redesign.
- **Resolves (ADR 0007 / spec Ch.10 open #8):** the **per-format region-spec model** + the **shared
  primitive and animation/transition libraries** (design + **2 of 8** exemplars built —
  `ranked_list`, `head_to_head`; the other 6 are data, M3, §11); **target fps = 30**;
  **GPU-Chromium vs pure-CPU → CPU raster + NVENC** (§8). A **throughput re-measurement method** is
  specified (§9), to be *run* on the box in M2.
- **Touches:** spec Ch.4 (05, 01a, 01e), Ch.5 (`layout.schema.json` + the typed beat contract),
  Ch.6 (the `layout` recipe), Ch.7 (throughput), Ch.10 (M2/M3 + open #8/#9).

## Context

ADR 0007 decided *that* every format owns a layout; it left *how a layout is expressed* open —
load-bearing, because it decides whether "adding a format is **data, not a code change**" (Ch.6)
holds. Three models were weighed: **per-format components** (most expressive, but add-a-format
becomes code and 8 components drift); a **pure-data DSL** (zero per-format code, but the expressive
ceiling is low and it reinvents the engine); and **hybrid — data regions + a closed primitive/
animation library** *(chosen)* — declarative `layout` data interpreted by one generic renderer over
a **closed** library. New **format = data**; new **kind** of primitive/animation = a library code
change. Only the hybrid keeps the data-not-code rule enforceable while leaving room for real motion.

## Decision

### 1. Hybrid model on the `LayoutEngine` adapter

A format's `layout` is **declarative data**. One generic Remotion `<Composition>` — the
`LayoutEngine` implementation — interprets it with **no per-format logic**: it iterates beats via
`<Sequence>`, places regions, mounts primitives, runs animations by name. The 8 layouts are data;
the renderer + libraries are the only code, shared verbatim with **01e data-viz** (a chart is a
`DataVizSlot` primitive in a region).

### 2. Engine & data flow — render is `pure(manifest)`

A deterministic, pure **resolve step** merges the format `layout` + typed per-beat data + WhisperX
word timings + brand kit + seeded slots (CTA bump D10, loop + end-card 0006) into a flat, fully
bound **`render_manifest.json`**, consuming the persisted `job.json` seed (ADR 0009). **Everything
stochastic is decided here**, so the Remotion render is a **pure function of the manifest** →
reproducible. The renderer paints frames; **per-platform deltas are manifest deltas** (safe-zone
insets + CTA verb/icon — same `<Composition>`, three manifests; the ADR 0005 D4 distinct cuts).

### 3. The region-spec schema (`layout.schema.json`)

A **region** carries: `name`; `bbox` in **grid + anchor units within the per-platform safe rect**
(§7a — *not* raw canvas pixels, so platform insets reflow automatically); `z`; `bind` (the typed
beat-field that feeds it — references the 00b contract, Ch.5); `primitive` (§4); `enter`/`exit`
(a **named** animation + params from §5); `style` (**token refs** into the brand kit — never raw
values, so the brand kit, ADR 0005 D9, stays the single source). Two beat-composition patterns
cover all 8: **beat-template** (one region set reused per beat — `ranked_list`) and **fixed-scene**
(regions persist across the arc — `head_to_head`).

`schemas/layout.schema.json` (sibling of `format.schema.json`) validates region/bbox/animation
names and — at resolve time — that **every `bind` exists in that format's typed beat contract**.
Authoring errors **fail loud before render**. This is what makes "add a format = data" safe.

### 4. The primitive library (closed — derived bottom-up from the 8 archetypes)

| primitive | role | key params | notes |
|---|---|---|---|
| `MediaZone` | media in a box | `fit` (cover/contain), `kenburns`, `mask` | full-bleed / half / quadrant — universal |
| `TextCard` | **all** styled text lockups | `role` (display/body/numeric/label), `align`, `plate`, `max_lines` | the workhorse: titles, labels, bullets, verdict, unpack, **and single animated numbers** (role=numeric + count-up) |
| `Badge` | number/glyph/short-text badge or stamp | `shape` (pill/circle/stamp), `content`, `accent` | **merges** rank # (`ranked_list`), VS (`head_to_head`), step # (`how_to_steps`), TRUE/FALSE stamp (`myth_buster`) — one primitive, not four |
| `KaraokeCaption` | word-timed caption band | `words` (WhisperX), `safe_anchor` | distinct: per-word highlight (D4), `.ass` semantics |
| `DataVizSlot` | 01e charts / bars / multi-series | `viz` (01e component ref) | **reserved for real charts** — a lone number is `TextCard`+count-up, not this |
| `CitationChip` | YMYL on-screen citation | `source_ref` | `TextCard`-family, **named** because 05b binds the "sources cited" check to it (Ch.9) |
| `CTABump` | mid-roll engagement bump | `verb`, `icon`, `platform` | `TextCard`+icon+timing, **named** because 05b whitelists it by region name (D10) |
| `BrandOverlay` | logo bug + lower-third | brand-kit driven | always-on brand (D9) |

A new **kind** of primitive is a code change; *using* one is data. `Badge` generalizing the four
badge cases is the decomposition that keeps the set from growing per-format. `CitationChip`/
`CTABump` are `TextCard`-family but kept named only as **semantic anchors a downstream gate binds
to** — the test for "deserves its own name."

### 5. The animation / transition library (closed — *motion* separated from *feel*)

Each is **one parameterized function of frame index** `t ∈ [0,dur]`, implemented once via Remotion
`interpolate`/`spring`, referenced by name + params. "Feel" variations are **params + an SFX cue**,
not new names.

- **Enter/exit (6):** `fade · slide-in(dir) · pop(overshoot) · count-up · riser-reveal · karaoke`
  — `pop` covers the old *tick-in* (= `pop` + tick SFX); `karaoke` is WhisperX-driven (D4);
  `count-up` is the numeric tween.
- **Transitions (4):** `cut · crossfade · swipe(dir) · slide-stack` — `swipe` covers the old *whip*
  (= `swipe` + blur + speed).
- **Params:** `{delay, dur, easing, dir, overshoot, sfx_cue}`; `easing` ∈ a small closed set
  `{linear, ease-out, ease-in-out, spring(stiffness,damping)}`.
- Each animation/transition **emits a synchronized SFX cue marker** into the manifest (whoosh on
  swipe, tick on a `pop`-badge, impact on `riser-reveal`) — bound at resolve time to the Stage 04
  transition-SFX layer (ADR 0005 D6).
- *(Later hook: the treatment's energy curve (ADR 0005) can drive default param intensity —
  high-energy beat → faster `dur`, more `overshoot`, louder cue. Deferred.)*

### 6. Inherited standard regions

The resolve step **injects** these into every layout, so a format declares only its *distinctive*
regions (DRY, consistency guaranteed): `caption` (03 band) · `brand_lower_third` + logo bug (D9) ·
`citation` (YMYL, Ch.9) · `cta_bump` (seeded mid-roll, D10, verified in-safe-rect by 05b) ·
loop-bridge + `end_card` (ADR 0006).

### 7a. Coordinate system — a grid inside the safe rect (replaces raw bboxes)

- **Canvas** 1080×1920 (Ch.4). **Per-platform safe insets** (fractions of canvas, tunable config;
  defaults to validate in M2): TikTok `{t .10, r .12, b .20, l .04}`, YouTube Shorts
  `{t .08, r .06, b .16, l .04}`, Instagram Reels `{t .10, r .10, b .18, l .04}` (D7).
- The resolve step computes `safe_rect = canvas − insets`, then projects each region's
  **`bbox` (0–1 of `safe_rect`)** to pixels — so one layout reflows across all 3 platforms.
- Horizontally regions snap to a **12-column grid**; vertically to **named anchors** (0–1 of
  `safe_rect`, tunable): `badge` .04–.18 · `headline` .26–.40 · `media` .00–1.0 (z0) ·
  `stat` .42–.52 · `caption` .82–.94. The exemplars below read in these terms. *(This corrects an
  earlier draft that placed the `ranked_list` title at the bottom, contradicting ADR 0007's sketch
  of title ≈ upper-third over the media zone.)*

### 7b. The two exemplar templates

Distinctive regions only (§6 standard regions injected). `bbox` as `{col,colspan | y,h}` of the
safe rect.

**`ranked_list` — beat-template (countdown)** · transition `swipe(left)` (whoosh); #1 overrides →
`riser-reveal` (impact).

| region | bbox (safe-rect) | z | primitive | bind | enter |
|---|---|---|---|---|---|
| `bg_media` | col1–12 · y0–1.0 | 0 | MediaZone(kenburns) | `item.media` | fade |
| `rank_badge` | col1–3 · `badge` | 3 | Badge(shape=circle) | `item.rank` | pop+tickSFX |
| `item_title` | col1–12 · `headline` | 2 | TextCard(role=display) | `item.title` | slide-in(up) |
| `item_stat` | col1–12 · `stat` | 2 | TextCard(role=numeric) | `item.stat` | count-up |

**`head_to_head` — fixed-scene (split-screen verdict)** · transition `swipe(fast,blur)` between
rounds.

| region | bbox (safe-rect) | z | primitive | bind | enter |
|---|---|---|---|---|---|
| `side_a_media` | col1–12 · y0–.5 | 0 | MediaZone | `side_a.media` | slide-in(down) |
| `side_b_media` | col1–12 · y.5–1.0 | 0 | MediaZone | `side_b.media` | slide-in(up) |
| `vs_badge` | col5–8 · y.44–.56 | 4 | Badge(shape=stamp,"VS") | `static` | pop |
| `side_a_label` | col1–8 · y.04–.12 | 2 | TextCard(role=label) | `side_a.label` | fade |
| `side_b_label` | col1–8 · y.88–.96 | 2 | TextCard(role=label) | `side_b.label` | fade |
| `stat_bars` | col2–11 · y.40–.60 | 3 | DataVizSlot | `round.metrics` | count-up(stagger) |
| `verdict` | col2–11 · y.42–.58 | 5 | TextCard(role=display) | `verdict.text` | riser-reveal |

`stat_bars` is the **01e DataVizSlot reused verbatim**. Both inherit §6 and reflow per-platform.

### 8. Parameters

- **fps = 30** — platform-native; karaoke cuts, badge pops, riser reveals and the CTA bump read
  smoother than 24 (where motion-graphics judder). ~25% more frames than 24 — paid on CPU (next).
- **Rasterization → CPU/SwiftShader on the 7800X3D.** GPU-Chromium (ANGLE/EGL) is faster but
  **non-deterministic** across driver/hardware. The reasoned middle path — *GPU raster + pinned
  driver + tolerance hashing* — was weighed and **rejected**: it reintroduces the host-driver-drift
  fragility Ch.7 names the #1 "doesn't-work-on-my-box" risk, and tolerance hashing weakens
  regression detection (§10). CPU raster is pixel-identical; ADR 0007 §4 already sizes the 16
  threads for it.
- **Encode → NVENC on the 5070 Ti** (`h264_nvenc`/`hevc_nvenc`) — the genuine GPU use in Stage 05.
  CPU paints a PNG sequence → ffmpeg NVENC per platform; we hash the **frame PNGs**, not the mp4.
- **Tripwire:** revisit GPU-raster only if the M2 measurement (§9) shows paint is the Stage-05
  bottleneck — unlikely, since Stage 05 overlaps the GPU lane.
- This resolves ADR 0007's "how much GPU-Chromium helps" item: **none worth its determinism cost.**

### 9. Throughput re-measurement method (run in M2)

Stage 05 cost ≈ `frames (= duration_s × 30) × CPU paint/frame + NVENC encode`. Measure on the box,
both lanes — **reach** (20–35s → 600–1050 frames) and **monetization** (61–90s → 1830–2700 frames)
— × 3 platform cuts, the two exemplars as fixtures. Deliver: per-stage wall-clock; confirmation
that **Stage 05 (CPU+NVENC) overlaps the GPU model stages** (compositor for video *N* while the GPU
diffuses *N+1*) so it is near-free on the critical path and *helps* the ADR 0011 lane-fork; and the
revised per-video figure folded into the **single reconciliation** Ch.7 / open #9 requires (vs the
ADR 0003 ~25 min baseline).

### 10. Determinism & testing

- **Render is `pure(manifest)`** → identical manifest yields identical frames.
- **Golden-frame CI:** render a fixture manifest, **exact-hash** sampled frames (first / mid / last
  + CTA-bump + #1-reveal), compare to goldens. CPU raster makes this stable across machines; plugs
  into the M0 golden-fixtures chain (ADR 0010).
- **Schema + bind validation** (§3) at author time and resolve time.
- **Safe-zone assertion:** no region bbox (incl. injected `caption`/`cta_bump`) projects outside the
  platform safe rect for any of the 3 platforms.
- **Human spot-check:** Remotion Studio for authoring; each render emits a **contact sheet**
  (key-beat thumbnail grid). Folds into 05x/05c, which judge the rendered pixels (ADR 0008).
- **Fixtures = the two exemplars.**

### 11. Scope — 2 of 8 now, 6 as data later

`ranked_list` (beat-template) + `head_to_head` (fixed-scene) prove both patterns + the library
breadth. The other 6 (`myth_buster`, `explainer`, `news_reaction`, `cautionary_tale`,
`surprising_stat`, `how_to_steps`) are authored in **M3 as pure data** against the validated
`layout.schema.json` — **no new code** unless one needs a genuinely new primitive/animation.

## Consequences

**Positive** — the data-not-code rule is now *enforceable* (schema + resolve-time bind validation);
`Badge` + the *motion-vs-feel* split keep the closed libraries small (8 primitives, 10 animations);
determinism is structural (`pure(manifest)` + CPU raster + exact PNG goldens, ADR 0009); Stage 05
overlaps the GPU lane (a throughput help); the coordinate grid removes invented numbers and reflows
per-platform from one layout.

**Negative / costs** — the closed libraries are still a real up-front build (the M2/M3 visual-path
cost ADR 0007 flagged); a new schema + resolve step join the contract surface; only 2 of 8 are
designed here, so the other 6 carry *authoring* (not engineering) risk that the two patterns
generalize — mitigated by picking one of each pattern as the exemplars.

## Open (tracked) — narrows ADR 0007 open #8

- **The other 6 region specs** — authored as data in M3 (§11).
- **Run the throughput method** (§9) and fold into the Ch.7 / open #9 reconciliation.
- **Validate the default safe insets + grid anchors** (§7a) on real platform UIs in M2.
- **Per-`role` style-token vocabulary + the easing intensities** — pinned with the brand kit
  (ADR 0005 D9 residue, open #6); the energy-curve→param hook (§5) is post-M3.
- *(Engine is no longer open — Remotion locked, ADR 0007 §4 D4; Playwright/Motion-Canvas remain the
  tripwire fallback.)*
