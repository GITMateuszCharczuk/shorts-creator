# M2 — Visuals (01a–01e) + Format-Aware Compositor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the real visual lane (`01a` stock + `01b` FLUX + `01c` LTX + `01d` upscale/restore + `01e` data-viz) and replace M1's ffmpeg interim `05` with the **format-aware Remotion compositor** — the deterministic resolve→`render_manifest`→render pipeline (ADR 0007/0007a) — so output stops "looking obviously AI" and the finance signature visual (animated data-viz) exists.

**Architecture:** Visual stages are M0 `@stage` `run(ctx)` functions that are thin HTTP clients to the host ComfyUI (FLUX/LTX/ESRGAN/RIFE/GFPGAN) behind the M0 `ModelBackend` Protocol, plus a licensed-stock client. The picture is chosen by **CLIP relevance ranking + cross-video dedup**, with a deterministic **per-region fallback ladder** (stock → AI → branded card) so prominent slots never ship a mismatched clip. Stage `05` becomes a pure **resolve step** that merges `layout.schema` + the script's typed per-beat data + brand kit + word timings + seed into a flat `render_manifest.json`, rendered as a **pure function** by a **Remotion** `LayoutEngine` (CPU rasterization @30fps in a pinned toolchain image), then encoded with `h264_nvenc`. CI exercises every pure piece with fixtures; GPU/Remotine calls are `@pytest.mark.integration`.

**Tech Stack:** Python 3.12 + the M0/M1 toolchain; `open-clip-torch` (relevance, host-only), `httpx` (ComfyUI), `Pillow`/`numpy` (image ops + SSIM), and a **Node/TypeScript Remotion project** (`remotion/`) invoked from Python via the Remotion CLI. NVENC via `ffmpeg -c:v h264_nvenc`.

**Decisions made here (spec left open; pinned for M2):**
- **CLIP relevance model: `open-clip` ViT-B/32 (laion2b_s34b_b79k).** Small, fast on the 5070 Ti, strong enough for beat↔image similarity; bigger ViT-L is deferred A/B (ADR 0005 open). Behind a `ClipRanker` so the model id is a config swap.
- **Data-viz tech (01e): Remotion**, the *same* engine as the compositor (ADR 0007 "one engine, shared by 05 and 01e"). Rejected matplotlib/Plotly→frames: it would be a second rendering stack to maintain and wouldn't share the brand-kit/animation libraries. So 01e and 05 share `remotion/` components.
- **Determinism bar (ADR 0007a §1/§9):** in the **pinned toolchain image**, the CPU raster of a fixed manifest is asserted **byte-identical** (sha256 of frame PNGs) as a regression tripwire; on any other host the test asserts **SSIM ≥ 0.99** (advisory, not a gate). The golden test auto-detects the pinned image via an env stamp.
- **`layout.schema.json` is authored here** (M0 deferred it); M2 ships the `ranked_list` + `head_to_head` region specs as data (the ADR 0007a exemplars). The other 6 formats are M3. The region model follows ADR 0007a §3/§4/§7 **verbatim**: inclusive `colA–colB`, vertical = named-anchor **or** `{y,h}` fraction, format-extensible `anchors{}`, the **8-primitive** enum (`MediaZone/TextCard/Badge/KaraokeCaption/DataVizSlot/CitationChip/CTABump/BrandOverlay`), and `bind:"static"` (+ `primitive.params.content`).
- **`render_manifest.schema.json` is authored here too** — ADR 0007a §2 nominally said "authored M0," but M0 deferred the compositor, so both compositor contracts land in M2. `resolve()`'s output validates against it.
- **Generative-stage cache keys include `model_id + graph_version`** (ADR 0010 D4 / 0012 §1) so a model/graph bump is a miss, never a stale hit.

---

## File Structure

```
schemas/layout.schema.json                # NEW (M2): the format's layout recipe (ADR 0007a)
formats/ranked_list/layout.json           # NEW: ranked_list region spec (data)
formats/head_to_head/layout.json          # NEW: head_to_head region spec (data)
shared/adapters/real.py                    # MODIFY: add ComfyUIBackend (generate_image/img2vid + restore)
shared/visual/
  __init__.py
  clip.py                                 # ClipRanker: score/rank candidates by beat similarity
  dedup.py                                # cross-video dedup (perceptual hash + ledger)
  fallback.py                             # per-region fallback-ladder decision (pure)
  stock.py                                # licensed-stock client + provenance records
shared/layout/
  __init__.py
  schema_load.py                          # load + validate a format's layout.json
  resolve.py                              # resolve(layout, beat_data, brand_kit, timings, seed) -> render_manifest
  bind.py                                 # bind-validation: every region bind exists in the beat contract
  remotion.py                             # Python<->Remotion bridge (write manifest, invoke CLI, collect frames)
  encode.py                               # frames -> h264_nvenc mp4
remotion/                                  # Node/TS Remotion project (the LayoutEngine + 01e charts)
  package.json  remotion.config.ts  src/index.ts  src/Root.tsx  src/Manifest.tsx
  src/primitives/{Text,Image,Chart,Card,Badge}.tsx
stages/s01a_stock/{stage.py,manifest.json}
stages/s01b_imagegen/{stage.py,manifest.json}
stages/s01c_img2vid/{stage.py,manifest.json}
stages/s01d_upscale/{stage.py,manifest.json}
stages/s01e_dataviz/{stage.py,manifest.json}
stages/s05_render/{stage.py,manifest.json}   # REPLACE M1 interim: resolve -> Remotion -> nvenc
tests/
  fixtures/m2/
    layout_ranked_list.json  beat_data_ranked_list.json  brand_kit.json
    render_manifest_golden.json           # the resolved manifest the determinism test renders
    frames_golden/                        # sha256-pinned PNGs (pinned-image regression tripwire)
    clip_candidates/                      # tiny images + a beat to rank
  test_layout_schema.py  test_clip.py  test_dedup.py  test_fallback.py
  test_resolve.py  test_bind.py  test_stock.py
  test_render_determinism.py              # hash (pinned) / SSIM (advisory) of the golden render
  test_s01a_stock.py  test_s01e_dataviz.py  test_s05_compositor.py
pyproject.toml                             # MODIFY: add open-clip-torch (host extra), imagehash, scikit-image
```

**Responsibility split:** `shared/visual/` = how the *picture per beat* is chosen (CI-tested pure logic + a CLIP seam); `shared/layout/` = the resolve→manifest→render→encode pipeline (pure resolve/bind CI-tested, the Remotion/NVENC calls integration); `remotion/` = the TS render components shared by `05` and `01e`. GPU talks over HTTP only inside `real.py`.

---

# Part A — The visual-fetch lane (`01a`–`01e`)

## Phase A0 — Deps

### Task 0: Add M2 dependencies

**Files:** Modify `pyproject.toml`

- [ ] **Step 1:** Add to dev/host deps: `"imagehash>=4.3"`, `"scikit-image>=0.22"` (SSIM), `"numpy"`, `"pillow"` (if not already from M1). Add a host-only extra group note: `open-clip-torch`, `torch` are installed on the host, imported lazily in `shared/visual/clip.py` so CI import never fails.
- [ ] **Step 2:** Run `uv sync && uv run pytest -q -m "not integration"` → M0+M1 tests still PASS.
- [ ] **Step 3:** Commit: `git add pyproject.toml && git commit -m "chore(m2): add visual-lane deps"`

## Phase A1 — CLIP relevance ranking

### Task 1: `ClipRanker` — rank candidate images by beat similarity

**Files:** Create `shared/visual/__init__.py` (empty), `shared/visual/clip.py`; Test `tests/test_clip.py`

- [ ] **Step 1: Write the failing tests** (pure ranking logic with an injected scorer; the real CLIP model is integration)

```python
# tests/test_clip.py
import pytest
from shared.visual.clip import rank_candidates, ClipRanker


def test_rank_orders_by_descending_score():
    scores = {"a.jpg": 0.2, "b.jpg": 0.9, "c.jpg": 0.5}
    ranked = rank_candidates(["a.jpg", "b.jpg", "c.jpg"], lambda p: scores[p])
    assert ranked == ["b.jpg", "c.jpg", "a.jpg"]


def test_below_threshold_filtered():
    scores = {"a.jpg": 0.1, "b.jpg": 0.4}
    ranked = rank_candidates(["a.jpg", "b.jpg"], lambda p: scores[p], threshold=0.3)
    assert ranked == ["b.jpg"]


@pytest.mark.integration
def test_clip_ranker_scores_real_image(tmp_path):
    r = ClipRanker(model="ViT-B-32", pretrained="laion2b_s34b_b79k")
    assert 0.0 <= r.score("a green stock chart", tmp_path / "chart.png") <= 1.0
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/visual/clip.py`**

```python
from pathlib import Path
from typing import Callable


def rank_candidates(paths: list[str], scorer: Callable[[str], float],
                    threshold: float = 0.0) -> list[str]:
    scored = [(p, scorer(p)) for p in paths]
    kept = [(p, s) for p, s in scored if s >= threshold]
    return [p for p, _ in sorted(kept, key=lambda x: x[1], reverse=True)]


class ClipRanker:
    """open-clip beat<->image cosine similarity. model_id is config-swappable (ADR 0005)."""

    def __init__(self, model: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        self.model_id = f"open-clip:{model}:{pretrained}"
        self._model = model
        self._pretrained = pretrained
        self._loaded = None

    def _ensure(self):
        if self._loaded is None:
            import open_clip, torch  # host-only
            m, _, prep = open_clip.create_model_and_transforms(self._model, pretrained=self._pretrained)
            self._loaded = (m, prep, open_clip.get_tokenizer(self._model), torch)
        return self._loaded

    def score(self, beat_text: str, image: Path) -> float:
        from PIL import Image
        m, prep, tok, torch = self._ensure()
        with torch.no_grad():
            img = prep(Image.open(image)).unsqueeze(0)
            txt = tok([beat_text])
            i = m.encode_image(img); t = m.encode_text(txt)
            i = i / i.norm(dim=-1, keepdim=True); t = t / t.norm(dim=-1, keepdim=True)
            return float((i @ t.T).item())
```

- [ ] **Step 4: Run** → `uv run pytest tests/test_clip.py -m "not integration" -v` → PASS (2). **Commit.**

```bash
git add shared/visual/__init__.py shared/visual/clip.py tests/test_clip.py
git commit -m "feat(m2): CLIP relevance ranking (open-clip ViT-B/32, ADR 0005 D5)"
```

## Phase A2 — Cross-video dedup + the fallback ladder

### Task 2: Perceptual-hash cross-video dedup (pure)

ADR 0005 D5: no coin-jar clip in every video — dedup candidates against clips used in other batch videos + the ledger.

**Files:** Create `shared/visual/dedup.py`; Test `tests/test_dedup.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dedup.py
from shared.visual.dedup import is_duplicate, filter_new


def test_near_identical_hash_is_duplicate():
    assert is_duplicate("ffff0000ffff0000", {"ffff0000ffff0001"}, max_distance=2) is True


def test_distinct_hash_kept():
    assert is_duplicate("ffff0000ffff0000", {"0000ffff0000ffff"}, max_distance=2) is False


def test_filter_new_drops_seen():
    cands = [("a.jpg", "ffff0000ffff0000"), ("b.jpg", "0000ffff0000ffff")]
    used = {"ffff0000ffff0001"}
    assert filter_new(cands, used, max_distance=2) == [("b.jpg", "0000ffff0000ffff")]
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/visual/dedup.py`**

```python
def _hamming_hex(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def is_duplicate(phash: str, used: set[str], max_distance: int = 2) -> bool:
    return any(_hamming_hex(phash, u) <= max_distance for u in used)


def filter_new(candidates: list[tuple[str, str]], used: set[str],
               max_distance: int = 2) -> list[tuple[str, str]]:
    return [(p, h) for p, h in candidates if not is_duplicate(h, used, max_distance)]
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/visual/dedup.py tests/test_dedup.py
git commit -m "feat(m2): perceptual-hash cross-video dedup (ADR 0005 D5)"
```

### Task 3: Per-region fallback ladder (pure)

ADR 0008 D3: ranked stock → AI gen → branded card; terminal is a clean on-brand card, never a mismatched clip; hook frame floors at a typographic card.

**Files:** Create `shared/visual/fallback.py`; Test `tests/test_fallback.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fallback.py
from shared.visual.fallback import choose_asset, AssetChoice


def test_stock_used_when_above_threshold():
    c = choose_asset(beat="gold bars", stock_ranked=[("g.jpg", 0.42)], stock_threshold=0.30,
                     ai_available=True, is_hook=False)
    assert c == AssetChoice(kind="stock", ref="g.jpg")


def test_falls_through_to_ai_when_stock_weak():
    c = choose_asset(beat="gold bars", stock_ranked=[("g.jpg", 0.10)], stock_threshold=0.30,
                     ai_available=True, is_hook=False)
    assert c == AssetChoice(kind="ai", ref=None)


def test_terminal_is_branded_card_not_generic():
    c = choose_asset(beat="gold bars", stock_ranked=[], stock_threshold=0.30,
                     ai_available=False, is_hook=False)
    assert c == AssetChoice(kind="card", ref=None)


def test_hook_floor_is_typographic_card():
    c = choose_asset(beat="hook", stock_ranked=[], stock_threshold=0.30,
                     ai_available=False, is_hook=True)
    assert c == AssetChoice(kind="hook_card", ref=None)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/visual/fallback.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetChoice:
    kind: str          # "stock" | "ai" | "card" | "hook_card"
    ref: str | None    # stock path when kind == "stock", else None


def choose_asset(*, beat: str, stock_ranked: list[tuple[str, float]], stock_threshold: float,
                 ai_available: bool, is_hook: bool) -> AssetChoice:
    if stock_ranked and stock_ranked[0][1] >= stock_threshold:
        return AssetChoice(kind="stock", ref=stock_ranked[0][0])
    if ai_available:
        return AssetChoice(kind="ai", ref=None)
    return AssetChoice(kind="hook_card" if is_hook else "card", ref=None)
```

- [ ] **Step 4: Run** → PASS (4). **Commit.**

```bash
git add shared/visual/fallback.py tests/test_fallback.py
git commit -m "feat(m2): per-region asset fallback ladder (ADR 0008 D3)"
```

## Phase A3 — Stock client + 01a stage

### Task 4: Licensed-stock client + provenance (pure record-building)

**Files:** Create `shared/visual/stock.py`; Test `tests/test_stock.py`

- [ ] **Step 1: Write the failing tests** (pure: provenance record + license gating; the HTTP fetch is integration)

```python
# tests/test_stock.py
import pytest
from shared.visual.stock import provenance_record, license_ok


def test_provenance_record_shape():
    r = provenance_record(asset_id="px_1", source="pexels", url="https://p/1",
                          license="Pexels", fetch_date="2026-06-09")
    assert r == {"asset_id": "px_1", "source": "pexels", "url": "https://p/1",
                 "license": "Pexels", "fetch_date": "2026-06-09"}


def test_license_gate_rejects_unknown():
    assert license_ok("Pexels") is True
    assert license_ok("Unknown-NC") is False
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/visual/stock.py`**

```python
import httpx  # noqa: used by the live client

_COMMERCIAL_SAFE = {"Pexels", "Pixabay", "Mixkit", "Coverr", "Videvo-Free"}


def license_ok(license_name: str) -> bool:
    return license_name in _COMMERCIAL_SAFE


def provenance_record(*, asset_id: str, source: str, url: str, license: str,
                      fetch_date: str) -> dict:
    return {"asset_id": asset_id, "source": source, "url": url,
            "license": license, "fetch_date": fetch_date}


class StockClient:
    """Pulls N vertical candidates per query from commercial-safe libraries (host/integration)."""

    def __init__(self, providers: dict[str, str]):  # {provider: api_key}
        self._providers = providers

    def search(self, query: str, n: int) -> list[dict]:
        raise NotImplementedError("live provider HTTP wired at integration bring-up; "
                                  "01a CI uses fixture candidates")
```

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/visual/stock.py tests/test_stock.py
git commit -m "feat(m2): stock client provenance + license gate (Ch.9)"
```

### Task 5: Stage `01a` wiring (search → rank → dedup → fallback → scenes + provenance)

**Files:** Create `stages/s01a_stock/{__init__.py,stage.py,manifest.json}`; Test `tests/test_s01a_stock.py`

- [ ] **Step 1: Write the failing test** (the full per-beat selection pipeline with injected scorer + candidates)

```python
# tests/test_s01a_stock.py
from stages.s01a_stock.stage import select_for_beat
from shared.visual.fallback import AssetChoice


def test_select_for_beat_ranks_dedups_then_chooses():
    cands = [("a.jpg", "ffff0000ffff0000"), ("b.jpg", "0000ffff0000ffff")]
    choice = select_for_beat(
        beat="gold bars", candidates=cands,
        scorer=lambda p: {"a.jpg": 0.1, "b.jpg": 0.5}[p],
        used_hashes={"ffff0000ffff0001"},   # a.jpg is a near-dup of a used clip
        stock_threshold=0.30, ai_available=True, is_hook=False)
    assert choice == AssetChoice(kind="stock", ref="b.jpg")  # a dropped by dedup, b clears threshold
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `stages/s01a_stock/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage
from shared.visual.clip import rank_candidates
from shared.visual.dedup import filter_new
from shared.visual.fallback import AssetChoice, choose_asset


def select_for_beat(*, beat, candidates, scorer, used_hashes, stock_threshold,
                    ai_available, is_hook) -> AssetChoice:
    fresh = filter_new(candidates, used_hashes)
    ranked_paths = rank_candidates([p for p, _ in fresh], scorer, threshold=0.0)
    stock_ranked = [(p, scorer(p)) for p in ranked_paths]
    return choose_asset(beat=beat, stock_ranked=stock_ranked, stock_threshold=stock_threshold,
                        ai_available=ai_available, is_hook=is_hook)


@stage(StageManifest(id="01a", inputs=["script"], outputs=["scenes_stock", "provenance"],
                     compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    # iterate the format's media zones; for each beat: search -> select_for_beat;
    # below-threshold beats flagged ai_needed for 01b. Writes scenes_stock.json + provenance.json.
    raise NotImplementedError("zone iteration + live search wired at integration; "
                              "select_for_beat is unit-tested")
```

> The offline DAG (M0 runner) supplies a fake `StockClient` returning fixture candidates so 01a's selection runs in CI; the `run()` zone-iteration body is wired at host bring-up.

- [ ] **Step 4: Write `manifest.json`**

```json
{"id": "01a", "inputs": ["script"], "outputs": ["scenes_stock", "provenance"], "compute": "cpu"}
```

- [ ] **Step 5: Run** → PASS (1). **Commit.**

```bash
git add stages/s01a_stock/ tests/test_s01a_stock.py
git commit -m "feat(m2): 01a stock select (rank+dedup+fallback per beat, ADR 0005/0008)"
```

## Phase A4 — GPU stages (01b/01c/01d) over ComfyUI

### Task 6: `ComfyUIBackend` (generate_image / img2vid / restore) + 01b/01c/01d stages

ADR 0001: thin HTTP client to host ComfyUI. ADR 0010 D4: generative cache key folds in `model_id + graph_version`.

**Files:** Modify `shared/adapters/real.py`; Create `stages/s01b_imagegen/`, `stages/s01c_img2vid/`, `stages/s01d_upscale/` (`stage.py`+`manifest.json` each); Test `tests/test_adapters_comfy.py`

- [ ] **Step 1: Write the failing tests** (payload/graph-version construction is pure; the live queue is integration)

```python
# tests/test_adapters_comfy.py
import pytest
from shared.adapters import ModelBackend
from shared.adapters.real import ComfyUIBackend


def test_comfy_satisfies_protocol():
    be = ComfyUIBackend(base_url="http://h:8188", graphs={"flux": "g_flux_v3"})
    assert isinstance(be, ModelBackend)
    assert hasattr(be, "restore")   # restore is part of ModelBackend (added to the M0 Protocol)


def test_graph_version_exposed_for_cache_key():
    be = ComfyUIBackend(base_url="http://h:8188", graphs={"flux": "g_flux_v3"})
    assert be.graph_version("flux") == "g_flux_v3"   # folded into the generative cache key


@pytest.mark.integration
def test_generate_image_live(tmp_path):
    be = ComfyUIBackend(base_url="http://127.0.0.1:8188", graphs={"flux": "g_flux_v3"})
    p = be.generate_image("a green candlestick chart, studio lighting", seed=7)
    assert p.exists()
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Add `ComfyUIBackend` to `shared/adapters/real.py`**

```python
class ComfyUIBackend:
    """ModelBackend for the host ComfyUI: FLUX (generate_image), LTX (img2vid),
    ESRGAN+RIFE+GFPGAN (restore). Each capability maps to a named, versioned graph."""

    def __init__(self, base_url: str, graphs: dict[str, str], timeout: float = 600.0):
        self._base = base_url.rstrip("/")
        self._graphs = graphs           # {capability: graph_version}
        self._timeout = timeout
        self.model_id = "comfyui"

    def graph_version(self, capability: str) -> str:
        return self._graphs[capability]

    def _submit(self, capability: str, inputs: dict, seed: int):
        import httpx
        graph = self._build_graph(capability, inputs, seed)  # JSON workflow for /prompt
        r = httpx.post(f"{self._base}/prompt", json={"prompt": graph}, timeout=self._timeout)
        r.raise_for_status()
        return self._await_output(r.json()["prompt_id"])      # poll /history, return artifact path

    def generate_image(self, prompt: str, seed: int):
        return self._submit("flux", {"prompt": prompt}, seed)

    def img2vid(self, image, seed: int):
        return self._submit("ltx", {"image": str(image)}, seed)

    def restore(self, frames):
        return self._submit("restore", {"frames": [str(f) for f in frames]}, seed=0)

    def _build_graph(self, capability, inputs, seed):
        raise NotImplementedError("ComfyUI workflow JSON wired at host bring-up")
    def _await_output(self, prompt_id):
        raise NotImplementedError("poll /history wired at host bring-up")
    # llm/tts/vlm_judge not provided by ComfyUI
    def llm(self, prompt): raise NotImplementedError
    def tts(self, text): raise NotImplementedError
    def vlm_judge(self, frames, script): raise NotImplementedError
```

- [ ] **Step 4: Implement the three thin stages.** Each reads its input scenes, calls the backend per beat needing fill, and writes its output; the cache key uses `model_id + graph_version`. Example `stages/s01b_imagegen/stage.py`:

```python
import json
from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="01b", inputs=["script", "scenes_stock"], outputs=["scenes_gen"],
                     compute="gpu", capability="generate_image"))
def run(ctx: StageContext) -> StageResult:
    be = ctx.backend("generate_image")
    # for each beat flagged ai_needed by 01a: be.generate_image(prompt, ctx.seed)
    # cache key for this stage includes model_id + be.graph_version("flux") (ADR 0010 D4)
    raise NotImplementedError("per-beat FLUX fill wired at host bring-up")
```

`manifest.json` for 01b: `{"id":"01b","inputs":["script","scenes_stock"],"outputs":["scenes_gen"],"compute":"gpu","capability":"generate_image"}`. Mirror for 01c (`inputs:["scenes_gen"]`,`outputs:["scenes_motion"]`,`capability:"img2vid"`) and 01d (`inputs:["scenes_motion"]`,`outputs:["assets"]`,`compute:"gpu"`).

- [ ] **Step 5: Run** → `uv run pytest tests/test_adapters_comfy.py -m "not integration" -v` → PASS (2). **Commit.**

```bash
git add shared/adapters/real.py stages/s01b_imagegen/ stages/s01c_img2vid/ stages/s01d_upscale/ tests/test_adapters_comfy.py
git commit -m "feat(m2): ComfyUI backend + 01b/01c/01d GPU stages (graph-versioned cache, ADR 0001/0010)"
```

## Phase A5 — 01e data-viz (Remotion-shared) + assets assembly

### Task 7: Stage `01e` data-viz (renders chart components via the Remotion bridge)

**Files:** Create `stages/s01e_dataviz/{__init__.py,stage.py,manifest.json}`; Test `tests/test_s01e_dataviz.py`

- [ ] **Step 1: Write the failing test** (pure: build the chart spec the Remotion `Chart` component consumes from `data.json` numbers)

```python
# tests/test_s01e_dataviz.py
from stages.s01e_dataviz.stage import chart_spec


def test_chart_spec_from_data_series():
    data = {"market": {"cpi_yoy": {"value": 3.2}, "fed_funds": {"value": 4.5}}}
    spec = chart_spec(data, keys=["cpi_yoy", "fed_funds"], kind="bar", brand={"accent": "#00E5FF"})
    assert spec["kind"] == "bar"
    assert spec["series"] == [{"label": "cpi_yoy", "value": 3.2}, {"label": "fed_funds", "value": 4.5}]
    assert spec["accent"] == "#00E5FF"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `stages/s01e_dataviz/stage.py`**

```python
import json
from shared.ctx import StageContext, StageResult
from shared.layout.remotion import render_component   # shared bridge (Task 11)
from shared.stage import StageManifest, stage


def chart_spec(data: dict, keys: list[str], kind: str, brand: dict, section: str = "market") -> dict:
    return {"kind": kind, "accent": brand["accent"],
            "series": [{"label": k, "value": data[section][k]["value"]} for k in keys]}


@stage(StageManifest(id="01e", inputs=["data", "script"], outputs=["scenes_viz"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    data = json.loads(ctx.read_input("data").read_text())
    # for each data-viz beat: build chart_spec -> render_component("Chart", spec) -> clip
    raise NotImplementedError("viz-beat iteration wired at integration; chart_spec is unit-tested")
```

- [ ] **Step 4:** `manifest.json`: `{"id":"01e","inputs":["data","script"],"outputs":["scenes_viz"],"compute":"cpu"}`.
- [ ] **Step 5: Run** → PASS (1). **Commit.**

```bash
git add stages/s01e_dataviz/ tests/test_s01e_dataviz.py
git commit -m "feat(m2): 01e data-viz chart spec (Remotion-shared, ADR 0005 D5/0007)"
```

---

# Part B — The format-aware compositor (replaces M1's `05`)

## Phase B1 — `layout.schema.json` + region specs

### Task 8: Author `layout.schema.json` + the ranked_list / head_to_head region specs

ADR 0007a: named regions (`bbox` on a 12-col grid + vertical anchors, `z`, `bind`, `primitive`, `enter`/`exit`, `style`) + beat pattern.

**Files:** Create `schemas/layout.schema.json`, `formats/ranked_list/layout.json`, `formats/head_to_head/layout.json`; Test `tests/test_layout_schema.py`

- [ ] **Step 1: Write `schemas/layout.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "layout.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "format", "beat_pattern", "regions"],
  "properties": {
    "schema_version": {"type": "string"},
    "format": {"type": "string"},
    "beat_pattern": {"type": "array", "items": {"type": "string"}},
    "anchors": {
      "description": "format-local named anchors merged OVER the §7a defaults (name -> [y,h]).",
      "type": "object",
      "additionalProperties": {"type": "array", "items": {"type": "number"},
                               "minItems": 2, "maxItems": 2}
    },
    "regions": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["name", "bbox", "z", "primitive", "bind"],
        "properties": {
          "name": {"type": "string"},
          "bbox": {
            "description": "ADR 0007a §3/§7a: inclusive colA-colB on a 12-col grid; vertical is EITHER a named anchor OR a literal {y,h} fraction of the safe rect.",
            "type": "object", "additionalProperties": false,
            "required": ["colA", "colB"],
            "properties": {
              "colA": {"type": "integer", "minimum": 1, "maximum": 12},
              "colB": {"type": "integer", "minimum": 1, "maximum": 12},
              "anchor": {"type": "string"},
              "y": {"type": "number", "minimum": 0, "maximum": 1},
              "h": {"type": "number", "minimum": 0, "maximum": 1}
            },
            "oneOf": [{"required": ["anchor"]}, {"required": ["y", "h"]}]
          },
          "z": {"type": "integer"},
          "primitive": {
            "type": "object", "additionalProperties": false,
            "required": ["type"],
            "properties": {
              "type": {"enum": ["MediaZone", "TextCard", "Badge", "KaraokeCaption",
                                "DataVizSlot", "CitationChip", "CTABump", "BrandOverlay"]},
              "params": {"type": "object"}
            }
          },
          "bind": {"type": "string", "description": "dotted beat-field path, or the literal \"static\" (content then from primitive.params.content)"},
          "on": {"type": "array", "items": {"type": "string"},
                 "description": "optional: beat kinds this region appears on (gates static regions like vs_badge to round beats)"},
          "enter": {"enum": ["none", "fade", "slide_in_up", "slide_in_down", "pop",
                             "count_up", "count_up_stagger", "riser_reveal"]},
          "exit": {"enum": ["none", "fade", "slide_out_up", "slide_out_down"]},
          "style": {"type": "string"}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write `formats/ranked_list/layout.json`** (binds to the `ranked_list` beat contract: `items[].{rank,title,body,media_query,stat?}`)

```json
{
  "schema_version": "1.0.0",
  "format": "ranked_list",
  "beat_pattern": ["hook", "item", "item", "item", "cta"],
  "regions": [
    {"name": "bg_media", "bbox": {"colA": 1, "colB": 12, "y": 0.0, "h": 1.0}, "z": 0,
     "primitive": {"type": "MediaZone", "params": {"fit": "cover", "kenburns": true}},
     "bind": "item.media_query", "enter": "fade", "exit": "fade", "style": "brand.media"},
    {"name": "rank_badge", "bbox": {"colA": 1, "colB": 3, "anchor": "badge"}, "z": 3,
     "primitive": {"type": "Badge", "params": {"shape": "circle"}},
     "bind": "item.rank", "enter": "pop", "exit": "fade", "style": "brand.badge"},
    {"name": "item_title", "bbox": {"colA": 1, "colB": 12, "anchor": "headline"}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "display"}},
     "bind": "item.title", "enter": "slide_in_up", "exit": "fade", "style": "brand.title"},
    {"name": "item_stat", "bbox": {"colA": 1, "colB": 12, "anchor": "stat"}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "numeric"}},
     "bind": "item.stat", "enter": "count_up", "exit": "fade", "style": "brand.stat"}
  ]
}
```

- [ ] **Step 3: Write `formats/head_to_head/layout.json`** (binds `side_a/side_b/verdict`; `vs_badge` uses a static bind)

```json
{
  "schema_version": "1.0.0",
  "format": "head_to_head",
  "beat_pattern": ["hook", "round", "round", "verdict", "cta"],
  "regions": [
    {"name": "side_a_media", "bbox": {"colA": 1, "colB": 12, "y": 0.0, "h": 0.5}, "z": 0,
     "primitive": {"type": "MediaZone", "params": {"fit": "cover"}},
     "bind": "side_a.media_query", "enter": "slide_in_down", "exit": "fade", "style": "brand.media"},
    {"name": "side_b_media", "bbox": {"colA": 1, "colB": 12, "y": 0.5, "h": 0.5}, "z": 0,
     "primitive": {"type": "MediaZone", "params": {"fit": "cover"}},
     "bind": "side_b.media_query", "enter": "slide_in_up", "exit": "fade", "style": "brand.media"},
    {"name": "side_a_label", "bbox": {"colA": 1, "colB": 8, "y": 0.04, "h": 0.08}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "label"}},
     "bind": "side_a.label", "enter": "fade", "exit": "fade", "style": "brand.label"},
    {"name": "side_b_label", "bbox": {"colA": 1, "colB": 8, "y": 0.88, "h": 0.08}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "label"}},
     "bind": "side_b.label", "enter": "fade", "exit": "fade", "style": "brand.label"},
    {"name": "vs_badge", "bbox": {"colA": 5, "colB": 8, "y": 0.44, "h": 0.12}, "z": 4,
     "primitive": {"type": "Badge", "params": {"shape": "stamp", "content": "VS"}},
     "bind": "static", "on": ["round"], "enter": "pop", "exit": "none", "style": "brand.vs"},
    {"name": "stat_bars", "bbox": {"colA": 2, "colB": 11, "y": 0.40, "h": 0.20}, "z": 3,
     "primitive": {"type": "DataVizSlot", "params": {"viz": "bars"}},
     "bind": "round.metrics", "on": ["round"], "enter": "count_up_stagger", "exit": "fade", "style": "brand.viz"},
    {"name": "verdict", "bbox": {"colA": 2, "colB": 11, "y": 0.42, "h": 0.16}, "z": 5,
     "primitive": {"type": "TextCard", "params": {"role": "display"}},
     "bind": "verdict.text", "enter": "riser_reveal", "exit": "fade", "style": "brand.verdict"}
  ]
}
```

- [ ] **Step 4: Write `tests/test_layout_schema.py`**

```python
import json
from pathlib import Path
from shared.schema import SchemaRegistry

REG = SchemaRegistry()
ROOT = Path(__file__).resolve().parents[1]


def test_ranked_list_layout_validates():
    REG.validate("layout", json.loads((ROOT / "formats/ranked_list/layout.json").read_text()))


def test_head_to_head_layout_validates():
    REG.validate("layout", json.loads((ROOT / "formats/head_to_head/layout.json").read_text()))
```

- [ ] **Step 5: Run** → PASS (2). **Commit.**

```bash
git add schemas/layout.schema.json formats/ tests/test_layout_schema.py
git commit -m "feat(m2): layout.schema + ranked_list/head_to_head region specs (ADR 0007a)"
```

## Phase B2 — Resolve step + bind validation (pure)

### Task 9: Bind validation — every region bind exists in the beat contract

ADR 0007a §3: resolve-time `bind` validation rejects a layout whose region binds a field the format's typed beat data doesn't provide.

**Files:** Create `shared/layout/__init__.py` (empty), `shared/layout/bind.py`; Test `tests/test_bind.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bind.py
import pytest
from shared.layout.bind import validate_binds, BindError


def test_static_bind_always_ok():
    validate_binds(["static"], beat_data={})  # no raise (content comes from primitive.params)


def test_dotted_bind_must_exist():
    validate_binds(["item.title", "item.stat"], beat_data={"item": {"title": "x", "stat": "y"}})


def test_missing_bind_raises():
    with pytest.raises(BindError):
        validate_binds(["item.missing"], beat_data={"item": {"title": "x"}})
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/layout/bind.py`**

```python
class BindError(Exception):
    """A region binds a field absent from the format's typed beat data."""


def _exists(path: str, data: dict) -> bool:
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def validate_binds(binds: list[str], beat_data: dict) -> None:
    for b in binds:
        if b == "static":            # ADR 0007a §3: literal "static"; content via primitive.params
            continue
        if not _exists(b, beat_data):
            raise BindError(f"region bind {b!r} not in beat data")
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/layout/__init__.py shared/layout/bind.py tests/test_bind.py
git commit -m "feat(m2): resolve-time bind validation (ADR 0007a §3)"
```

### Task 10: The resolve step — `(layout, beat_data, brand_kit, timings, seed) → render_manifest`

ADR 0007a §2: a pure function merging the inputs into a flat manifest the engine renders.

**Files:** Create `shared/layout/resolve.py`, `shared/layout/schema_load.py`; Create fixtures under `tests/fixtures/m2/`; Test `tests/test_resolve.py`

- [ ] **Step 1: Write fixtures** `tests/fixtures/m2/layout_ranked_list.json` (copy of `formats/ranked_list/layout.json`), `beat_data_ranked_list.json`:

```json
{"beats": [
  {"kind": "item", "item": {"rank": 1, "title": "ACME", "body": "Yield 4.1%", "media_query": "acme", "stat": "4.1%"}},
  {"kind": "item", "item": {"rank": 2, "title": "BETA", "body": "Yield 3.7%", "media_query": "beta", "stat": "3.7%"}}
]}
```
and `brand_kit.json`: `{"accent": "#00E5FF", "font": "Inter", "styles": {"brand.title": {"size": 72}}}`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_resolve.py
import json
from pathlib import Path
from shared.layout.resolve import resolve
from shared.schema import SchemaRegistry

FIX = Path(__file__).parent / "fixtures" / "m2"
REG = SchemaRegistry()


def _load(n): return json.loads((FIX / n).read_text())


def test_resolve_emits_manifest_validating_against_schema():
    m = resolve(layout=_load("layout_ranked_list.json"),
                beat_data=_load("beat_data_ranked_list.json"),
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}],
                seed=7)
    REG.validate("render_manifest", m)         # output is a versioned contract (ADR 0007a §2)
    assert m["fps"] == 30 and m["width"] == 1080 and m["height"] == 1920 and m["seed"] == 7
    assert len(m["scenes"]) == 2
    s0 = m["scenes"][0]
    assert s0["start"] == 0.0 and s0["end"] == 2.0
    title = next(r for r in s0["regions"] if r["name"] == "item_title")
    assert title["value"] == "ACME" and title["style"]["size"] == 72
    assert set(title["rect"]) == {"x", "y", "w", "h"}     # projected to PIXELS (§7a)


def test_resolve_is_pure_deterministic():
    args = dict(layout=_load("layout_ranked_list.json"),
                beat_data=_load("beat_data_ranked_list.json"),
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}], seed=7)
    assert resolve(**args) == resolve(**args)


def test_resolve_rejects_unbound_field():
    import pytest
    from shared.layout.bind import BindError
    bad = _load("beat_data_ranked_list.json")
    del bad["beats"][0]["item"]["title"]
    with pytest.raises(BindError):
        resolve(layout=_load("layout_ranked_list.json"), beat_data=bad,
                brand_kit=_load("brand_kit.json"),
                timings=[{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}], seed=7)
```

- [ ] **Step 3: Implement `shared/layout/schema_load.py`**

```python
import json
from pathlib import Path
from shared.schema import SchemaRegistry

_REG = SchemaRegistry()


def load_layout(path: Path) -> dict:
    layout = json.loads(Path(path).read_text())
    _REG.validate("layout", layout)
    return layout
```

- [ ] **Step 3b: Author `schemas/render_manifest.schema.json`** — the resolve step's output contract (ADR 0007a §2 calls for this; M0 deferred the compositor's schemas, so it is authored here alongside `layout.schema.json`). `test_resolve` (Step 2) validates `resolve()`'s output against it.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "render_manifest.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "fps", "width", "height", "seed", "scenes"],
  "properties": {
    "schema_version": {"type": "string"},
    "fps": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"},
    "seed": {"type": "integer"}, "accent": {"type": ["string", "null"]},
    "safe_rect": {"type": "object"}, "markers": {"type": "object"},
    "scenes": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["start", "end", "kind", "regions"],
        "properties": {
          "start": {"type": "number"}, "end": {"type": "number"}, "kind": {"type": "string"},
          "regions": {
            "type": "array",
            "items": {
              "type": "object", "additionalProperties": false,
              "required": ["name", "primitive", "rect", "z", "value"],
              "properties": {
                "name": {"type": "string"}, "primitive": {"type": "object"},
                "rect": {"type": "object"}, "z": {"type": "integer"},
                "enter": {"type": "string"}, "exit": {"type": "string"},
                "value": {}, "style": {"type": "object"}
              }
            }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Implement `shared/layout/resolve.py`**

```python
from typing import Any
from shared.layout.bind import BindError, validate_binds

# §7a default named anchors: name -> [y, h] as fractions of the safe rect.
DEFAULT_ANCHORS = {
    "badge": [0.06, 0.10], "headline": [0.62, 0.16], "stat": [0.80, 0.12],
    "label": [0.04, 0.10], "caption": [0.82, 0.12],
}


def _standard_regions() -> list[dict]:
    # §6 standard regions injected into every layout (caption band + brand bug).
    return [
        {"name": "caption", "bbox": {"colA": 1, "colB": 12, "anchor": "caption"}, "z": 8,
         "primitive": {"type": "KaraokeCaption", "params": {}}, "bind": "static",
         "enter": "none", "exit": "none", "style": "brand.caption"},
        {"name": "brand_overlay", "bbox": {"colA": 9, "colB": 12, "y": 0.02, "h": 0.06}, "z": 9,
         "primitive": {"type": "BrandOverlay", "params": {}}, "bind": "static",
         "enter": "none", "exit": "none", "style": "brand.bug"},
    ]


def _project(bbox: dict, anchors: dict, safe: dict) -> dict:
    col_w = safe["w"] / 12.0
    x = safe["x"] + (bbox["colA"] - 1) * col_w
    w = (bbox["colB"] - bbox["colA"] + 1) * col_w          # colA-colB INCLUSIVE (§7a)
    if "anchor" in bbox:
        if bbox["anchor"] not in anchors:
            raise BindError(f"anchor {bbox['anchor']!r} not in defaults ∪ format anchors (§3)")
        y_frac, h_frac = anchors[bbox["anchor"]]
    else:
        y_frac, h_frac = bbox["y"], bbox["h"]
    return {"x": round(x), "y": round(safe["y"] + y_frac * safe["h"]),
            "w": round(w), "h": round(h_frac * safe["h"])}


def _applies(region: dict, beat: dict) -> bool:
    on = region.get("on")
    if on is not None:                       # explicit beat-kind gate (e.g. vs_badge -> round)
        return beat["kind"] in on
    if region["bind"] == "static":           # §6 standard regions ride every beat
        return True
    return region["bind"].split(".")[0] in beat   # data-driven: bind root present in this beat


def _resolve_bind(bind: str, beat: dict, primitive: dict) -> Any:
    if bind == "static":
        return primitive.get("params", {}).get("content")   # §3: content from the primitive
    node: Any = beat
    for part in bind.split("."):
        if not isinstance(node, dict) or part not in node:
            raise BindError(f"bind {bind!r} missing in beat {beat.get('kind')!r}")
        node = node[part]
    return node


def resolve(*, layout: dict, beat_data: dict, brand_kit: dict, timings: list[dict],
            seed: int, safe_rect: dict | None = None) -> dict:
    """Pure fn: layout + typed beat data + brand kit + word timings + seed -> render_manifest
    with PROJECTED PIXEL rects, §6 injected regions, and marker frame-indices (ADR 0007a §2)."""
    safe = safe_rect or {"x": 0, "y": 0, "w": 1080, "h": 1920}
    anchors = {**DEFAULT_ANCHORS, **layout.get("anchors", {})}
    beats = beat_data["beats"]
    all_regions = layout["regions"] + _standard_regions()
    styles = brand_kit.get("styles", {})
    fps = 30

    # author-time bind validation (§3): every non-static bind must exist in the format
    # contract (union of all beat shapes), regardless of which beat renders it.
    contract: dict = {}
    for b in beats:
        contract.update({k: v for k, v in b.items() if k != "kind"})
    validate_binds([r["bind"] for r in all_regions], contract)

    scenes, markers = [], {}
    for beat, t in zip(beats, timings):
        regs = []
        for r in all_regions:
            if not _applies(r, beat):
                continue
            regs.append({
                "name": r["name"], "primitive": r["primitive"],
                "rect": _project(r["bbox"], anchors, safe),
                "z": r["z"], "enter": r.get("enter", "none"), "exit": r.get("exit", "none"),
                "value": _resolve_bind(r["bind"], beat, r["primitive"]),
                "style": styles.get(r.get("style", ""), {}),
            })
            if r["name"] in ("cta_bump", "vs_badge"):   # named markers for §10 golden samples
                markers[r["name"]] = round(t["start"] * fps)
        scenes.append({"start": t["start"], "end": t["end"], "kind": beat["kind"],
                       "regions": sorted(regs, key=lambda x: x["z"])})
    return {"schema_version": "1.0.0", "fps": fps, "width": 1080, "height": 1920, "seed": seed,
            "accent": brand_kit.get("accent"), "safe_rect": safe, "markers": markers,
            "scenes": scenes}
```

- [ ] **Step 5: Run** → PASS (3). **Commit.**

```bash
git add shared/layout/resolve.py shared/layout/schema_load.py tests/fixtures/m2/ tests/test_resolve.py
git commit -m "feat(m2): pure resolve step layout+data+brand+timings+seed -> render_manifest (ADR 0007a §2)"
```

## Phase B3 — Remotion bridge + NVENC encode + determinism tripwire

### Task 11: Remotion project + the Python↔Remotion bridge

**Files:** Create `remotion/package.json`, `remotion/remotion.config.ts`, `remotion/src/Root.tsx`, `remotion/src/Manifest.tsx`, `remotion/src/primitives/*.tsx`; Create `shared/layout/remotion.py`; Test `tests/test_render_determinism.py` (Task 13 finalizes)

- [ ] **Step 1: Scaffold the Remotion project.** `remotion/src/index.ts` is the Remotion entry — it `registerRoot(Root)`; `src/Root.tsx` registers the compositions: `Manifest` (the full `LayoutEngine`) and one per primitive (so 01e can render a single `DataVizSlot` standalone — same components, same engine). `remotion/src/Manifest.tsx` reads `render_manifest.json` (input props) and renders each scene's regions by `primitive.type` onto a 1080×1920 @30fps canvas using the **8 ADR 0007a §4 primitive components** (`MediaZone`, `TextCard`, `Badge`, `KaraokeCaption`, `DataVizSlot`, `CitationChip`, `CTABump`, `BrandOverlay`), positioning from each region's **already-projected pixel `rect`** (resolve did the grid→pixel projection), applying `enter`/`exit` animations by name. `package.json` pins exact Remotion + Node versions (the determinism contract, ADR 0007a §1).

```json
// remotion/package.json (excerpt)
{ "name": "shorts-compositor", "private": true,
  "dependencies": { "@remotion/cli": "4.0.*", "remotion": "4.0.*", "react": "18.*", "react-dom": "18.*" },
  "scripts": { "render": "remotion render src/index.ts Manifest" } }
```

- [ ] **Step 2: Implement `shared/layout/remotion.py`** — writes the manifest, invokes the Remotion CLI to render PNG frames into an out dir, returns the frame paths.

```python
import json
import subprocess
from pathlib import Path

REMOTION_DIR = Path(__file__).resolve().parents[2] / "remotion"


def render_manifest_to_frames(manifest: dict, out_dir: Path) -> list[Path]:
    """Pure-function render: same manifest -> same frames (in the pinned toolchain image)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    raw = out_dir / "raw"
    subprocess.run(
        ["npx", "remotion", "render", "src/index.ts", "Manifest",
         "--props", str(manifest_path), "--sequence", "--image-format", "png",
         "--output", str(raw)],
        cwd=REMOTION_DIR, check=True)
    # Remotion --sequence emits element-<n>.png (NOT zero-padded). Renumber to a zero-padded
    # sequence so ffmpeg's `%05d.png` pattern (encode.py) matches and ordering is numeric
    # (lexical == numeric once padded) — fixes both the glob mismatch and the sort-order bug.
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    raws = sorted(raw.glob("*.png"),
                  key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    out = []
    for i, src in enumerate(raws):
        dst = frames_dir / f"{i:05d}.png"
        dst.write_bytes(src.read_bytes())
        out.append(dst)
    return out


def render_component(component: str, props: dict, out_dir: Path) -> Path:
    """Renders ONE registered Remotion composition standalone — 01e uses it for the `DataVizSlot`
    component, the SAME component `Manifest` mounts for the `stat_bars` region — so 01e and 05
    share the engine AND the chart component, not merely the project (ADR 0007a §1/§4)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    props_path = out_dir / f"{component}.props.json"
    props_path.write_text(json.dumps(props, sort_keys=True))
    subprocess.run(["npx", "remotion", "render", "src/index.ts", component,
                    "--props", str(props_path), "--output", str(out_dir / f"{component}.mp4")],
                   cwd=REMOTION_DIR, check=True)
    return out_dir / f"{component}.mp4"
```

- [ ] **Step 3: Commit the scaffold + bridge.**

```bash
git add remotion/ shared/layout/remotion.py
git commit -m "feat(m2): Remotion project + Python bridge (LayoutEngine + 01e shared, ADR 0007)"
```

### Task 12: NVENC encode (frames → mp4)

**Files:** Create `shared/layout/encode.py`; Test `tests/test_encode.py`

- [ ] **Step 1: Write the failing test** (pure command construction)

```python
# tests/test_encode.py
from pathlib import Path
from shared.layout.encode import build_nvenc_cmd


def test_nvenc_cmd_uses_h264_nvenc_and_audio(tmp_path):
    cmd = build_nvenc_cmd(frames_glob=str(tmp_path / "frames/%05d.png"),
                          narration=tmp_path / "narration.wav", fps=30,
                          out=tmp_path / "youtube.mp4")
    s = " ".join(cmd)
    assert "h264_nvenc" in s and "-framerate 30" in s and s.endswith(str(tmp_path / "youtube.mp4"))
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/layout/encode.py`**

```python
from pathlib import Path


def build_nvenc_cmd(*, frames_glob: str, narration: Path, fps: int, out: Path) -> list[str]:
    return ["ffmpeg", "-y", "-framerate", str(fps), "-i", frames_glob,
            "-i", str(narration), "-c:v", "h264_nvenc", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out)]
```

- [ ] **Step 4: Run** → PASS (1). **Commit.**

```bash
git add shared/layout/encode.py tests/test_encode.py
git commit -m "feat(m2): NVENC encode command (frames -> mp4, ADR 0007a)"
```

### Task 13: Render determinism tripwire (hash in pinned image / SSIM advisory)

ADR 0007a §1/§9.

**Files:** Create `tests/fixtures/m2/render_manifest_golden.json`, `tests/fixtures/m2/frames_golden/`; Test `tests/test_render_determinism.py`

- [ ] **Step 1: Write `render_manifest_golden.json`** — the output of `resolve(...)` on the ranked_list fixtures (a small 2-scene manifest), committed so the test renders a fixed input.

- [ ] **Step 2: Write the test** (integration — needs the Remotion toolchain; exact-hash only in the pinned image)

```python
# tests/test_render_determinism.py
import hashlib
import json
import os
from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures" / "m2"
PINNED = os.environ.get("SHORTS_TOOLCHAIN") == "pinned"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.integration
def test_golden_render_is_stable(tmp_path):
    from shared.layout.remotion import render_manifest_to_frames
    manifest = json.loads((FIX / "render_manifest_golden.json").read_text())
    frames = render_manifest_to_frames(manifest, tmp_path)
    golden = sorted((FIX / "frames_golden").glob("*.png"))
    assert len(frames) == len(golden)
    if PINNED:
        assert [_sha(f) for f in frames] == [_sha(g) for g in golden]   # byte-identical tripwire
    else:
        from skimage.metrics import structural_similarity as ssim
        from PIL import Image
        import numpy as np
        for f, g in zip(frames, golden):
            a = np.array(Image.open(f).convert("L")); b = np.array(Image.open(g).convert("L"))
            assert ssim(a, b) >= 0.99                                   # advisory elsewhere
```

- [ ] **Step 3:** Generate `frames_golden/` once inside the pinned image and commit them (documented in the task: run `SHORTS_TOOLCHAIN=pinned` render, copy frames to the fixture dir).

- [ ] **Step 4: Run** (on host/pinned) → PASS; in CI it's deselected by `-m "not integration"`. **Commit.**

```bash
git add tests/fixtures/m2/render_manifest_golden.json tests/fixtures/m2/frames_golden/ tests/test_render_determinism.py
git commit -m "test(m2): render determinism tripwire (hash pinned / SSIM advisory, ADR 0007a §1/§9)"
```

## Phase B4 — Stage 05 replacement

### Task 14: Replace `stages/s05_render` with the compositor (resolve → Remotion → NVENC)

**Files:** Modify `stages/s05_render/stage.py` (replace M1 ffmpeg body), `manifest.json` (inputs now include `data`/timings); Test `tests/test_s05_compositor.py`

- [ ] **Step 1: Write the failing test** (pure: per-platform manifest delta — the YT vs TikTok cut differs by safe-zone/CTA, not a re-encode)

```python
# tests/test_s05_compositor.py
from stages.s05_render.stage import platform_delta


def test_platform_delta_changes_only_declared_fields():
    base = {"fps": 30, "scenes": [], "cta": {"verb": "Follow"}, "safe_bottom_pct": 12}
    yt = platform_delta(base, platform="youtube")
    assert yt["cta"]["verb"] == "Subscribe"        # YT delta
    assert yt["fps"] == 30 and yt["scenes"] == []   # everything else identical
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Replace `stages/s05_render/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.layout.encode import build_nvenc_cmd
from shared.layout.remotion import render_manifest_to_frames
from shared.layout.resolve import resolve
from shared.layout.schema_load import load_layout
from shared.stage import StageManifest, stage
import subprocess


def platform_delta(manifest: dict, platform: str) -> dict:
    m = json.loads(json.dumps(manifest))  # deep copy
    if platform == "youtube":
        m.setdefault("cta", {})["verb"] = "Subscribe"
    elif platform == "tiktok":
        m.setdefault("cta", {})["verb"] = "Follow"
    return m


@stage(StageManifest(id="05", inputs=["script", "assets", "narration", "captions",
                                      "word_timings", "data"],
                     outputs=["render"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    layout = load_layout(ctx.run_dir / f"formats/{script['format']}/layout.json")
    words = json.loads(ctx.read_input("word_timings").read_text())   # declared input (no SDK bypass)
    brand_kit = json.loads((ctx.run_dir / ctx.config.get("brand_kit", "brand_kit.json")).read_text())
    beat_data = {"beats": _beats_from_script(script)}  # the typed per-beat data 00b emitted
    plat = ctx.job.get("platform_targets", ["youtube"])[0]
    manifest = resolve(layout=layout, beat_data=beat_data, brand_kit=brand_kit,
                       timings=_scene_spans(words, beat_data), seed=ctx.seed,
                       safe_rect=_safe_rect(plat, ctx.config))   # per-platform reflow (ADR 0005 D4)
    out = ctx.write_output("render")
    frames = render_manifest_to_frames(platform_delta(manifest, plat), out.parent)
    subprocess.run(build_nvenc_cmd(frames_glob=str(frames[0].parent / "%05d.png"),
                                   narration=ctx.read_input("narration"),
                                   fps=30, out=out), check=True)
    ctx.log.info("compositor render complete", scenes=len(manifest["scenes"]), platform=plat)
    return StageResult(outputs={"render": out})


def _beats_from_script(script: dict) -> list[dict]:
    ld = script["layout_data"]
    if ld["kind"] == "ranked_list":
        return [{"kind": "item", "item": it} for it in ld["items"]]
    return [{"kind": "round", **ld}]  # head_to_head: rounds carry side_a/side_b/verdict


def _scene_spans(words: list[dict], beat_data: dict) -> list[dict]:
    # word-timed cuts (ADR 0007a §2): partition words into n contiguous groups; each scene
    # spans its group's first->last word — NOT a flat division.
    n = len(beat_data["beats"])
    k, m = divmod(len(words), n)
    spans, idx = [], 0
    for s in range(n):
        size = k + (1 if s < m else 0)
        grp = words[idx:idx + size]; idx += size
        spans.append({"start": grp[0]["start"], "end": grp[-1]["end"]} if grp
                     else {"start": 0.0, "end": 0.0})
    return spans


def _safe_rect(platform: str, config: dict) -> dict:
    # per-platform safe insets reflow the SAME layout (the load-bearing per-platform delta).
    insets = {"youtube": {"top": 0.06, "bottom": 0.10}, "tiktok": {"top": 0.08, "bottom": 0.16}}
    p = insets.get(platform, {"top": 0.06, "bottom": 0.12})
    return {"x": 0, "y": int(1920 * p["top"]), "w": 1080,
            "h": int(1920 * (1 - p["top"] - p["bottom"]))}
```

- [ ] **Step 4: Update `manifest.json`**

```json
{"id": "05", "inputs": ["script", "assets", "narration", "captions", "word_timings", "data"], "outputs": ["render"], "compute": "cpu"}
```

> Note: `word_timings` is the WhisperX per-word JSON; M1's Stage 03 emits it as a declared output alongside `captions.ass` (a one-line M1 addendum), so 05 consumes it **through the SDK** (`ctx.read_input`) rather than reaching into the run dir.

- [ ] **Step 5: Run** → `uv run pytest tests/test_s05_compositor.py -v` → PASS (1); confirm the M0 manifest drift-catcher still passes (the manifest changed, so update the M1 05 manifest expectation if asserted). **Commit.**

```bash
git add stages/s05_render/ tests/test_s05_compositor.py
git commit -m "feat(m2): replace 05 ffmpeg interim with Remotion compositor (resolve->render->nvenc, ADR 0007/0007a)"
```

---

## M2 Acceptance Checklist (the testable "done")

- [ ] `01a` selects per beat via **CLIP rank → cross-video dedup → fallback ladder**; a prominent slot with no good stock falls through to AI/branded card, never a mismatched clip → Tasks 1–5.
- [ ] `01b/01c/01d` are thin ComfyUI clients; generative cache keys fold in `model_id + graph_version` → Task 6.
- [ ] `01e` renders branded data-viz from `data.json` numbers via the **shared Remotion engine** → Task 7.
- [ ] `layout.schema.json` + the `ranked_list` and `head_to_head` region specs validate; resolve-time **bind validation** rejects an unbound region → Tasks 8–9.
- [ ] The **resolve step is pure/deterministic** (same inputs → identical `render_manifest`) → Task 10.
- [ ] The golden manifest renders **byte-identically in the pinned toolchain image** (SSIM ≥0.99 elsewhere) → Task 13.
- [ ] Stage `05` produces the render via **resolve → Remotion → NVENC**; per-platform cuts are **manifest deltas**, not code paths → Task 14.
- [ ] CI stays green and GPU-free (`-m "not integration"`); all GPU/Remotion calls are integration-marked.

---

## Self-Review

**Spec coverage (Ch.4 rows + ADRs):** 01a→T1-T5 (CLIP ADR 0005 D5, dedup, fallback ADR 0008 D3, provenance Ch.9); 01b/01c/01d→T6 (ComfyUI over HTTP ADR 0001, graph-versioned cache ADR 0010 D4); 01e→T7 (data-viz, Remotion-shared ADR 0005 D5/0007); the compositor→T8-T14 (layout.schema + region specs, bind validation, pure resolve, Remotion render, NVENC, determinism tripwire, per-platform manifest delta — all ADR 0007/0007a). `lane_support`/content-scaling (ADR 0008 D2) is consumed from the format library 00b already wrote; not re-implemented here. Deferred to M3 (noted): the other 6 format region specs, the 05x/05b/05c gates, music (04), persona/brand-kit authoring.

**Placeholder scan:** No "TBD"/"add error handling". The `NotImplementedError` bodies (`StockClient.search`, ComfyUI `_build_graph`/`_await_output`, the 01a/01b/01e `run()` zone-iteration loops, 01c/01d) are **documented host-integration seams** — each names its CI substitute (fixture candidates / the offline-DAG fakes) and its pure-logic sibling that *is* implemented and tested (select_for_beat, chart_spec, graph_version, the ranking/dedup/fallback/resolve/bind/encode functions). This mirrors M1's seam discipline.

**Type consistency vs M0/M1:** Uses M0 names exactly — `@stage(StageManifest(...))`, `StageContext`, `StageResult(outputs=...)`, `SchemaRegistry().validate`, `ctx.read_input/write_output/backend`. New backends implement the M0 `ModelBackend` Protocol (`generate_image/img2vid/tts/llm/vlm_judge/restore` — `restore` was **added to the Protocol in M0** to host 01d's ESRGAN/RIFE/GFPGAN). `ComfyUIBackend` provides `generate_image/img2vid/restore` and raises on `llm/tts/vlm_judge`, fully satisfying the Protocol. `AssetChoice(kind, ref)`, `validate_binds`/`BindError`, `resolve(layout, beat_data, brand_kit, timings, seed)`, `render_manifest_to_frames`/`render_component`, `build_nvenc_cmd` names are consistent between their definition tasks and the stage-wiring tasks. The `LayoutEngine.render(render_manifest)` Protocol (ADR 0012 §6) is realized by `render_manifest_to_frames` (the bridge) — note in code that this is the concrete LayoutEngine.

**Scope:** Two parts, one acceptance gate, produces working testable software (real visuals + the compositor render). Part A (visual-fetch lane) and Part B (compositor) are cleanly separable — if execution wants two PRs, cleave at the Phase A/B boundary. M2 replaces M1's `shared/render/` interim with `shared/layout/`; the swap is contained.
```
