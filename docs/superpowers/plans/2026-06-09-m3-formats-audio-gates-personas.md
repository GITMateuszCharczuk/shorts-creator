# M3 — Formats, Audio Layer, Vision+Creative-QC Gates, Personas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the creative layer — author the **other 6 format layout templates** as data, the **audio performance layer** (music taxonomy + SFX + per-platform LUFS), the **`05x` vision pass + `05c` creative-QC gate** (incl. the ADR 0014 original-insight criterion), and **persona/brand-kit profiles for finance + business** — proving the two-niche abstraction, the format→layout binding, and the enforceable quality bar.

**Architecture:** Everything builds on the M0 SDK and the M1/M2 stages. The 6 new formats are **pure data** (`layout.json` + `format.json` + a `script.schema` `layout_data` branch each), validated by the same `layout`/bind machinery M2 built. `05x` is a thin GPU client to Qwen2.5-VL behind the M0 `ModelBackend.vlm_judge` Protocol; `05c` is a text-judge that reads the **rendered-output** `vision.json` (not just intent) and gates against a quality floor. Music/SFX/LUFS selection and the QC floor logic are **pure, CI-testable**; the VLM and ffmpeg-mix calls are `@pytest.mark.integration`.

**Tech Stack:** Python 3.12 + the M0 toolchain; the M2 `shared/layout/` resolve+Remotion path (the 6 new formats flow through it unchanged); `httpx` (Qwen2.5-VL endpoint); `ffmpeg` (music duck/SFX mix, LUFS via `loudnorm`). CI runs only pure/fake tests.

**Decisions made here (spec/ADR left open; pinned for M3):**
- **`explainer`'s "worked-through number" → `TextCard` role=numeric with `count_up` step reveals** (ADR 0007a §4/§11: "a lone number is `TextCard`+count-up, not `DataVizSlot`"). `DataVizSlot` stays reserved for real multi-series charts (`head_to_head` `stat_bars`). Same call applied to `surprising_stat`/`cautionary_tale`.
- **Music taxonomy is a closed `{mood} × {energy}` enum** mapped to a per-niche curated library file (`profiles/<niche>/music/index.json`); selection is deterministic given `(mood, energy, seed)` with **batch anti-repeat** via the existing ledger pattern.
- **Per-platform LUFS targets:** YouTube **-14 LUFS**, TikTok **-14 LUFS** integrated, true-peak **-1 dBTP** (config-overridable).
- **VLM keyframe sample set:** hook frame (frame 0), end-card frame (last), and the manifest `markers` frames (cta_bump / format-specific) + one mid-frame per scene — capped at **8 frames** for VRAM.
- **`05c` quality floor = 0.70** (overall, config; **re-anchored against the ramp's approve/reject labels** — ADR 0016 D2); the rubric is **5 criteria** (hook, original-insight, visual↔script coherence, pacing, payoff), original-insight weighted **0.30** (ADR 0014 D1). **Split per ADR 0016 D5:** the 05x VLM scores the *visual* pair (`coherence`, `pacing`) and emits observations; **05c's independent judge scores the text pair + hook** (`hook`, `original_insight`, `payoff`) from script + treatment + observations, then merges.
- **The 05c judge is an independent, non-Qwen-lineage model (ADR 0016 D1)** — resolved per-stage via the config layer (e.g. a **Mistral-family 7–9B Q4 — Apache-2.0, the license-clean default** — or Gemma-family, noting Gemma's terms are not strictly permissive; fits the 16 GB card alone in the post-render slot); the final pick happens at bring-up against the D2 calibration labels. The author model never grades its own survival criterion.
- **VLM serving is an OpenAI-compatible chat endpoint with image content** (e.g. Ollama `/v1/chat/completions` with a vision model) — no bespoke `/judge` route (ADR 0016 D5).

---

## File Structure

```
schemas/script.schema.json                # MODIFY: add 6 layout_data branches (the new formats' beat shapes)
formats/<fmt>/layout.json                  # NEW x6: myth_buster, explainer, news_reaction,
                                           #         cautionary_tale, surprising_stat, how_to_steps
formats/<fmt>/format.json                  # NEW x8: id, beat_pattern, lane_support, data_shape (all 8)
shared/formats/
  __init__.py
  registry.py                              # load+validate all formats; lane×format compatibility (ADR 0008 D2)
shared/audio/
  __init__.py
  music.py                                 # closed taxonomy + deterministic anti-repeat selection
  sfx.py                                   # format -> SFX cue list (whoosh/tick/riser+impact)
  loudness.py                              # per-platform LUFS targets + ffmpeg loudnorm args
shared/qc/
  __init__.py
  sampling.py                              # keyframe sample-set selection from a render_manifest
  creative.py                              # 05c rubric aggregation + floor gate (pure)
shared/adapters/real.py                    # MODIFY: add QwenVLBackend (implements vlm_judge)
shared/profiles/
  __init__.py
  loader.py                                # load+validate profiles/<niche>/profile.yaml via profile.schema
profiles/finance/profile.yaml              # NEW: persona + brand kit (finance)
profiles/business/profile.yaml             # NEW: persona + brand kit (business, the 2nd niche)
stages/s04_music/stage.py                  # MODIFY (M1 had a stub): taxonomy select + SFX + LUFS mix
stages/s05x_vision/{stage.py,manifest.json}    # NEW: sample keyframes -> Qwen2.5-VL -> vision.json
stages/s05c_qc/{stage.py,manifest.json}        # NEW: read vision+script -> judge -> creative_qc.json (gate)
tests/
  fixtures/m3/
    layouts/  beat_data/                   # per-format layout + a minimal valid beat_data instance
    vision.json  music_index.json  profile_finance.yaml  profile_business.yaml
  test_formats_registry.py  test_format_layouts_validate.py  test_lane_support.py
  test_music.py  test_sfx.py  test_loudness.py
  test_sampling.py  test_creative_qc.py
  test_qwenvl_backend.py  test_profiles_loader.py
  test_business_slice_offline.py           # two-niche proof: run the offline DAG for business
```

**Responsibility split:** `formats/` + `shared/formats/` = format *data* + its registry/compatibility; `shared/audio/` = the three pure audio-selection concerns; `shared/qc/` = sampling + the floor gate (pure) with the VLM behind `real.py`; `shared/profiles/` = niche data loading. New stages stay thin (M0 `run(ctx)`), delegating to those pure modules.

---

# Part A — The 8 format layout templates (the other 6 as data)

## Phase A1 — Extend the `script.schema` beat contract for the 6 new formats

### Task 1: Add the 6 `layout_data` branches to `script.schema.json`

The M0/M2 schema has `ranked_list` + `head_to_head`. Add 6 branches to the `layout_data` `oneOf`, each a closed object with a `kind` const and the typed beat fields below (from spec Ch.6):

| format | `layout_data` shape (beyond `kind`) |
|---|---|
| `myth_buster` | `claim:{text}`, `why_wrong:{text}`, `truth:{text}` |
| `explainer` | `concept:{title}`, `steps:[{label, value}]` (worked-through number as count-up steps), `takeaway:{text}` |
| `news_reaction` | `event:{headline, source_ref}`, `implications:[{text}]`, `takeaway:{text}` |
| `cautionary_tale` | `setup:{text}`, `mistake:{text}`, `cost:{stat}`, `lesson:{text}` |
| `surprising_stat` | `stat:{value, source_ref}`, `unpack:{text}`, `so_what:{text}` |
| `how_to_steps` | `steps:[{n, title, body}]` |

**Files:** Modify `schemas/script.schema.json`; Test `tests/test_format_layouts_validate.py` (negative branch here)

- [ ] **Step 1: Add the 6 branches** to the `layout_data.oneOf` array. Example for `explainer` + `surprising_stat` (author all 6 to this pattern):

```json
{
  "type": "object", "additionalProperties": false,
  "required": ["kind", "concept", "steps", "takeaway"],
  "properties": {
    "kind": {"const": "explainer"},
    "concept": {"type": "object", "additionalProperties": false,
                "required": ["title"], "properties": {"title": {"type": "string"}}},
    "steps": {"type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["label", "value"],
      "properties": {"label": {"type": "string"}, "value": {"type": "string"}}}},
    "takeaway": {"type": "object", "additionalProperties": false,
                 "required": ["text"], "properties": {"text": {"type": "string"}}}
  }
},
{
  "type": "object", "additionalProperties": false,
  "required": ["kind", "stat", "unpack", "so_what"],
  "properties": {
    "kind": {"const": "surprising_stat"},
    "stat": {"type": "object", "additionalProperties": false,
             "required": ["value", "source_ref"],
             "properties": {"value": {"type": "string"}, "source_ref": {"type": "string"}}},
    "unpack": {"type": "object", "additionalProperties": false,
               "required": ["text"], "properties": {"text": {"type": "string"}}},
    "so_what": {"type": "object", "additionalProperties": false,
                "required": ["text"], "properties": {"text": {"type": "string"}}}
  }
}
```

- [ ] **Step 2: Write a failing test** that a `surprising_stat` instance validates and a malformed one fails

```python
# tests/test_format_layouts_validate.py
import json
from pathlib import Path
import pytest
from shared.schema import SchemaRegistry, SchemaError

REG = SchemaRegistry()


def _script(layout_data: dict) -> dict:
    return {"schema_version": "1.0.0", "format": layout_data["kind"],
            "treatment": {"thesis": "t", "angle": "a", "tone": "x",
                          "visual_motif": ["m"], "energy_curve": [0.3, 1.0]},
            "hook": {"spoken": "h", "on_screen_text": "h", "first_frame_visual": "card", "duration": 1.8},
            "narration_beats": [{"text": "n"}], "captions": [{"text": "c"}],
            "music": {"mood": "confident", "energy": "mid"},
            "platform_meta": {"youtube": {"title": "t", "description": "Not advice.", "hashtags": ["x"]}},
            "claims": [], "disclaimer": "Not financial advice.", "layout_data": layout_data}


def test_surprising_stat_layout_data_validates():
    REG.validate("script", _script({"kind": "surprising_stat",
        "stat": {"value": "90%", "source_ref": "market.day_traders"},
        "unpack": {"text": "u"}, "so_what": {"text": "s"}}))


def test_malformed_layout_data_rejected():
    with pytest.raises(SchemaError):
        REG.validate("script", _script({"kind": "surprising_stat", "stat": {"value": "90%"}}))  # missing source_ref
```

- [ ] **Step 3: Run** → `uv run pytest tests/test_format_layouts_validate.py -v` → PASS (2).
- [ ] **Step 4: Commit**

```bash
git add schemas/script.schema.json tests/test_format_layouts_validate.py
git commit -m "feat(m3): script.schema layout_data branches for the 6 new formats (Ch.6)"
```

## Phase A2 — Author the 6 region specs + 8 format configs

### Task 2: Author `formats/<fmt>/layout.json` for the 6 new formats

Each follows the ADR 0007a region model (M2's `layout.schema`): inclusive `colA–colB`, `(anchor | {y,h})`, the 8-primitive enum, `bind` dotted-or-`"static"`, optional `on`. Author all six to the contracts below. **Worked example — `explainer`** (worked-through number as `count_up` `TextCard` steps, the pinned decision):

**Files:** Create `formats/{myth_buster,explainer,news_reaction,cautionary_tale,surprising_stat,how_to_steps}/layout.json`; Test reuses `tests/test_format_layouts_validate.py`

- [ ] **Step 1: Write `formats/explainer/layout.json`**

```json
{
  "schema_version": "1.0.0",
  "format": "explainer",
  "beat_pattern": ["hook", "concept", "step", "step", "takeaway", "cta"],
  "anchors": {"concept_title": [0.10, 0.14], "step_num": [0.40, 0.20], "takeaway": [0.70, 0.16]},
  "regions": [
    {"name": "bg_media", "bbox": {"colA": 1, "colB": 12, "y": 0.0, "h": 1.0}, "z": 0,
     "primitive": {"type": "MediaZone", "params": {"fit": "cover", "kenburns": true}},
     "bind": "concept.title", "on": ["concept", "step", "takeaway"], "enter": "fade", "exit": "fade", "style": "brand.media"},
    {"name": "concept_title", "bbox": {"colA": 1, "colB": 12, "anchor": "concept_title"}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "display"}},
     "bind": "concept.title", "on": ["concept"], "enter": "slide_in_up", "exit": "fade", "style": "brand.title"},
    {"name": "step_value", "bbox": {"colA": 1, "colB": 12, "anchor": "step_num"}, "z": 3,
     "primitive": {"type": "TextCard", "params": {"role": "numeric"}},
     "bind": "step.value", "on": ["step"], "enter": "count_up", "exit": "fade", "style": "brand.stat"},
    {"name": "step_label", "bbox": {"colA": 1, "colB": 12, "anchor": "stat"}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "label"}},
     "bind": "step.label", "on": ["step"], "enter": "fade", "exit": "fade", "style": "brand.label"},
    {"name": "takeaway", "bbox": {"colA": 1, "colB": 12, "anchor": "takeaway"}, "z": 2,
     "primitive": {"type": "TextCard", "params": {"role": "display"}},
     "bind": "takeaway.text", "on": ["takeaway"], "enter": "riser_reveal", "exit": "fade", "style": "brand.verdict"}
  ]
}
```

- [ ] **Step 2: Author the other 5** to these region contracts (every `bind` must exist in the format's `layout_data` from Task 1; gate beat-specific regions with `on`):

| format | beat_pattern | key regions (name → bind, primitive, on) |
|---|---|---|
| `myth_buster` | hook, claim, truth, cta | `claim`→`claim.text` TextCard `[claim]`; `false_stamp`→`static` Badge(stamp,"MYTH") `[claim]`; `truth`→`truth.text` TextCard `[truth]`; `why`→`why_wrong.text` TextCard `[truth]` |
| `news_reaction` | hook, event, implication, implication, takeaway, cta | `headline`→`event.headline` TextCard `[event]`; `citation`→`event.source_ref` CitationChip `[event]`; `implication`→`implications.0.text`* TextCard `[implication]`; `takeaway`→`takeaway.text` TextCard `[takeaway]` |
| `cautionary_tale` | hook, setup, mistake, cost, lesson, cta | `setup`→`setup.text` TextCard `[setup]`; `mistake`→`mistake.text` TextCard `[mistake]`; `cost`→`cost.stat` TextCard numeric count_up `[cost]`; `lesson`→`lesson.text` TextCard `[lesson]` |
| `surprising_stat` | hook, stat, unpack, so_what, cta | `stat`→`stat.value` TextCard numeric count_up `[stat]`; `citation`→`stat.source_ref` CitationChip `[stat]`; `unpack`→`unpack.text` TextCard `[unpack]`; `so_what`→`so_what.text` TextCard `[so_what]` |
| `how_to_steps` | hook, step, step, step, cta | `step_num`→`step.n` Badge(circle) `[step]`; `step_title`→`step.title` TextCard display `[step]`; `step_body`→`step.body` TextCard body `[step]` (vertical stack via format anchors) |

*\*indexed binds (`implications.0.text`) require a list-index step in `_resolve_bind`; see Task 3 Step 2.*

- [ ] **Step 3: Extend `tests/test_format_layouts_validate.py`** with a sweep that every `formats/*/layout.json` validates against `layout.schema`

```python
ROOT = Path(__file__).resolve().parents[1]
ALL_FORMATS = ["ranked_list", "head_to_head", "myth_buster", "explainer",
               "news_reaction", "cautionary_tale", "surprising_stat", "how_to_steps"]


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_layout_validates(fmt):
    REG.validate("layout", json.loads((ROOT / f"formats/{fmt}/layout.json").read_text()))
```

- [ ] **Step 4: Run** → PASS (8 layouts validate). **Commit.**

```bash
git add formats/ tests/test_format_layouts_validate.py
git commit -m "feat(m3): author the 6 remaining format region specs as data (ADR 0007a §7b/§11)"
```

### Task 3: Resolve-time bind validation for all 8 formats (+ list-index binds)

ADR 0007a §3: every region `bind` must exist in that format's typed beat contract. M2's `validate_binds`/`_resolve_bind` handle dotted paths; `news_reaction` needs list-index binds (`implications.0.text`).

**Files:** Modify `shared/layout/bind.py`, `shared/layout/resolve.py`; Test `tests/test_format_layouts_validate.py`

- [ ] **Step 1: Write the failing test** (a list-index bind resolves; a missing index raises)

```python
def test_indexed_bind_resolves_and_missing_raises():
    from shared.layout.bind import _exists
    from shared.layout.resolve import _resolve_bind
    from shared.layout.bind import BindError
    import pytest as _pt
    beat = {"kind": "implication", "implications": [{"text": "first"}]}
    assert _exists("implications.0.text", beat) is True
    assert _resolve_bind("implications.0.text", beat, {"params": {}}) == "first"
    with _pt.raises(BindError):
        _resolve_bind("implications.5.text", beat, {"params": {}})
```

- [ ] **Step 2: Add `_walk` and wire it into BOTH `_exists` and `_resolve_bind`** (the M2 versions had dict-only loops). `_walk(node, path)` is **node-first**; callers pass node-first. `shared/layout/bind.py`:

```python
def _walk(node, path: str):
    """Walk a dotted path with optional integer list indices. Returns (value, found)."""
    for part in path.split("."):
        if part.isdigit() and isinstance(node, list):
            i = int(part)
            if i >= len(node):
                return None, False
            node = node[i]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None, False
    return node, True


def _exists(path: str, data: dict) -> bool:
    return _walk(data, path)[1]


def validate_binds(binds: list[str], beat_data: dict) -> None:
    for b in binds:
        if b == "static":            # ADR 0007a §3 exempt case
            continue
        if not _exists(b, beat_data):
            raise BindError(f"region bind {b!r} not in beat data")
```

And in `shared/layout/resolve.py` — update the import and replace `_resolve_bind`'s walk loop (keep the `static` short-circuit):

```python
from shared.layout.bind import BindError, _walk, validate_binds


def _resolve_bind(bind: str, beat: dict, primitive: dict):
    if bind == "static":
        return primitive.get("params", {}).get("content")   # §3: content from the primitive
    value, found = _walk(beat, bind)
    if not found:
        raise BindError(f"bind {bind!r} missing in beat {beat.get('kind')!r}")
    return value
```

- [ ] **Step 3: Run** → PASS. **Commit.**

```bash
git add shared/layout/bind.py shared/layout/resolve.py tests/test_format_layouts_validate.py
git commit -m "feat(m3): list-index binds for news_reaction (ADR 0007a §3)"
```

### Task 4: Format registry + lane×format compatibility (ADR 0008 D2)

`format.json` carries `lane_support` (`reach`/`monetization`/`both`) + content-scaling; the batch selector must only pick compatible format×lane pairs.

**Files:** Create `formats/<fmt>/format.json` (8), `shared/formats/__init__.py`, `shared/formats/registry.py`; Test `tests/test_formats_registry.py`, `tests/test_lane_support.py`

- [ ] **Step 1: Author the 8 `format.json`** (M0's `format.schema` validates them). Example `formats/ranked_list/format.json`:

```json
{"schema_version": "1.0.0", "id": "ranked_list", "beat_pattern": ["hook", "item", "item", "item", "cta"],
 "lane_support": {"reach": true, "monetization": true}, "data_shape": "ranked_list"}
```

Lane support per ADR 0006 D1 / 0008 D2: `surprising_stat`/`myth_buster`/`news_reaction` → reach+both; `explainer`/`cautionary_tale`/`head_to_head` → monetization; `ranked_list`/`how_to_steps` → both (scaled).

> **Content-scaling note (ADR 0008 D2):** the *item-count sizing* (top-3 in the reach lane vs top-7–10 in monetization; 3 vs 5+ steps) is a **00b sizing behavior** — 00b emits fewer `items[]`/`steps[]` for the reach lane. M3 declares **`lane_support` here** (the gate) but **defers the sizing logic to 00b's format-selection** (built in M1; the lane→count rule is a 00b prompt/validation concern, tracked there), so M3 does not add a `content_scaling` field. This keeps M3 scoped to the format *data* + the compatibility gate.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_lane_support.py
from shared.formats.registry import FormatRegistry, compatible


def test_compatible_only_for_supported_lane():
    reg = FormatRegistry()
    assert compatible(reg.get("explainer"), lane="monetization") is True
    assert compatible(reg.get("explainer"), lane="reach") is False


def test_all_eight_formats_load():
    reg = FormatRegistry()
    assert len(reg.all()) == 8
```

- [ ] **Step 3: Implement `shared/formats/registry.py`**

```python
import json
from pathlib import Path
from shared.schema import SchemaRegistry

_ROOT = Path(__file__).resolve().parents[2] / "formats"
_REG = SchemaRegistry()


def compatible(fmt: dict, lane: str) -> bool:
    return bool(fmt.get("lane_support", {}).get(lane, False))


class FormatRegistry:
    def __init__(self, root: Path = _ROOT):
        self._fmts = {}
        for p in sorted(root.glob("*/format.json")):
            fmt = json.loads(p.read_text())
            _REG.validate("format", fmt)
            self._fmts[fmt["id"]] = fmt

    def get(self, fid: str) -> dict:
        return self._fmts[fid]

    def all(self) -> list[dict]:
        return list(self._fmts.values())
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add formats/ shared/formats/ tests/test_formats_registry.py tests/test_lane_support.py
git commit -m "feat(m3): format registry + lane x format compatibility (ADR 0008 D2)"
```

---

# Part B — Audio performance layer

### Task 4c: Stage 02 — per-beat prosody → Kokoro (ADR 0005 D6)

M1's Stage 02 normalizes + joins beats but **ignores the script's per-beat prosody/emphasis markup**. ADR 0005 D6 requires prosody (emphasis/pause/pace, incl. a deliberate hook delivery) driving Kokoro. M3 closes this: a pure `speech_segments(script)` maps each beat's `prosody` to per-segment params, and Stage 02 synthesizes per segment.

**Files:** Modify `shared/finance/normalize.py` or new `shared/audio/prosody.py`; Modify `stages/s02_voice/stage.py`; Test `tests/test_prosody.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prosody.py
from shared.audio.prosody import speech_segments


def test_maps_prosody_to_segment_params_and_normalizes_text():
    script = {"narration_beats": [
        {"text": "CPI hit 3.2%", "prosody": "emphatic", "emphasis": ["3.2%"]},
        {"text": "Slow down here", "prosody": "measured"}]}
    segs = speech_segments(script)
    assert segs[0]["text"].endswith("percent") and segs[0]["rate"] < 1.0   # emphatic = slower, deliberate
    assert segs[0]["pause_after"] >= 0.3
    assert segs[1]["rate"] == 1.0                                          # measured = baseline
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/audio/prosody.py`**

```python
from shared.finance.normalize import normalize

# closed prosody vocabulary -> Kokoro per-segment params (rate multiplier, trailing pause seconds)
_PROSODY = {"emphatic": (0.9, 0.35), "rising": (1.05, 0.15), "measured": (1.0, 0.2),
            "fast": (1.15, 0.1), "pause": (1.0, 0.5)}


def speech_segments(script: dict) -> list[dict]:
    """One synth segment per narration beat: normalized text + rate + trailing pause from prosody."""
    segs = []
    for b in script.get("narration_beats", []):
        rate, pause = _PROSODY.get(b.get("prosody", "measured"), (1.0, 0.2))
        segs.append({"text": normalize(b["text"]), "rate": rate, "pause_after": pause,
                     "emphasis": b.get("emphasis", [])})
    return segs
```

- [ ] **Step 4: Wire into `stages/s02_voice/stage.py`** — replace the single `tts(spoken_text(script))` call with per-segment synthesis + concatenation (the segment-level rate is the Kokoro control; concatenation inserts `pause_after` silence). Keep `spoken_text` for the keyword-early check. The `KokoroBackend.tts` integration call gains an optional `rate` param (default 1.0); concatenation/silence is done with `numpy` in the backend. Show the 02 `run()` change:

```python
    segments = speech_segments(script)
    wav = ctx.backend("tts").tts_segments(segments)   # synth each seg at its rate + pause, concat
```

and add `tts_segments(self, segments) -> Path` to `KokoroBackend` (loops `tts` per segment at `rate`, concatenates with `np.zeros(int(pause*sr))` between) — `@pytest.mark.integration` for the live path; `speech_segments` is the CI-tested pure unit.

- [ ] **Step 5: Run** → `uv run pytest tests/test_prosody.py -v` → PASS. **Commit.**

```bash
git add shared/audio/prosody.py stages/s02_voice/stage.py shared/adapters/real.py tests/test_prosody.py
git commit -m "feat(m3): per-beat prosody driving Kokoro (ADR 0005 D6)"
```

### Task 5: Music selection — closed taxonomy + deterministic anti-repeat

ADR 0005 D6 / ADR 0009: closed mood/energy taxonomy tied to format; curated per-niche library; anti-repeat across the batch.

**Files:** Create `shared/audio/__init__.py`, `shared/audio/music.py`, `tests/fixtures/m3/music_index.json`; Test `tests/test_music.py`

- [ ] **Step 1: Write `tests/fixtures/m3/music_index.json`**

```json
[{"id": "t1", "mood": "confident", "energy": "mid", "path": "music/t1.mp3", "license": "YouTubeAudioLibrary"},
 {"id": "t2", "mood": "confident", "energy": "mid", "path": "music/t2.mp3", "license": "YouTubeAudioLibrary"},
 {"id": "t3", "mood": "tense", "energy": "high", "path": "music/t3.mp3", "license": "YouTubeAudioLibrary"}]
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_music.py
import json
from pathlib import Path
import pytest
from shared.audio.music import select_track, MOODS, ENERGIES, NoTrackError

LIB = json.loads((Path(__file__).parent / "fixtures" / "m3" / "music_index.json").read_text())


def test_select_matches_mood_energy_and_is_seed_deterministic():
    a = select_track(LIB, mood="confident", energy="mid", seed=7, recent_ids=set())
    b = select_track(LIB, mood="confident", energy="mid", seed=7, recent_ids=set())
    assert a["id"] == b["id"] and a["mood"] == "confident" and a["energy"] == "mid"


def test_anti_repeat_excludes_recent():
    chosen = select_track(LIB, mood="confident", energy="mid", seed=7, recent_ids={"t1"})
    assert chosen["id"] == "t2"


def test_taxonomy_is_closed():
    with pytest.raises(ValueError):
        select_track(LIB, mood="spicy", energy="mid", seed=7, recent_ids=set())


def test_no_track_when_all_recent():
    with pytest.raises(NoTrackError):
        select_track(LIB, mood="tense", energy="high", seed=1, recent_ids={"t3"})
```

- [ ] **Step 3: Implement `shared/audio/music.py`**

```python
import random

MOODS = {"confident", "tense", "uplifting", "somber", "neutral"}
ENERGIES = {"low", "mid", "high"}


class NoTrackError(Exception):
    """No library track matches (mood, energy) after anti-repeat exclusion."""


def select_track(library: list[dict], *, mood: str, energy: str, seed: int,
                 recent_ids: set[str]) -> dict:
    if mood not in MOODS or energy not in ENERGIES:
        raise ValueError(f"unknown mood/energy: {mood}/{energy}")
    pool = [t for t in library if t["mood"] == mood and t["energy"] == energy
            and t["id"] not in recent_ids]
    if not pool:
        raise NoTrackError(f"no track for {mood}/{energy} (recent={recent_ids})")
    pool.sort(key=lambda t: t["id"])               # stable order before seeded pick
    return random.Random(seed).choice(pool)
```

- [ ] **Step 4: Run** → PASS (4). **Commit.**

```bash
git add shared/audio/__init__.py shared/audio/music.py tests/fixtures/m3/music_index.json tests/test_music.py
git commit -m "feat(m3): music taxonomy + deterministic anti-repeat selection (ADR 0005 D6/0009)"
```

### Task 6: SFX cue mapping + per-platform LUFS

ADR 0005 D6: transition-SFX layer (whoosh/tick/reveal) + per-platform LUFS.

**Files:** Create `shared/audio/sfx.py`, `shared/audio/loudness.py`; Test `tests/test_sfx.py`, `tests/test_loudness.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sfx.py
from shared.audio.sfx import cues_for_scenes


def test_tick_per_list_item_and_riser_on_reveal():
    scenes = [{"kind": "hook"}, {"kind": "item"}, {"kind": "item"}, {"kind": "cta"}]
    cues = cues_for_scenes(scenes)
    kinds = [c["sfx"] for c in cues]
    assert kinds.count("tick") == 2          # one per item
    assert "whoosh" in kinds                  # transitions
```

```python
# tests/test_loudness.py
from shared.audio.loudness import loudnorm_args, target_lufs


def test_platform_targets():
    assert target_lufs("youtube") == -14.0 and target_lufs("tiktok") == -14.0


def test_loudnorm_args_string():
    a = loudnorm_args("youtube")
    assert "loudnorm" in a and "I=-14" in a and "TP=-1" in a
```

- [ ] **Step 2: Implement `shared/audio/sfx.py`**

```python
def cues_for_scenes(scenes: list[dict]) -> list[dict]:
    """Map scene kinds to transition SFX: whoosh on each cut, tick per list item,
    riser+impact on a reveal beat (verdict/takeaway/so_what)."""
    cues = []
    reveal = {"verdict", "takeaway", "so_what", "truth"}
    for i, s in enumerate(scenes):
        if i > 0:
            cues.append({"at_scene": i, "sfx": "whoosh"})
        if s["kind"] in ("item", "step"):
            cues.append({"at_scene": i, "sfx": "tick"})
        if s["kind"] in reveal:
            cues.append({"at_scene": i, "sfx": "riser"})
    return cues
```

- [ ] **Step 3: Implement `shared/audio/loudness.py`**

```python
_TARGETS = {"youtube": -14.0, "tiktok": -14.0}


def target_lufs(platform: str) -> float:
    return _TARGETS.get(platform, -14.0)


def loudnorm_args(platform: str, true_peak: float = -1.0) -> str:
    return f"loudnorm=I={target_lufs(platform):g}:TP={true_peak:g}:LRA=11"
```

- [ ] **Step 4: Run** → both PASS. **Commit.**

```bash
git add shared/audio/sfx.py shared/audio/loudness.py tests/test_sfx.py tests/test_loudness.py
git commit -m "feat(m3): SFX cue mapping + per-platform LUFS (ADR 0005 D6)"
```

### Task 7: Stage 04 music — wire selection + SFX + loudnorm into the mix

**Files:** Modify `stages/s04_music/stage.py` (+ `manifest.json`); Test `tests/test_s04_music.py`

- [ ] **Step 1: Write the failing test** (pure: the ffmpeg mix command applies loudnorm + sidechain duck)

```python
# tests/test_s04_music.py
from pathlib import Path
from stages.s04_music.stage import build_mix_cmd


def test_mix_applies_duck_and_loudnorm(tmp_path):
    cmd = build_mix_cmd(narration=tmp_path / "narration.wav", music=tmp_path / "t1.mp3",
                        platform="youtube", out=tmp_path / "music.wav")
    s = " ".join(cmd)
    assert "sidechaincompress" in s and "loudnorm=I=-14" in s and s.endswith(str(tmp_path / "music.wav"))
```

- [ ] **Step 2: Implement `stages/s04_music/stage.py`**

```python
import json
import subprocess

from shared.audio.loudness import loudnorm_args
from shared.audio.music import select_track
from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


def build_mix_cmd(*, narration, music, platform: str, out) -> list[str]:
    # duck music under VO (sidechain), then normalize the bed to the platform target
    fc = (f"[1:a]sidechaincompress=threshold=0.05:ratio=8[duck];"
          f"[0:a][duck]amix=inputs=2:duration=longest,{loudnorm_args(platform)}[a]")
    return ["ffmpeg", "-y", "-i", str(narration), "-i", str(music),
            "-filter_complex", fc, "-map", "[a]", str(out)]


@stage(StageManifest(id="04", inputs=["script", "narration"], outputs=["music"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    library = json.loads((ctx.run_dir / ctx.config.get("music_index", "music/index.json")).read_text())
    recent = set(ctx.config.get("recent_track_ids", []))   # batch anti-repeat (resolved from ledger)
    track = select_track(library, mood=script["music"]["mood"], energy=script["music"]["energy"],
                         seed=ctx.seed, recent_ids=recent)
    out = ctx.write_output("music")
    plat = ctx.job.get("platform_targets", ["youtube"])[0]
    subprocess.run(build_mix_cmd(narration=ctx.read_input("narration"),
                                 music=ctx.run_dir / track["path"], platform=plat, out=out), check=True)
    ctx.log.info("music mixed", track=track["id"])
    return StageResult(outputs={"music": out})
```

- [ ] **Step 3: Write `manifest.json`** → `{"id": "04", "inputs": ["script", "narration"], "outputs": ["music"], "compute": "cpu"}`. **Run** → PASS. **Commit.**

```bash
git add stages/s04_music/ tests/test_s04_music.py
git commit -m "feat(m3): 04 music mix (select + duck + loudnorm, ADR 0005 D6)"
```

---

# Part C — Vision pass (05x) + creative-QC gate (05c)

### Task 8: `QwenVLBackend` (implements `vlm_judge`)

ADR 0008 D1: Qwen2.5-VL over sampled keyframes; GPU citizen, never-co-resident.

**Files:** Modify `shared/adapters/real.py`; Test `tests/test_qwenvl_backend.py`

- [ ] **Step 1: Write the failing tests** (Protocol conformance + request shape; live call integration)

```python
# tests/test_qwenvl_backend.py
import pytest
from shared.adapters import ModelBackend
from shared.adapters.real import QwenVLBackend


def test_qwenvl_satisfies_protocol():
    assert isinstance(QwenVLBackend(base_url="http://h:8000", model="Qwen2.5-VL"), ModelBackend)


@pytest.mark.integration
def test_vlm_judge_live(tmp_path):
    from PIL import Image
    Image.new("RGB", (108, 192), (12, 30, 18)).save(tmp_path / "hook.png")
    be = QwenVLBackend(base_url="http://127.0.0.1:11434", model="qwen2.5-vl")  # Ollama OpenAI-compat
    j = be.vlm_judge([tmp_path / "hook.png"], {"hook": {"spoken": "x"}})
    assert set(j.scores) == {"coherence", "pacing"}      # visual sub-scores only (ADR 0016 D5)
    assert isinstance(j.observations, tuple)
```

- [ ] **Step 2: Add `QwenVLBackend` to `shared/adapters/real.py`** (implements the full `ModelBackend` surface; non-VLM methods raise)

```python
_OBSERVE_PROMPT = (
    "You are inspecting rendered video keyframes. Return STRICT JSON: "
    '{"coherence": 0-1, "pacing": 0-1, "observations": ["..."]} — observations are concrete, '
    "per-frame notes (artifacts, morphing hands, garbled/occluded text, caption overlap, "
    "composition). Score ONLY what you can SEE; do not judge the script's ideas.\n\nSCRIPT: ")


class QwenVLBackend:
    """ModelBackend.vlm_judge via an OpenAI-compatible chat endpoint with image content
    (e.g. Ollama /v1/chat/completions serving Qwen2.5-VL) — ADR 0016 D5. Returns
    OBSERVATIONS + the visual sub-scores (coherence/pacing); verdicts belong to the gates."""

    def __init__(self, base_url: str, model: str = "qwen2.5-vl", timeout: float = 300.0):
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def vlm_judge(self, frames, script):
        import base64
        import json
        import httpx
        from pathlib import Path
        from shared.adapters.types import Judgment
        content = [{"type": "text", "text": _OBSERVE_PROMPT + json.dumps(script)}]
        for f in frames:
            b64 = base64.b64encode(Path(f).read_bytes()).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"}})
        r = httpx.post(f"{self._base}/v1/chat/completions",
                       json={"model": self._model,
                             "messages": [{"role": "user", "content": content}],
                             "response_format": {"type": "json_object"}},   # constrained JSON (re-review)
                       timeout=self._timeout)
        r.raise_for_status()
        d = json.loads(r.json()["choices"][0]["message"]["content"])
        visual = {"coherence": float(d["coherence"]), "pacing": float(d["pacing"])}
        # overall/passed are advisory — 05c owns the authoritative, config-driven quality floor.
        return Judgment(overall=sum(visual.values()) / len(visual), scores=visual,
                        passed=False, observations=tuple(d.get("observations", [])))

    def llm(self, prompt, seed=None): raise NotImplementedError
    def llm_json(self, prompt, seed=None): raise NotImplementedError
    def tts(self, text): raise NotImplementedError
    def generate_image(self, prompt, seed): raise NotImplementedError
    def img2vid(self, image, seed): raise NotImplementedError
    def restore(self, frames): raise NotImplementedError
```

- [ ] **Step 3: Run** → `uv run pytest tests/test_qwenvl_backend.py -m "not integration" -v` → PASS (1). **Commit.**

```bash
git add shared/adapters/real.py tests/test_qwenvl_backend.py
git commit -m "feat(m3): QwenVL backend implementing vlm_judge (ADR 0008 D1)"
```

### Task 9: Keyframe sampling (pure) + Stage 05x

**Files:** Create `shared/qc/__init__.py`, `shared/qc/sampling.py`, `stages/s05x_vision/{stage.py,manifest.json}`; Test `tests/test_sampling.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sampling.py
from shared.qc.sampling import sample_frames


def test_includes_hook_endcard_markers_and_caps_at_8():
    manifest = {"fps": 30, "markers": {"cta_bump": 90},
                "scenes": [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0},
                           {"start": 4.0, "end": 6.0}]}
    total_frames = 180
    idx = sample_frames(manifest, total_frames)
    assert 0 in idx and (total_frames - 1) in idx and 90 in idx
    assert len(idx) <= 8 and idx == sorted(set(idx))
```

- [ ] **Step 2: Implement `shared/qc/sampling.py`**

```python
def sample_frames(manifest: dict, total_frames: int, cap: int = 8) -> list[int]:
    """Hook (0), end-card (last), manifest markers, + one mid-frame per scene; deduped, capped."""
    fps = manifest["fps"]
    idx = {0, total_frames - 1}
    idx.update(int(v) for v in manifest.get("markers", {}).values())
    for s in manifest.get("scenes", []):
        idx.add(int(((s["start"] + s["end"]) / 2) * fps))
    ordered = sorted(i for i in idx if 0 <= i < total_frames)
    if len(ordered) <= cap:
        return ordered
    # keep hook + end-card + evenly-spaced middle picks
    keep = {ordered[0], ordered[-1]}
    step = max(1, (len(ordered) - 2) // (cap - 2))
    keep.update(ordered[1:-1:step])
    return sorted(keep)[:cap]
```

- [ ] **Step 3: Implement `stages/s05x_vision/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.qc.sampling import sample_frames
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()


@stage(StageManifest(id="05x", inputs=["render", "script"], outputs=["vision"],
                     compute="gpu", capability="vlm_judge"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    manifest = json.loads((ctx.run_dir / "render_manifest.json").read_text())
    total = _frame_count(ctx.read_input("render"))            # ffprobe, integration
    indices = sample_frames(manifest, total)
    frame_paths = _extract_frames(ctx.read_input("render"), indices)   # integration
    judgment = ctx.backend("vlm_judge").vlm_judge(frame_paths, script)

    def _kind(i: int) -> str:                # 05b (M5) needs the hook/end-card distinction
        return "hook" if i == 0 else "end_card" if i == total - 1 else "beat"

    vision = {"schema_version": "1.0.0",
              "keyframes": [{"frame_id": str(idx), "kind": _kind(idx), "observations": []}
                            for idx in indices],
              "judgment": {"visual_scores": judgment.scores,                  # coherence, pacing
                           "observations": list(judgment.observations)}}      # ADR 0016 D5
    _REG.validate("vision", vision)          # boundary validation (Ch.5); judgment keys pinned in schema
    out = ctx.write_output("vision")
    out.write_text(json.dumps(vision))
    ctx.log.info("vision pass complete", frames=len(frame_paths))
    return StageResult(outputs={"vision": out})


def _frame_count(render):
    raise NotImplementedError("ffprobe frame count wired at integration; sampling is unit-tested")
def _extract_frames(render, indices):
    raise NotImplementedError("ffmpeg frame extraction wired at integration")
```

> **Dual-consumer contract (ADR 0008 D1 / 0016 D4-D5):** `vision.json` is read by **both** `05c` (this milestone — the visual sub-scores + observations feed its independent judge) **and** `05b` (M5 — artifact/garbled-text/caption-occlusion via `keyframes[].kind` + the observations). 05x runs **once, on the YouTube cut** (per-platform geometry is checked deterministically per cut in 05b — ADR 0016 D4), emits the VLM's **observations + visual sub-scores, never verdicts**, and **shapes `kind` faithfully** (hook/end_card/beat) so M5's 05b consumes the contract unchanged.

- [ ] **Step 3b: Extend `schemas/vision.schema.json`** — add the optional `judgment` block and **pin the visual sub-score keys** so the 05x→05c contract can't drift (the M0 schema was `keyframes`-only + `additionalProperties:false`, which would reject `judgment`). Per ADR 0016 D5 the VLM contributes only what it can *see* — the text-judged criteria (`hook`/`original_insight`/`payoff`) are scored by 05c's independent judge, not stored here:

```json
{
  "judgment": {
    "type": "object", "additionalProperties": false,
    "required": ["visual_scores", "observations"],
    "properties": {
      "visual_scores": {
        "type": "object", "additionalProperties": false,
        "required": ["coherence", "pacing"],
        "properties": {"coherence": {"type": "number"}, "pacing": {"type": "number"}}
      },
      "observations": {"type": "array", "items": {"type": "string"}}
    }
  }
}
```

Add `judgment` to `vision.schema`'s top-level `properties` (it stays optional — not in `required` — so an `observations`-only instance still validates). A `test_vision_judgment_schema` asserts a `judgment` with the two visual keys + observations validates and one missing a key fails.

- [ ] **Step 4: Write `manifest.json`** → `{"id": "05x", "inputs": ["render", "script"], "outputs": ["vision"], "compute": "gpu", "capability": "vlm_judge"}`. **Run** → PASS. **Commit** (include `schemas/vision.schema.json`).

```bash
git add shared/qc/__init__.py shared/qc/sampling.py schemas/vision.schema.json stages/s05x_vision/ tests/test_sampling.py
git commit -m "feat(m3): 05x vision pass + vision.schema judgment block (keyframes + Qwen2.5-VL, ADR 0008 D1)"
```

### Task 10: Stage 05c creative-QC — rubric + floor gate (with original-insight)

ADR 0005 D2 + ADR 0014 D1 + ADR 0016 D1/D5: the **independent, non-Qwen judge** (resolved via 05c's `llm` capability — the author model never grades its own survival criterion) scores the *text* criteria (`hook`, `original_insight`, `payoff`) from script + treatment + the 05x **observations**; these merge with the 05x **visual sub-scores** (`coherence`, `pacing`) under the rubric weights; below the floor → quarantine.

**Files:** Create `shared/qc/creative.py`, `stages/s05c_qc/{stage.py,manifest.json}`; Test `tests/test_creative_qc.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_creative_qc.py
import pytest
from shared.qc.creative import RUBRIC, weighted_overall, passes_floor, CRITERIA


def test_rubric_has_original_insight_weighted_030():
    assert "original_insight" in CRITERIA
    assert RUBRIC["original_insight"] == 0.30


def test_weights_sum_to_one():
    assert abs(sum(RUBRIC.values()) - 1.0) < 1e-9


def test_weighted_overall_and_floor():
    scores = {"hook": 0.9, "original_insight": 0.4, "coherence": 0.8, "pacing": 0.8, "payoff": 0.8}
    o = weighted_overall(scores)
    assert abs(o - (0.9*0.2 + 0.4*0.3 + 0.8*0.2 + 0.8*0.15 + 0.8*0.15)) < 1e-9
    assert passes_floor(o, floor=0.70) is (o >= 0.70)


def test_missing_criterion_raises():
    with pytest.raises(KeyError):
        weighted_overall({"hook": 0.9})


def test_05c_merges_independent_text_judge_with_visual_scores():
    from stages.s05c_qc.stage import _judge_text

    class _IndependentJudge:                      # non-Qwen judge fake (ADR 0016 D1)
        def llm_json(self, prompt, seed=None):
            return {"hook": 0.8, "original_insight": 0.7, "payoff": 0.9}

    text = _judge_text(_IndependentJudge(), {"format": "x"}, ["clean frames"])
    assert set(text) == {"hook", "original_insight", "payoff"}
    merged = {**{"coherence": 0.8, "pacing": 0.85}, **text}
    assert set(merged) == {"hook", "original_insight", "coherence", "pacing", "payoff"}
```

- [ ] **Step 2: Implement `shared/qc/creative.py`**

```python
# ADR 0005 D2 + ADR 0014 D1: 5 criteria; original_insight is the policy-survival criterion (0.30).
RUBRIC = {"hook": 0.20, "original_insight": 0.30, "coherence": 0.20, "pacing": 0.15, "payoff": 0.15}
CRITERIA = set(RUBRIC)


def weighted_overall(scores: dict[str, float]) -> float:
    return sum(scores[c] * w for c, w in RUBRIC.items())   # KeyError if a criterion is missing


def passes_floor(overall: float, floor: float = 0.70) -> bool:
    return overall >= floor
```

- [ ] **Step 3: Implement `stages/s05c_qc/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.qc.creative import passes_floor, weighted_overall
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()


def _judge_text(llm, script: dict, observations: list[str]) -> dict:
    """The INDEPENDENT judge (non-Qwen lineage, resolved per-stage — ADR 0016 D1) scores the
    text-judgeable criteria from script + treatment + the 05x render observations."""
    prompt = ("Score 0-1 each of: hook, original_insight (a non-obvious, specific point of view — "
              "NOT a generic template fill), payoff. Respond as STRICT JSON "
              '{"hook": x, "original_insight": y, "payoff": z}.\n\n'
              f"SCRIPT: {json.dumps(script)}\nRENDER OBSERVATIONS: {json.dumps(observations)}")
    return llm.llm_json(prompt)   # constrained JSON + bounded retry (re-review)


@stage(StageManifest(id="05c", inputs=["render", "vision", "script"], outputs=["creative_qc"],
                     compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    vision = json.loads(ctx.read_input("vision").read_text())
    script = json.loads(ctx.read_input("script").read_text())
    visual = vision["judgment"]["visual_scores"]                 # coherence, pacing (05x VLM)
    text = _judge_text(ctx.backend("llm"), script, vision["judgment"]["observations"])
    scores = {**visual, **text}                                  # the full 5-criterion rubric
    overall = weighted_overall(scores)
    floor = float(ctx.config.get("quality_floor", 0.70))
    ok = passes_floor(overall, floor)
    payload = {"schema_version": "1.0.0", "scores": scores,
               "overall": overall, "floor": floor, "pass": ok}
    _REG.validate("creative_qc", payload)            # boundary validation (Ch.5)
    out = ctx.write_output("creative_qc")
    out.write_text(json.dumps(payload))              # write the artifact BEFORE any quarantine raise
    if not ok:
        ctx.quarantine(f"creative-QC below floor: {overall:.3f} < {floor}")
    ctx.log.info("creative-QC pass", overall=round(overall, 3))
    return StageResult(outputs={"creative_qc": out})
```

- [ ] **Step 4: Write `manifest.json`** → `{"id": "05c", "inputs": ["render", "vision", "script"], "outputs": ["creative_qc"], "compute": "cpu", "capability": "llm"}` (cpu stage carrying a capability — mirror it, per the M0 drift-catcher note). **Run** → PASS (4). **Commit.**

```bash
git add shared/qc/creative.py stages/s05c_qc/ tests/test_creative_qc.py
git commit -m "feat(m3): 05c creative-QC rubric + floor gate w/ original-insight (ADR 0005 D2/0014 D1)"
```

---

# Part D — Persona / brand kit + the business niche

### Task 11: Profile loader + finance & business profiles (two-niche proof)

ADR 0005 D9 / ADR 0010 D5: profiles are validated data (`profile.schema`); persona + brand kit; the business profile proves the two-niche abstraction.

**Files:** Create `shared/profiles/__init__.py`, `shared/profiles/loader.py`, `profiles/finance/profile.yaml`, `profiles/business/profile.yaml`; Test `tests/test_profiles_loader.py`, `tests/test_business_slice_offline.py`

- [ ] **Step 1: Write `profiles/finance/profile.yaml`** (and `business` to the same shape)

```yaml
schema_version: "1.0.0"
niche: finance
persona:
  voice: "a rigorous, data-first finance explainer who distrusts hype"
  pov: "long-term, evidence over vibes"
brand_kit:
  palette: ["#0C1E12", "#00E5FF", "#FFFFFF"]
  font: Inter
  logo: brand/finance_logo.png
defaults:
  music_index: profiles/finance/music/index.json
  emphasis_hex: "00E5FF"
```

And `profiles/business/profile.yaml` — **distinct** persona/brand-kit/library so the niche is provably data, not code:

```yaml
schema_version: "1.0.0"
niche: business
persona:
  voice: "a pragmatic operator who explains business mechanics plainly"
  pov: "incentives and unit economics over hustle-culture"
brand_kit:
  palette: ["#11161D", "#FFB020", "#FFFFFF"]
  font: Inter
  logo: brand/business_logo.png
defaults:
  music_index: profiles/business/music/index.json
  emphasis_hex: "FFB020"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_profiles_loader.py
from pathlib import Path
from shared.profiles.loader import load_profile

ROOT = Path(__file__).resolve().parents[1]


def test_finance_and_business_profiles_load_and_validate():
    for niche in ("finance", "business"):
        p = load_profile(ROOT / "profiles" / niche / "profile.yaml")
        assert p["niche"] == niche
        assert {"palette", "font", "logo"} <= set(p["brand_kit"])
        assert p["persona"]["voice"]
```

- [ ] **Step 3: Implement `shared/profiles/loader.py`** (YAML → dict → `profile.schema` validation)

```python
import json
from pathlib import Path
import yaml                                   # add pyyaml to deps
from shared.schema import SchemaRegistry

_REG = SchemaRegistry()


def load_profile(path: Path) -> dict:
    profile = yaml.safe_load(Path(path).read_text())
    _REG.validate("profile", profile)
    return profile
```

- [ ] **Step 4: Run** → PASS. Add `"pyyaml"` to `pyproject.toml` deps. **Commit.**

```bash
git add shared/profiles/ profiles/ pyproject.toml tests/test_profiles_loader.py
git commit -m "feat(m3): profile loader + finance & business personas/brand kits (ADR 0005 D9)"
```

- [ ] **Step 5: Write the two-niche proof test** — prove the niche is **pure config**: the *same* config-resolution + audio code path takes the **business** profile's data and yields business-specific config (no `if niche ==`), and the DAG itself carries no niche branch (already enforced by M0's `test_no_platform_branches`). This is the honest proof — *not* rerunning finance fixtures with a different seed.

```python
# tests/test_business_slice_offline.py
import shutil
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_business_niche_is_pure_config():
    from shared.profiles.loader import load_profile
    from shared.config import resolve_config
    fin = load_profile(ROOT / "profiles/finance/profile.yaml")
    biz = load_profile(ROOT / "profiles/business/profile.yaml")
    assert (fin["niche"], biz["niche"]) == ("finance", "business")
    # identical resolver call, different niche DATA -> different resolved config (no code branch)
    fin_cfg = resolve_config(global_defaults={"fps": 30}, niche=fin["defaults"], batch={}, per_platform={})
    biz_cfg = resolve_config(global_defaults={"fps": 30}, niche=biz["defaults"], batch={}, per_platform={})
    assert fin_cfg["music_index"] != biz_cfg["music_index"]
    assert fin_cfg["emphasis_hex"] != biz_cfg["emphasis_hex"]
    for p in (fin, biz):                            # both personas + brand kits load + validate (ADR 0005 D9)
        assert {"palette", "font", "logo"} <= set(p["brand_kit"]) and p["persona"]["voice"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_dag_runs_niche_agnostic(run_dir, tmp_path):
    # the DAG carries no niche branch (enforced by test_no_platform_branches), so a run under any
    # niche produces a render — exercised here with the M1 fixture chain.
    from tests.helpers.m1 import run_m1_slice
    result = run_m1_slice(run_dir=run_dir, seed=11, fixtures=ROOT / "tests/fixtures/m1",
                          timing_log=tmp_path / "t.jsonl")
    assert (run_dir / result["render"]).exists()
```

- [ ] **Step 6: Run** → PASS. **Commit.**

```bash
git add tests/test_business_slice_offline.py
git commit -m "test(m3): two-niche proof — business runs the DAG as pure config (ADR 0010 D5)"
```

---

# Part E — Render finishing (the previously-unowned ADR 0005 D4 / 0006 D5/D8 features)

### Task 12: End-card + loop bridge + thumbnail + per-clip color match + cut-rate guard

Spec Ch.4's Stage-05 row promises these; the architecture re-review found no milestone owned them.
They build on M2's compositor: a pure `inject_finishing()` post-resolve step, two small ffmpeg
helpers, and a manifest assertion.

**Files:**
- Create: `shared/layout/finishing.py`
- Modify: `stages/s05_render/stage.py` (wire-in), `stages/s01d_upscale/stage.py` (color-match pass)
- Test: `tests/test_finishing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_finishing.py
import pytest
from shared.layout.finishing import (inject_finishing, build_thumb_cmd,
                                     color_match_args, assert_cut_rate, CutRateError)


def _manifest():
    return {"fps": 30, "markers": {}, "scenes": [
        {"start": 0.0, "end": 2.0, "kind": "hook", "regions": []},
        {"start": 2.0, "end": 4.0, "kind": "item", "regions": []}]}


def test_end_card_injected_on_final_scene_with_platform_verb_and_loop_flag():
    m = inject_finishing(_manifest(), brand_kit={"end_card_phrases": ["Follow or you miss it"]},
                         seed=7, platform="youtube")
    last = m["scenes"][-1]
    card = next(r for r in last["regions"] if r["name"] == "end_card")
    assert "Subscribe" in card["value"]            # platform verb swap (ADR 0006 D8)
    assert m["markers"]["end_card"] == 60          # 2.0s * 30fps
    assert m["loop"]["bridge"] is True             # seamless loop (ADR 0006 D5)


def test_thumb_cmd_grabs_hook_frame():
    cmd = build_thumb_cmd(render="renders/youtube.mp4", out="thumbnail.jpg")
    s = " ".join(cmd)
    assert "-frames:v 1" in s and s.endswith("thumbnail.jpg")   # frame 1 = the designed cover


def test_color_match_args_pulls_toward_target():
    args = color_match_args(clip_mean=80.0, target_mean=120.0)
    assert "eq=brightness=" in args                # per-clip matching BEFORE the grade (D4)


def test_cut_rate_guard():
    assert_cut_rate(_manifest(), max_scene_s=4.0)  # ok
    slow = {"fps": 30, "scenes": [{"start": 0.0, "end": 9.0, "kind": "item", "regions": []}]}
    with pytest.raises(CutRateError):
        assert_cut_rate(slow, max_scene_s=4.0)     # the no-slideshow target (ADR 0005 D4)
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError: shared.layout.finishing`).

- [ ] **Step 3: Implement `shared/layout/finishing.py`**

```python
class CutRateError(Exception):
    """A scene exceeds the visual-change-rate target (the slideshow tell, ADR 0005 D4)."""


def inject_finishing(manifest: dict, *, brand_kit: dict, seed: int, platform: str) -> dict:
    """ADR 0006 D5/D8: the closing end-card is OVERLAID on the final beat (no dead air appended,
    so it cannot defeat the loop bridge) + the loop flag the engine uses to trim/crossfade the
    tail back into frame 0."""
    verb = {"youtube": "Subscribe", "tiktok": "Follow"}.get(platform, "Follow")
    phrases = brand_kit.get("end_card_phrases",
                            ["Follow — the algorithm only shows us once"])
    phrase = phrases[seed % len(phrases)].replace("Follow", verb, 1)
    last = manifest["scenes"][-1]
    last["regions"].append({
        "name": "end_card", "primitive": {"type": "TextCard", "params": {"role": "display"}},
        "rect": {"x": 90, "y": 1340, "w": 900, "h": 300}, "z": 9,
        "enter": "riser_reveal", "exit": "none", "value": phrase,
        "style": brand_kit.get("styles", {}).get("brand.end_card", {})})
    manifest["markers"]["end_card"] = round(last["start"] * manifest["fps"])
    manifest["loop"] = {"bridge": True}
    return manifest


def build_thumb_cmd(*, render: str, out: str) -> list[str]:
    # hook frame = frame 1 = the designed pattern-interrupt (TikTok cover, ADR 0005 D3)
    return ["ffmpeg", "-y", "-i", str(render), "-vf", "select=eq(n\\,0),scale=1080:1920",
            "-frames:v", "1", str(out)]


def color_match_args(*, clip_mean: float, target_mean: float) -> str:
    """Per-clip exposure matching toward the batch median BEFORE the global grade (ADR 0005 D4 —
    a blanket LUT over mismatched exposures fixes nothing)."""
    delta = max(-0.3, min(0.3, (target_mean - clip_mean) / 255.0))
    return f"eq=brightness={delta:.3f}"


def assert_cut_rate(manifest: dict, *, max_scene_s: float = 4.0) -> None:
    for s in manifest["scenes"]:
        if (s["end"] - s["start"]) > max_scene_s:
            raise CutRateError(f"scene {s.get('kind')} runs {s['end'] - s['start']:.1f}s "
                               f"> {max_scene_s}s — add a cut or media change")
```

- [ ] **Step 4: Wire in.** In `stages/s05_render/stage.py`'s per-platform loop, after
  `platform_delta`: `manifest = inject_finishing(manifest, brand_kit=brand_kit, seed=ctx.seed,
  platform=plat)` then `assert_cut_rate(manifest)`; after the **primary** cut's encode, emit the
  cover: `subprocess.run(build_thumb_cmd(render=str(cut), out=str(out.parent / "thumbnail.jpg")),
  check=True)` — and 05's declared outputs gain `thumbnail` (mirror it in `manifest.json`, per the
  M0 drift-catcher rule). **Per-clip color matching** runs in the visual lane: `01d` applies
  `color_match_args` per asset against the batch's median frame mean (one ffmpeg `eq` pass each)
  before `assets.json` is finalized.

- [ ] **Step 5: Run** → `uv run pytest tests/test_finishing.py -v` → PASS (4). **Commit.**

```bash
git add shared/layout/finishing.py stages/s05_render/ stages/s01d_upscale/ tests/test_finishing.py
git commit -m "feat(m3): render finishing — end-card+loop, thumbnail, color match, cut-rate (ADR 0005 D4/0006 D5 D8)"
```

---

## M3 Acceptance Checklist (the testable "done")

- [ ] All **8 `formats/*/layout.json`** validate against `layout.schema`; their `bind`s resolve against each format's `layout_data` contract (incl. `news_reaction` list-index binds) → Tasks 1–3.
- [ ] The **format registry** loads 8 formats; `lane × format` compatibility gates selection (ADR 0008 D2) → Task 4.
- [ ] **Music** selection is seed-deterministic, taxonomy-closed, batch-anti-repeat; **04** mixes with duck + per-platform LUFS; SFX cues map per scene → Tasks 5–7.
- [ ] **05x** samples ≤8 keyframes (hook/end-card/markers/mid), runs once on the YouTube cut via an OpenAI-compatible VLM endpoint, and emits **observations + visual sub-scores, not verdicts**; **05c**'s **independent non-Qwen judge** (ADR 0016 D1/D5) scores the text criteria, merges with the visual pair (original-insight 0.30), and **quarantines below the 0.70 floor** → Tasks 8–10.
- [ ] **finance + business** profiles load + validate; the business niche runs the offline DAG as pure config (two-niche abstraction proven) → Task 11.
- [ ] **Render finishing**: the end-card + loop flag are injected on the final beat (platform verb swapped), the thumbnail/cover is emitted from the hook frame, per-clip color matching runs in 01d, and the cut-rate guard rejects slideshow pacing → Task 12.
- [ ] CI stays GPU-free (`-m "not integration"`); VLM/ffmpeg calls are integration-marked.

---

## Self-Review

**Spec coverage (Ch.10 M3 + ADRs):** the 8 format templates → A1/A2 (the 6 new as data, ADR 0007a §7b/§11; explainer worked-number pinned to count-up per §4/§11); audio performance layer → B (**per-beat prosody driving Kokoro** Task 4c, music taxonomy+anti-repeat ADR 0005 D6/0009, SFX, per-platform LUFS, 04 mix — D6 now fully covered); content-scaling item-sizing deferred to 00b with citation (ADR 0008 D2, Task 4 note); caption design → **landed in M1** (Task 8/9 there), not re-done here (noted); `05c` creative-QC backed by `05x` vision → C (ADR 0008 D1 + ADR 0005 D2 + ADR 0014 D1 original-insight); persona + brand kit + business profile → D (ADR 0005 D9, two-niche proof ADR 0010 D5); **render finishing** (end-card/loop ADR 0006 D5/D8, thumbnail, per-clip color match + cut-rate ADR 0005 D4 — previously unowned) → E (Task 12). `05b` safety gate + `06` distribution remain **M5** (noted, not in scope).

**Placeholder scan:** no "TBD"/"add error handling". The `NotImplementedError` bodies (`_frame_count`/`_extract_frames` in 05x; live VLM/ffmpeg) are documented integration seams with their CI substitute named (the pure `sample_frames`/`weighted_overall`/`select_track` are fully implemented + tested). Format authoring uses an explicit per-format bind/region contract table, not "similar to".

**Type consistency vs M0/M1/M2:** uses `@stage(StageManifest(...))`, `StageContext`, `StageResult`, `SchemaRegistry().validate`, `ctx.read_input/write_output/backend/quarantine`, the M2 `validate_binds`/`_resolve_bind` (extended for list indices, signature preserved), `resolve()`'s `render_manifest` (05x reads its `markers`). `QwenVLBackend` implements the full M0 `ModelBackend` surface incl. `restore` (the method added in the M0 re-review) — so `isinstance(_, ModelBackend)` holds. New cpu stages carrying a `capability` (`05c` → llm) mirror it in `manifest.json` per the M0 drift-catcher note. `creative_qc` / `vision` instances carry `schema_version` for the harness.

**Scope:** four parts, one acceptance gate, produces working testable software (8 validated formats + the audio mix + the enforced quality gate + a second niche running the DAG). Parts A–D are separable — if execution wants smaller PRs, cleave at the part boundaries.
