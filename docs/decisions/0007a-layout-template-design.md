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
- **Touches (synced in lockstep):** spec Ch.4 (05, 01a, 01e), Ch.5 (`layout.schema.json` + the typed
  beat contract — whose `script.schema.json` field list this ADR **extends** with
  `stat?`/`round[]`/sub-shapes, §7b), Ch.6 (the `layout` recipe), Ch.7 (throughput), Ch.10 (M2/M3 +
  open #8/#9). The `LayoutEngine` render signature is updated to `render(render_manifest)` (§2) in
  ADR 0010 §D3 + ADR 0012 §6, and the beat contract in ADR 0007 D3 + spec Ch.5.

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

A deterministic, pure **resolve step** merges the format `layout` + typed per-beat data + **the
visual lane's chosen per-beat assets (`assets.json` — MediaZone regions resolve to the selected
clip's path, not the `media_query` string)** + WhisperX
word timings **(threaded into the injected `KaraokeCaption` region's `words` param, not only into
scene spans)** + brand kit + seeded slots (CTA bump D10, loop + end-card 0006) into a flat, fully
bound **`render_manifest.json`**, consuming the persisted `job.json` seed (ADR 0009). **Everything
stochastic is decided here**, so the Remotion render is a **pure function of the manifest** →
reproducible. The renderer paints frames; **per-platform deltas are manifest deltas** (safe-zone
insets + CTA verb/icon — same `<Composition>`, three manifests; the ADR 0005 D4 distinct cuts).
*(Honesty note, ADR 0015: production renders run in the WSL2 venv, not the pinned CI image — so
production output is SSIM-class vs the goldens; the byte-hash tripwire is a CI regression guard.)*

This **refines the ADR 0010 D3 seam** from `render(format_layout, structured_data, brand_kit) →
frames` to `render(render_manifest) → frames`: resolve is the new pre-engine step that merges those
three inputs (plus timings + seed) into the manifest, so the engine carries *no* unresolved or
stochastic input. The manifest gets its own `render_manifest.schema.json` (**authored in M2**
alongside `layout.schema.json` — M0 deferred the compositor's contracts, so both land in the M2
compositor milestone, not M0) — the resolve step's output contract, sibling to `layout.schema.json`. It carries **projected pixel
bboxes** (post-grid, §7a) plus resolved style values and the SFX/marker frame-indices, so the
renderer is pure painting with **no geometry of its own**.

### 3. The region-spec schema (`layout.schema.json`)

A **region** carries: `name`; `bbox` in **grid + anchor units within the per-platform safe rect**
(§7a — *not* raw canvas pixels, so platform insets reflow automatically); `z`; `bind` (the typed
beat-field that feeds it — references the 00b contract, Ch.5); `primitive` (§4); `enter`/`exit`
(a **named** animation + params from §5); `style` (**token refs** into the brand kit — never raw
values, so the brand kit, ADR 0005 D9, stays the single source). Two beat-composition patterns
cover all 8: **beat-template** (one region set reused per beat — `ranked_list`) and **fixed-scene**
(regions persist across the arc — `head_to_head`).

`schemas/layout.schema.json` (sibling of `format.schema.json`) validates region/bbox/animation
names and — at resolve time — that **every `bind` exists in that format's typed beat contract**
(the literal `bind: "static"` case is exempt — content then comes from the primitive's `content`
param). Authoring errors **fail loud before render**. This is what makes "add a format = data" safe.

The region object skeleton (enums inlined, so the schema is writable without reverse-engineering the
tables below): `name: string` · `bbox: {colA: int(1–12), colB: int(1–12)` **inclusive** (matches the
§7b `colA–colB` tables)`, y: number(0–1), h: number(0–1)}` *or* `{colA, colB, anchor}` where
`anchor ∈` the §7a default anchors **∪ the format's own `anchors{}`** map · `z: int` ·
`bind: string` (dotted beat-field path, or `"static"`) · `primitive: {type: enum(§4), params: {…}}` ·
`enter`/`exit: {name: enum(§5), params: {delay, dur, easing, dir?, overshoot?, sfx_cue?}}` ·
`style: {<prop>: "<dotted-token-path>"}` (props open, paths resolved against the brand kit). Roles
`{display, body, numeric, label}`, shapes `{pill, circle, stamp}`, `fit {cover, contain}`.

### 4. The primitive library (closed — derived bottom-up from the 8 archetypes)

| primitive | role | key params | notes |
|---|---|---|---|
| `MediaZone` | media in a box | `fit` (cover/contain), `kenburns(from_rect,to_rect)`, `mask(shape\|source)` | full-bleed / half / quadrant — universal |
| `TextCard` | **all** styled text lockups | `role` (display/body/numeric/label), `content` (static text; else from `bind`), `align`, `plate(fill,radius,pad)`, `max_lines` | the workhorse: titles, labels, bullets, verdict, unpack, **and single animated numbers** (role=numeric + count-up) |
| `Badge` | number/glyph/short-text badge or stamp | `shape` (pill/circle/stamp), `content`, `accent` | **merges** rank # (`ranked_list`), VS (`head_to_head`), step # (`how_to_steps`), TRUE/FALSE stamp (`myth_buster`) — one primitive, not four |
| `KaraokeCaption` | word-timed caption band | `words` (WhisperX), `safe_anchor` | distinct: per-word highlight (D4), `.ass` semantics |
| `DataVizSlot` | 01e charts / bars / multi-series | `viz` (01e component ref) | **reserved for real charts** — a lone number is `TextCard`+count-up, not this |
| `CitationChip` | YMYL on-screen citation | `source_ref` | `TextCard`-family, **named** because 05b binds the "sources cited" check to it (Ch.9) |
| `CTABump` | mid-roll engagement bump | `verb`, `icon`, `platform` | `TextCard`+icon+timing, **named** because 05b whitelists it by region name (D10) |
| `BrandOverlay` | logo bug + lower-third | brand-kit driven | always-on brand (D9) |

A new **kind** of primitive is a code change; *using* one is data. `Badge` generalizing the four
badge cases is the decomposition that keeps the set from growing per-format. A primitive earns its
own name by **one of**: a downstream gate binds to it (`CitationChip`→05b sources check,
`CTABump`→05b region whitelist, D10), a distinct render mechanism (`KaraokeCaption` `.ass`,
`BrandOverlay` always-on), or an external component (`DataVizSlot`→01e) — not styling alone.

*M3 decomposition to pin before authoring `explainer`:* its **worked-through** number (a
sequenced/annotated reveal — e.g. $1k→$2k→$4k with labels) sits between `DataVizSlot` (reserved for
real charts) and a lone `TextCard`+count-up. Resolve it as either a `count-up` with step params or a
`DataVizSlot` viz variant — and state which is data vs code — before M3 (Open, §11). This call also
decides whether `DataVizSlot` admits **non-chart sequenced reveals** at all, so it is the boundary
decision for `surprising_stat`/`cautionary_tale` too, not just `explainer`.

### 5. The animation / transition library (closed — *motion* separated from *feel*)

Each is **one parameterized function of frame index** `t ∈ [0,dur]`, implemented once via Remotion
`interpolate`/`spring`, referenced by name + params. "Feel" variations are **params + an SFX cue**,
not new names.

- **Enter/exit (6):** `fade · slide-in(dir) · pop(overshoot) · count-up(from,to) · riser-reveal(rise,impact)
  · karaoke` — `pop` covers the old *tick-in* (= `pop` + tick SFX); `karaoke` is WhisperX-driven
  (D4); `count-up` is the numeric tween; `riser-reveal` rises `rise` (fraction of `safe_rect`) into
  place with an `impact` settle at its peak (the #1-reveal golden marker, §10).
- **Transitions (4):** `cut · crossfade · swipe(dir) · slide-stack(dir)` — `swipe` covers the old
  *whip* (= `swipe` + blur + speed).
- **Params:** `{delay, dur, easing, dir, overshoot, sfx_cue}`; `easing` ∈ named presets
  `{linear, ease-out, ease-in, ease-in-out, spring(stiffness,damping)}` **∪ `cubic-bezier(x1,y1,
  x2,y2)`** as the escape hatch — keeps determinism while leaving room for the energy-curve hook
  below without re-opening the set. (`spring` params are Remotion-defined; a fallback engine
  re-derives its goldens — see Consequences on the animation library as the real portability cost. A
  **canonical bezier evaluator** — fixed sample count + rounding — is pinned in the toolchain image
  so author-dialed curves stay golden-reproducible across an engine swap, not just the named presets.)
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
- **Projection is unambiguous:** columns evenly divide `safe_rect` width with **zero grid gutter**
  (intra-region spacing is the primitive's own `style` padding); `colA–colB` is **inclusive**
  (so `col1–3` spans 3 columns, `col5–8` spans 4). Vertical position is **either** a named anchor
  **or** a literal `y–h` fraction of `safe_rect`; a named anchor expands to its fraction pair at
  resolve. The named anchors are **tunable defaults a format may extend**, not a closed list — so a
  vertical stack (`how_to_steps`) or narrative beat (`cautionary_tale`) adds anchors rather than
  silently falling back to raw `y`. A format declares custom anchors **in its own `layout` data** —
  an `anchors: {name: [y,h]}` map the resolve step merges over the §7a defaults — so anchor-extension
  is **format-local data, not a `layout.schema.json`/shared-code change** (keeping the data-not-code
  rule intact; the schema validates `anchor ∈ defaults ∪ that map`, §3).

### 7b. The two exemplar templates

Distinctive regions only (§6 standard regions injected). `bbox` as `{col,colspan | y,h}` of the
safe rect.

**`ranked_list` — beat-template (countdown)** · transition `swipe(left)` (whoosh); #1 overrides →
`riser-reveal` (impact).

| region | bbox (safe-rect) | z | primitive | bind | enter |
|---|---|---|---|---|---|
| `bg_media` | col1–12 · y0–1.0 | 0 | MediaZone(kenburns) | `item.media_query` | fade |
| `rank_badge` | col1–3 · `badge` | 3 | Badge(shape=circle) | `item.rank` | pop+tickSFX |
| `item_title` | col1–12 · `headline` | 2 | TextCard(role=display) | `item.title` | slide-in(up) |
| `item_stat` | col1–12 · `stat` | 2 | TextCard(role=numeric) | `item.stat` | count-up |

**`head_to_head` — fixed-scene (split-screen verdict)** · transition `swipe(fast,blur)` between
rounds.

| region | bbox (safe-rect) | z | primitive | bind | enter |
|---|---|---|---|---|---|
| `side_a_media` | col1–12 · y0–.5 | 0 | MediaZone | `side_a.media_query` | slide-in(down) |
| `side_b_media` | col1–12 · y.5–1.0 | 0 | MediaZone | `side_b.media_query` | slide-in(up) |
| `vs_badge` | col5–8 · y.44–.56 | 4 | Badge(shape=stamp,"VS") | `static` | pop |
| `side_a_label` | col1–8 · y.04–.12 | 2 | TextCard(role=label) | `side_a.label` | fade |
| `side_b_label` | col1–8 · y.88–.96 | 2 | TextCard(role=label) | `side_b.label` | fade |
| `stat_bars` | col2–11 · y.40–.60 | 3 | DataVizSlot | `round.metrics` | count-up(stagger) |
| `verdict` | col2–11 · y.42–.58 | 5 | TextCard(role=display) | `verdict.text` | riser-reveal |

`stat_bars` is the **01e DataVizSlot reused verbatim**. Both inherit §6 and reflow per-platform.

These exemplars **pin — and *extend* — the ADR 0007 D3 beat contract** (the "real contract change
(Ch.5)" D3 itself flagged, having given the fields only as "e.g."): `ranked_list` items carry
`{rank, title, body, media_query, stat?}`; `head_to_head` carries `{side_a, side_b, verdict,
round[]}` with `side_*: {media_query, label}`, `verdict: {text}`, `round: {metrics}`. The **`stat?`,
`round[]` and the sub-shapes are additions** beyond ADR 0007 D3 / spec Ch.5 `script.schema.json`'s
original `{rank,title,body,media_query}` / `{side_a,side_b,verdict}` — both now **updated in lockstep**,
without which resolve-time `bind` validation (§3) would reject these exemplars.
Every `bind` above resolves against this contract; `vs_badge` uses `bind: "static"` (literal "VS"
via the `content` param), the documented exempt case.

### 8. Parameters

- **fps = 30** — platform-native; karaoke cuts, badge pops, riser reveals and the CTA bump read
  smoother than 24 (where motion-graphics judder). ~25% more frames than 24 — paid on CPU (next).
- **Rasterization → CPU/SwiftShader on the 7800X3D.** GPU-Chromium (ANGLE/EGL) is faster but
  **non-deterministic** across driver/hardware. The reasoned middle path — *GPU raster + pinned
  driver + tolerance hashing* — was weighed and **rejected**: it reintroduces the host-driver-drift
  fragility Ch.7 names the #1 "doesn't-work-on-my-box" risk, and tolerance hashing weakens
  regression detection (§10). CPU raster removes the *hardware/driver* drift — but it is only
  **bit-identical within a pinned toolchain image** (Remotion + Chromium/Skia + FreeType/HarfBuzz +
  fontconfig and the bundled font set, all locked by digest): font shaping/hinting and even PNG
  encoding still vary across freetype/libc/font versions, and ADR 0013 runs raster in WSL2 on the
  box but in Linux containers elsewhere. So goldens are rendered — and only regenerated — **inside
  that one image** (CI or a local `docker run` of it; the bare WSL2 box can't match the byte-hash,
  §10) and exact-hash is an *in-image regression tripwire*, not a cross-host guarantee. GPU raster is
  rejected because it adds driver drift *on top of* the toolchain drift we already pin away — strictly
  more nondeterminism for no determinism we keep. ADR 0007 §4 already sizes the 16 threads for CPU.
- **Encode → NVENC on the 5070 Ti** (`h264_nvenc`/`hevc_nvenc`) — the genuine GPU use in Stage 05.
  CPU paints a PNG sequence → ffmpeg NVENC per platform; we hash the **frame PNGs**, not the mp4.
- **Tripwire:** revisit GPU-raster only if the M2 measurement (§9) shows CPU paint is the Stage-05
  bottleneck *or* starves the audio lane (ADR 0011) — to be **confirmed by §9, not assumed**; and
  drop fps 30→24 (the cheaper dial) before abandoning CPU raster.
- This resolves ADR 0007's "how much GPU-Chromium helps" item: **none worth its determinism cost.**

### 9. Throughput re-measurement method (run in M2)

Stage 05 cost ≈ `frames (= duration_s × 30) × CPU paint/frame + NVENC encode`. Measure on the box,
both lanes — **reach** (20–35s → 600–1050 frames) and **monetization** (61–90s → 1830–2700 frames)
— × 3 platform cuts, the two exemplars as fixtures, measured at the **per-day N-video total**, not a
single video. Deliver: per-stage wall-clock; a **published ms/frame paint target and a fail
threshold** (if Stage-05 CPU paint exceeds X% of the GPU-lane wall-clock *or* starves the audio
lane — against ADR 0011's open lane-fork resource bound — the GPU-raster tripwire §8 fires; fps
30→24 first); confirmation that **Stage-05 CPU paint of video *N* pipelines against GPU diffusion of
video *N+1* across the batch** (the ADR 0011 D1 lane-fork generalized across videos; #7 NVENC
pipelining is the encode sub-case) — i.e. near-free on the *batch* critical path, **not** the per-video one
(per-video paint sits on *N*'s own path); and the revised per-video figure folded into the **single
reconciliation** Ch.7 / open #9 requires (vs the ~25 min baseline ADR 0005 carries from ADR 0003).

### 10. Determinism & testing

- **Render is `pure(manifest)`** → identical manifest yields identical frames.
- **Golden-frame CI:** a **separate lane** from the GPU-less fake-DAG (ADR 0012 §7) — it
  *live-renders* a fixture manifest **inside the pinned toolchain image (§8)**, **CPU-only** (PNG
  frames, **no NVENC/GPU**, so it still needs no GPU runner), and **exact-hashes** sampled frames —
  `first=0`, `mid=floor(total/2)`, `last`, plus the **CTA-bump enter-complete** and
  **#1 `riser-reveal` peak** frames (emitted as named marker frame-indices in the manifest, so the
  sample set is deterministic) — against goldens. **Goldens are authored and regenerated *only* via
  that image** (in CI, or a local `docker run` of it); the bare WSL2 dev box (ADR 0013) is a
  *cross-host* and can never match the byte-exact hash — locally it gets an **advisory per-frame SSIM
  check (≥ 0.99), not a blocking gate**. Exact-hash-in-image is the gate; SSIM is the eyeball aid.
  Plugs into the M0 golden-fixtures chain (ADR 0010).
- **Schema + bind validation** (§3) at author time and resolve time.
- **Safe-zone assertion:** no region bbox (incl. injected `caption`/`cta_bump`) projects outside the
  platform safe rect for any of the 3 platforms.
- **Human spot-check:** Remotion Studio for authoring; each render emits a **contact sheet**
  (key-beat thumbnail grid). Folds into the rendered-pixel vision pass (ADR 0008) — the spec's
  `05x`/`05c` gates (Ch.4).
- **Fixtures = the two exemplars.**

### 11. Scope — 2 of 8 now, 6 as data later

`ranked_list` (beat-template) + `head_to_head` (fixed-scene) prove both patterns + the library
breadth. The other 6 (`myth_buster`, `explainer`, `news_reaction`, `cautionary_tale`,
`surprising_stat`, `how_to_steps`) are authored in **M3 as pure data** against the validated
`layout.schema.json` — **no new code** unless one needs a genuinely new primitive/animation.

## Consequences

**Positive** — the data-not-code rule is now *enforceable* (schema + resolve-time bind validation);
`Badge` + the *motion-vs-feel* split keep the closed libraries small (8 primitives, 10 animations);
determinism is structural (`pure(manifest)` + CPU raster **within a pinned toolchain image** + exact
PNG goldens, ADR 0009); Stage 05 paint pipelines against GPU diffusion **across the batch** (a
throughput help, to be confirmed by §9); the coordinate grid removes invented numbers and reflows
per-platform from one layout.

**Negative / costs** — the closed libraries are still a real up-front build (the M2/M3 visual-path
cost ADR 0007 flagged); a new schema + resolve step join the contract surface; only 2 of 8 are
designed here, so the other 6 carry *authoring* (not engineering) risk that the two patterns
generalize — mitigated by picking one of each pattern as the exemplars. The **animation library is
written in Remotion idioms** (`interpolate`/`spring`), so a tripwire swap to the Playwright/
Motion-Canvas fallback re-implements those 10 functions to stay golden-identical — the adapter keeps
the *manifest* engine-agnostic, not the library; that library is the real portability cost. And
golden determinism is bought with **toolchain-image pinning** (§8): every Chromium/freetype/font
bump is a deliberate, goldens-regenerated event, not a free upgrade.

## Open (tracked) — narrows ADR 0007 open #8

- **The other 6 region specs** — authored as data in M3 (§11); pin `explainer`'s worked-through
  number (`count-up`-steps vs `DataVizSlot` variant, §4) *before* authoring it.
- **Run the throughput method** (§9) and fold into the Ch.7 / open #9 reconciliation — including the
  published ms/frame target + fail threshold, not just wall-clock.
- **Validate the default safe insets + grid anchors** (§7a) on real platform UIs in M2.
- **Per-`role` style-token vocabulary + the easing intensities** — pinned with the brand kit
  (ADR 0005 D9 residue, open #6); the energy-curve→param hook (§5) is post-M3.
- *(Engine is no longer open — Remotion locked, ADR 0007 §4 D4; Playwright/Motion-Canvas remain the
  tripwire fallback.)*
