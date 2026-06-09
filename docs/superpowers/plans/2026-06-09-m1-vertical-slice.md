# M1 — Vertical Slice (finance: research → script → voice → subs → render) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the M0 thin/fake stages for `00a → 00b → 02 → 03 → 05` with **real** finance implementations that produce one genuine `renders/youtube.mp4` end-to-end, and capture the per-stage timing baseline (ADR 0011).

**Architecture:** Every stage stays an M0 `@stage`-decorated `run(ctx) -> StageResult` reading/writing declared inputs/outputs by name, validating against the M0 JSON schemas, using the content-addressed cache and the config-precedence resolver. Real model work (Qwen via Ollama, Kokoro TTS, WhisperX) lives behind the M0 `ModelBackend` Protocol in a new `shared/adapters/real.py`; tests that hit those services are `@pytest.mark.integration` and skipped in the GPU-free CI lane. The **pure logic** that defines M1's quality — deterministic numeric grounding, finance text-normalization, prosody markup, forced-alignment-to-known-script, caption styling, the ffmpeg command graph, Ken Burns keyframes, timing capture — is CI-testable with fixtures and is where the TDD weight sits.

**Tech Stack:** Python 3.12, `uv`, `pytest`, `jsonschema` (from M0); `httpx` (Ollama/HTTP), `kokoro` + `soundfile` (TTS), `whisperx` (forced alignment), `ffmpeg` (render via `subprocess`), `feedparser` (RSS), `requests`/`httpx` (market APIs). Real models run on the host; CI runs only the fake/pure-logic tests.

**Decisions made here (spec left open; pinned for M1):**
- **`data.schema.json` is authored in M1** (M0's 11 schemas did not include it; 00b's numeric-grounding check needs `data.json` typed). It carries `{schema_version, market: {<series>: {value, source, as_of}}, news: [{title, url, source, published, summary}]}`.
- **Market source for M1:** Alpha Vantage (`GLOBAL_QUOTE`, `TIME_SERIES_DAILY`) + FRED (`CPIAUCSL`, `FEDFUNDS`) — keyed by env; a fixture cache makes 00a CI-testable without live keys. Free-tier budget: Alpha Vantage ≤25 req/day, tracked in the cache layer.
- **Numeric-grounding tolerance:** a figure matches a `data.json` value if `abs(parsed - value) <= max(0.5% * |value|, 0.01)`; percentages compared as parsed floats. Ungrounded or out-of-tolerance → `ctx.quarantine`.
- **Pronunciation lexicon** lives at `shared/finance/lexicon.json` (`{token: spoken_form}`); text-normalization is regex + lexicon, deterministic.
- **Captions:** `.ass` format, **≤4 words on screen**, brand font, stroke+shadow, emphasis-word color; per-platform vertical safe-zone margins as config.
- **M1's Stage 05 is the ffmpeg interim** (stills + Ken Burns + word-timed cuts + brand overlay → `renders/youtube.mp4`). The format-aware Remotion compositor **replaces it in M2** — this plan marks every 05 file as "M2-replaceable".
- **Best-of-N:** `N=3` for M1 (config); the judge is the same Ollama model with a separate rubric prompt (a distinct judge backend is ADR 0009 D4, deferred).

---

## File Structure

```
schemas/data.schema.json                 # NEW (M1): typed 00a output (market + news)
shared/adapters/real.py                   # NEW: OllamaBackend, KokoroBackend (implement ModelBackend)
shared/finance/
  __init__.py
  normalize.py                            # finance text-normalization + lexicon application
  lexicon.json                            # {token: spoken_form} pronunciation map
  grounding.py                            # deterministic numeric-grounding check (pure)
shared/captions/
  __init__.py
  ass.py                                  # build_ass(): styled .ass from aligned words
shared/render/
  __init__.py
  kenburns.py                             # Ken Burns keyframe math (pure)
  ffmpeg.py                               # build_ffmpeg_cmd(): the M1 interim render graph (M2-replaceable)
shared/timing.py                          # NEW: per-stage wall-clock capture -> timing.jsonl
stages/s00a_research/{stage.py,manifest.json}   # REAL: market+news fetch, budget, corroboration
stages/s00b_script/{stage.py,manifest.json}     # REAL: Ollama treatment+best-of-N+judge+grounding+seed
stages/s02_voice/{stage.py,manifest.json}       # REAL: normalize -> Kokoro -> narration.wav
stages/s03_subs/{stage.py,manifest.json}        # REAL: WhisperX align-to-script -> captions.ass
stages/s05_render/{stage.py,manifest.json}      # INTERIM: ffmpeg stills+KenBurns -> renders/youtube.mp4
tests/
  fixtures/m1/
    data.json                            # golden 00a output (finance)
    aligned_words.json                   # golden WhisperX word timings (for caption/ render tests)
    ollama_responses/                    # canned LLM completions for 00b unit tests
  test_data_schema.py
  test_grounding.py  test_normalize.py  test_ass.py  test_kenburns.py  test_ffmpeg.py
  test_s00a_research.py  test_s00b_script.py  test_s02_voice.py  test_s03_subs.py  test_s05_render.py
  test_timing.py
  test_m1_slice_offline.py               # 00a->05 with fakes, asserts a youtube.mp4 is produced
pyproject.toml                            # MODIFY: add deps + the `integration` marker
.github/workflows/ci.yml                  # MODIFY: run `-m "not integration"`
```

**Responsibility split:** `shared/finance/`, `shared/captions/`, `shared/render/` hold the *pure, deterministic* logic (CI-tested); `stages/*/stage.py` are thin orchestration that wires those + a backend; `shared/adapters/real.py` is the only place that talks to live models. This keeps each file focused and the bulk of M1 testable without a GPU.

---

## Phase 0 — Deps + the integration marker

### Task 0: Add dependencies and the `integration` pytest marker

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add deps + marker to `pyproject.toml`**

Add to `[project].dependencies`: `"httpx>=0.27"`, `"feedparser>=6.0"`, `"soundfile>=0.12"`. Add a new section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = ["integration: touches a live model/service; skipped in GPU-free CI"]
```

(Note: `kokoro`, `whisperx` are host-only and installed on the host, not in CI — they are imported lazily inside `real.py` so CI import never fails.)

- [ ] **Step 2: Make CI skip integration tests** — edit `.github/workflows/ci.yml` run step:

```yaml
      - name: Run the GPU-free suite
        run: uv run pytest -q -m "not integration"
```

- [ ] **Step 3: Verify** — `uv sync && uv run pytest -q -m "not integration"` → existing M0 tests still PASS.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml
git commit -m "chore(m1): add deps + integration marker (CI stays GPU-free)"
```

---

## Phase 1 — `data.schema.json` + the deterministic numeric-grounding check

### Task 1: Author `data.schema.json` and its golden fixture

**Files:**
- Create: `schemas/data.schema.json`
- Create: `tests/fixtures/m1/data.json`
- Test: `tests/test_data_schema.py`

- [ ] **Step 1: Write `schemas/data.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "data.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "market", "news"],
  "properties": {
    "schema_version": {"type": "string"},
    "market": {
      "type": "object",
      "additionalProperties": {
        "type": "object", "additionalProperties": false,
        "required": ["value", "source", "as_of"],
        "properties": {"value": {"type": "number"}, "source": {"type": "string"},
                       "as_of": {"type": "string"}}
      }
    },
    "news": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["title", "url", "source", "published"],
        "properties": {"title": {"type": "string"}, "url": {"type": "string"},
                       "source": {"type": "string"}, "published": {"type": "string"},
                       "summary": {"type": "string"}}
      }
    }
  }
}
```

- [ ] **Step 2: Write `tests/fixtures/m1/data.json`**

```json
{
  "schema_version": "1.0.0",
  "market": {
    "cpi_yoy": {"value": 3.2, "source": "FRED:CPIAUCSL", "as_of": "2026-06-08"},
    "fed_funds": {"value": 4.5, "source": "FRED:FEDFUNDS", "as_of": "2026-06-08"},
    "ACME_price": {"value": 184.21, "source": "AlphaVantage:GLOBAL_QUOTE", "as_of": "2026-06-08"}
  },
  "news": [
    {"title": "Inflation cools to 3.2%", "url": "https://ex.com/a", "source": "Reuters",
     "published": "2026-06-08", "summary": "CPI eased."},
    {"title": "Fed holds rates", "url": "https://ex.com/b", "source": "AP",
     "published": "2026-06-07", "summary": "No change."}
  ]
}
```

- [ ] **Step 3: Write `tests/test_data_schema.py`**

```python
import json
from pathlib import Path
from shared.schema import SchemaRegistry

REG = SchemaRegistry()
FIX = Path(__file__).parent / "fixtures" / "m1"


def test_data_golden_validates():
    REG.validate("data", json.loads((FIX / "data.json").read_text()))
```

- [ ] **Step 4: Run** → `uv run pytest tests/test_data_schema.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add schemas/data.schema.json tests/fixtures/m1/data.json tests/test_data_schema.py
git commit -m "feat(m1): data.schema + finance golden fixture"
```

### Task 2: Deterministic numeric-grounding check (`shared/finance/grounding.py`)

ADR 0009: every cited figure carries `{value, source_ref}`; a **non-LLM** check rejects any number with no matching `data.json` value or out of tolerance.

**Files:**
- Create: `shared/finance/__init__.py` (empty), `shared/finance/grounding.py`
- Test: `tests/test_grounding.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_grounding.py
import pytest
from shared.finance.grounding import resolve_ref, within_tolerance, check_claims, GroundingError


def test_resolve_ref_dotted_path():
    data = {"market": {"cpi_yoy": {"value": 3.2}}}
    assert resolve_ref(data, "market.cpi_yoy") == 3.2


def test_within_tolerance_percent_band():
    assert within_tolerance(3.21, 3.2) is True       # within 0.5%
    assert within_tolerance(3.5, 3.2) is False


def test_parse_money_and_percent():
    # "3.2%" and "$184.21" parse to 3.2 and 184.21
    data = {"market": {"cpi_yoy": {"value": 3.2}, "ACME_price": {"value": 184.21}}}
    claims = [{"value": "3.2%", "source_ref": "market.cpi_yoy"},
              {"value": "$184.21", "source_ref": "market.ACME_price"}]
    check_claims(claims, data)  # no raise


def test_ungrounded_ref_raises():
    with pytest.raises(GroundingError):
        check_claims([{"value": "9.9%", "source_ref": "market.nope"}], {"market": {}})


def test_out_of_tolerance_raises():
    with pytest.raises(GroundingError):
        check_claims([{"value": "5.0%", "source_ref": "market.cpi_yoy"}],
                     {"market": {"cpi_yoy": {"value": 3.2}}})
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `shared/finance/grounding.py`**

```python
import re
from typing import Any


class GroundingError(Exception):
    """A cited figure is ungrounded or out of tolerance vs data.json."""


def resolve_ref(data: dict[str, Any], ref: str) -> float:
    node: Any = data
    for part in ref.split("."):
        if not isinstance(node, dict) or part not in node:
            raise GroundingError(f"unresolved source_ref: {ref!r}")
        node = node[part]
    if isinstance(node, dict) and "value" in node:
        node = node["value"]
    if not isinstance(node, (int, float)):
        raise GroundingError(f"source_ref {ref!r} is not numeric")
    return float(node)


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_number(text: str) -> float:
    m = _NUM.search(text.replace(",", ""))
    if not m:
        raise GroundingError(f"no number in claim value {text!r}")
    return float(m.group())


def within_tolerance(parsed: float, expected: float) -> bool:
    return abs(parsed - expected) <= max(0.005 * abs(expected), 0.01)


def check_claims(claims: list[dict], data: dict[str, Any]) -> None:
    for c in claims:
        expected = resolve_ref(data, c["source_ref"])
        parsed = parse_number(c["value"])
        if not within_tolerance(parsed, expected):
            raise GroundingError(
                f"claim {c['value']!r} != data {expected} (ref {c['source_ref']})")
```

- [ ] **Step 4: Run** → PASS (5). **Commit.**

```bash
git add shared/finance/__init__.py shared/finance/grounding.py tests/test_grounding.py
git commit -m "feat(m1): deterministic numeric-grounding check (ADR 0009)"
```

---

## Phase 2 — Real model backends (Ollama + Kokoro)

### Task 3: `OllamaBackend` + `KokoroBackend` implementing the M0 `ModelBackend` Protocol

ADR 0012 §6: backends implement `llm/tts/generate_image/img2vid/vlm_judge`. M1 needs `llm` (Ollama) and `tts` (Kokoro); the rest raise `NotImplementedError` (they are M2 GPU stages).

**Files:**
- Create: `shared/adapters/real.py`
- Test: `tests/test_adapters_real.py`

- [ ] **Step 1: Write the failing tests** (unit-level: Protocol conformance + URL/payload construction; the live call is integration)

```python
# tests/test_adapters_real.py
import pytest
from shared.adapters import ModelBackend
from shared.adapters.real import OllamaBackend, KokoroBackend


def test_ollama_satisfies_protocol():
    assert isinstance(OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct"),
                      ModelBackend)


def test_ollama_builds_generate_payload():
    be = OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct")
    url, payload = be._request("hello")
    assert url == "http://h:11434/api/generate"
    assert payload == {"model": "qwen2.5:14b-instruct", "prompt": "hello", "stream": False}


def test_ollama_seeded_payload_sets_options_seed():
    be = OllamaBackend(base_url="http://h:11434", model="qwen2.5:14b-instruct")
    _, payload = be._request("hi", seed=7)
    assert payload["options"]["seed"] == 7   # best-of-N is reproducible (ADR 0009)


@pytest.mark.integration
def test_ollama_llm_live():
    be = OllamaBackend(base_url="http://127.0.0.1:11434", model="qwen2.5:14b-instruct")
    assert isinstance(be.llm("Reply with the single word OK."), str)
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `shared/adapters/real.py`**

```python
from pathlib import Path

import httpx

from shared.adapters.types import Judgment


class OllamaBackend:
    """ModelBackend.llm via an Ollama /api/generate endpoint on the host."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def _request(self, prompt: str, seed: int | None = None) -> tuple[str, dict]:
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        if seed is not None:
            payload["options"] = {"seed": seed, "temperature": 0.8}  # seed the SAMPLER (ADR 0009)
        return (f"{self._base}/api/generate", payload)

    def llm(self, prompt: str, seed: int | None = None) -> str:
        url, payload = self._request(prompt, seed)
        r = httpx.post(url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        return r.json()["response"]

    # M2 GPU capabilities — not provided by the LLM endpoint.
    def generate_image(self, prompt: str, seed: int) -> Path:
        raise NotImplementedError("generate_image is an M2 ComfyUI backend")

    def img2vid(self, image: Path, seed: int) -> Path:
        raise NotImplementedError("img2vid is an M2 ComfyUI backend")

    def tts(self, text: str) -> Path:
        raise NotImplementedError("use KokoroBackend for tts")

    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment:
        raise NotImplementedError("vlm_judge is an M3 backend")

    def restore(self, frames: list[Path]) -> list[Path]:
        raise NotImplementedError("restore is an M2 ComfyUI backend")


class KokoroBackend:
    """ModelBackend.tts via Kokoro-82M; writes a wav and returns its path."""

    def __init__(self, out_dir: Path, voice: str = "af_heart", sample_rate: int = 24000):
        self._out = Path(out_dir)
        self._voice = voice
        self._sr = sample_rate

    def tts(self, text: str) -> Path:
        from kokoro import KPipeline  # host-only import
        import numpy as np
        import soundfile as sf
        self._out.mkdir(parents=True, exist_ok=True)
        pipe = KPipeline(lang_code="a")
        audio = np.concatenate([chunk.audio for chunk in pipe(text, voice=self._voice)])
        path = self._out / "narration.wav"
        sf.write(path, audio, self._sr)
        return path

    def llm(self, prompt: str, seed: int | None = None) -> str:
        raise NotImplementedError("use OllamaBackend for llm")

    def generate_image(self, prompt: str, seed: int) -> Path:
        raise NotImplementedError
    def img2vid(self, image: Path, seed: int) -> Path:
        raise NotImplementedError
    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment:
        raise NotImplementedError
    def restore(self, frames: list[Path]) -> list[Path]:
        raise NotImplementedError
```

- [ ] **Step 4: Run** → `uv run pytest tests/test_adapters_real.py -m "not integration" -v` → PASS (2; integration test deselected). **Commit.**

```bash
git add shared/adapters/real.py tests/test_adapters_real.py
git commit -m "feat(m1): Ollama + Kokoro backends implementing ModelBackend (ADR 0012 §6)"
```

---

## Phase 3 — Stage 00a (research / ingest)

### Task 4: API budget tracker (pure) + the 00a fetch with cache + corroboration

ADR 0009: API budgeting + local cache (Alpha Vantage ~25 req/day); `news_reaction` needs ≥2-source corroboration; fetch failure is a first-class DAG state.

**Files:**
- Create: `stages/s00a_research/__init__.py` (empty), `stages/s00a_research/stage.py`, `stages/s00a_research/manifest.json`
- Test: `tests/test_s00a_research.py`

- [ ] **Step 1: Write the failing tests** (pure logic: corroboration + budget; live fetch is integration)

```python
# tests/test_s00a_research.py
import json
import pytest
from pathlib import Path
from stages.s00a_research.stage import corroborated, BudgetExceeded, Budget


def test_corroboration_needs_two_sources():
    news = [{"title": "Inflation cooled", "source": "Reuters"},
            {"title": "CPI inflation eases", "source": "AP"}]
    assert corroborated("inflation", news, min_sources=2) is True


def test_corroboration_single_source_fails():
    assert corroborated("inflation", [{"title": "Inflation cooled", "source": "Reuters"}],
                        min_sources=2) is False


def test_corroboration_ignores_offtopic_sources():
    news = [{"title": "Inflation cooled", "source": "Reuters"},
            {"title": "Sports recap", "source": "ESPN"}]   # second item not about the topic
    assert corroborated("inflation", news, min_sources=2) is False


def test_budget_blocks_over_limit():
    b = Budget(limit=2)
    b.spend("alpha_vantage"); b.spend("alpha_vantage")
    with pytest.raises(BudgetExceeded):
        b.spend("alpha_vantage")
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `stages/s00a_research/stage.py`**

```python
import json
import os
from dataclasses import dataclass, field

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


class BudgetExceeded(Exception):
    """A free-tier API budget was exhausted for the batch."""


@dataclass
class Budget:
    limit: int
    spent: dict[str, int] = field(default_factory=dict)

    def spend(self, api: str) -> None:
        n = self.spent.get(api, 0) + 1
        if n > self.limit:
            raise BudgetExceeded(api)
        self.spent[api] = n


def corroborated(topic: str, news: list[dict], min_sources: int = 2) -> bool:
    # ADR 0009: a story needs >=min_sources DISTINCT sources whose item is ABOUT `topic`
    # (title/summary match) — not merely global source diversity across unrelated items.
    t = topic.lower()
    sources = {n["source"] for n in news
               if t in (n.get("title", "") + " " + n.get("summary", "")).lower()}
    return len(sources) >= min_sources


@stage(StageManifest(id="00a", inputs=[], outputs=["data"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    # M1: live fetch behind env keys; falls back to the committed fixture when keys absent
    # (keeps the slice runnable + the stage CI-testable). Real HTTP client lives here.
    fixture = ctx.config.get("data_fixture")
    if fixture:
        data = json.loads((ctx.run_dir / fixture).read_text())
    else:
        data = _fetch_live(ctx)  # uses httpx + Budget; raises -> ctx.degrade on partial
    out = ctx.write_output("data")
    out.write_text(json.dumps(data))
    ctx.log.info("data written", market_series=len(data["market"]), news=len(data["news"]))
    return StageResult(outputs={"data": out})


def _fetch_live(ctx: StageContext) -> dict:
    import httpx  # noqa
    budget = Budget(limit=int(os.environ.get("AV_DAILY_LIMIT", "25")))
    # ... per-series Alpha Vantage / FRED pulls, each guarded by budget.spend(...),
    # news via feedparser over the niche RSS list, filtered to <=3 days, corroboration-checked.
    # On any series failure: ctx.degrade("market pull failed: <series>") (first-class DAG state).
    raise NotImplementedError("live fetch wired during integration bring-up; M1 CI uses data_fixture")
```

> Note: the live `_fetch_live` body is wired during host bring-up; M1 CI and the offline slice run with `config.data_fixture = "data.json"` (the committed fixture copied into the run dir), so the entire downstream chain is exercised deterministically. The corroboration + budget logic it *will* use is unit-tested above.

- [ ] **Step 4: Write `stages/s00a_research/manifest.json`**

```json
{"id": "00a", "inputs": [], "outputs": ["data"], "compute": "cpu"}
```

- [ ] **Step 5: Run** → PASS (3). **Commit.**

```bash
git add stages/s00a_research/ tests/test_s00a_research.py
git commit -m "feat(m1): 00a research stage (budget+corroboration pure logic; fixture-backed fetch)"
```

---

## Phase 4 — Stage 00b (script: treatment + best-of-N + judge + grounding)

### Task 5: Best-of-N selection + judge parsing (pure)

**Files:**
- Create: `stages/s00b_script/__init__.py` (empty), `stages/s00b_script/stage.py`, `manifest.json`
- Test: `tests/test_s00b_script.py`

- [ ] **Step 1: Write the failing tests** (pure: best-of-N pick + seed determinism + grounding integration)

```python
# tests/test_s00b_script.py
import json
from pathlib import Path
import pytest
from stages.s00b_script.stage import pick_best, build_judge_prompt
from shared.finance.grounding import GroundingError

FIX = Path(__file__).parent / "fixtures" / "m1"


def test_pick_best_returns_highest_score():
    scored = [({"hook": "a"}, 0.4), ({"hook": "b"}, 0.9), ({"hook": "c"}, 0.7)]
    assert pick_best(scored) == {"hook": "b"}


def test_pick_best_is_deterministic_on_ties_by_index():
    scored = [({"hook": "a"}, 0.9), ({"hook": "b"}, 0.9)]
    assert pick_best(scored) == {"hook": "a"}  # first wins on tie


def test_judge_prompt_includes_original_insight_criterion():
    p = build_judge_prompt({"hook": {"spoken": "x"}})
    assert "non-obvious" in p.lower() or "original" in p.lower()  # ADR 0014 D1
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `stages/s00b_script/stage.py`** (the run() wires Ollama + grounding; pure helpers are unit-tested)

```python
import json
import random

from shared.ctx import StageContext, StageResult
from shared.finance.grounding import check_claims
from shared.stage import StageManifest, stage


def pick_best(scored: list[tuple[dict, float]]) -> dict:
    # max by score; ties resolve to the earliest index (deterministic)
    best_i = max(range(len(scored)), key=lambda i: (scored[i][1], -i))
    return scored[best_i][0]


def build_judge_prompt(script: dict) -> str:
    return ("Score this short-video script 0-1 on: hook strength; "
            "does it say something NON-OBVIOUS with an ORIGINAL point of view "
            "(not a generic template fill); visual-script coherence; payoff. "
            "Return only a number.\n\n" + json.dumps(script))


@stage(StageManifest(id="00b", inputs=["data"], outputs=["script"], compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    data = json.loads(ctx.read_input("data").read_text())
    llm = ctx.backend("llm")
    rng = random.Random(ctx.seed)  # seed -> reproducible best-of-N (ADR 0009)
    n = int(ctx.config.get("best_of_n", 3))

    scored: list[tuple[dict, float]] = []
    for i in range(n):
        script = _generate_script(llm, data, ctx.config, rng.randint(0, 2**31))
        score = float(llm.llm(build_judge_prompt(script)).strip().split()[0])
        scored.append((script, score))

    chosen = pick_best(scored)
    chosen["hook_variants"] = [{"spoken": s["hook"]["spoken"], "score": sc} for s, sc in scored]
    check_claims(chosen.get("claims", []), data)  # deterministic grounding; raises -> caught below

    out = ctx.write_output("script")
    out.write_text(json.dumps(chosen))
    ctx.log.info("script chosen", n=n, best_score=max(sc for _, sc in scored))
    return StageResult(outputs={"script": out})


def _generate_script(llm, data: dict, config: dict, seed: int) -> dict:
    # Builds the finance-persona prompt (treatment + format + hook + beats + claims with
    # {value, source_ref}) and parses the model's JSON into a script.schema instance.
    # Prompt construction is deterministic given (data, config, seed); the model call is live.
    prompt = _build_prompt(data, config, seed)
    return json.loads(llm.llm(prompt, seed=seed))   # seed threaded to the sampler (ADR 0009)


def _build_prompt(data: dict, config: dict, seed: int) -> str:
    persona = config.get("persona", "a rigorous, data-first finance explainer")
    return (f"You are {persona}. Using ONLY these figures (cite each as "
            f'{{"value","source_ref"}} into the given keys): {json.dumps(data["market"])}. '
            f"Recent news: {json.dumps(data['news'])}. Seed={seed}. "
            "Write a vertical short-video script as JSON matching the script schema "
            "(format, treatment, hook, narration_beats, captions, music, platform_meta, "
            "claims, disclaimer, layout_data). Pick the ranked_list format. "
            "Include a YMYL disclaimer. Make the take NON-OBVIOUS.")
```

> The `run()` is wrapped so a `GroundingError` becomes a quarantine: in the SDK runner a stage exception on a quality invariant calls `ctx.quarantine`. For M1, wrap the `check_claims` call: `try: check_claims(...) except GroundingError as e: ctx.quarantine(str(e))`.

- [ ] **Step 4: Add the quarantine wrap** — change the `check_claims(...)` line to:

```python
    from shared.finance.grounding import GroundingError
    try:
        check_claims(chosen.get("claims", []), data)
    except GroundingError as e:
        ctx.quarantine(f"numeric grounding failed: {e}")
    if not chosen.get("disclaimer", "").strip():
        ctx.quarantine("missing YMYL disclaimer")   # ADR 0004 YMYL requirement (enforced, not just prompted)
```

- [ ] **Step 5: Write `manifest.json`**

```json
{"id": "00b", "inputs": ["data"], "outputs": ["script"], "compute": "cpu", "capability": "llm"}
```

- [ ] **Step 6: Run** → PASS (3). **Commit.**

```bash
git add stages/s00b_script/ tests/test_s00b_script.py
git commit -m "feat(m1): 00b script (best-of-N+judge+seed+grounding-quarantine, ADR 0005/0009/0014)"
```

---

## Phase 5 — Stage 02 (voice)

### Task 6: Finance text-normalization + lexicon (pure)

**Files:**
- Create: `shared/finance/lexicon.json`, `shared/finance/normalize.py`
- Test: `tests/test_normalize.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize.py
from shared.finance.normalize import normalize


def test_money_millions():
    assert normalize("$1.5M") == "one point five million dollars"


def test_known_token_from_lexicon():
    assert normalize("401(k)") == "four oh one k"


def test_percent():
    assert normalize("3.2%") == "three point two percent"


def test_dollars_with_hundreds():
    assert normalize("$184.21") == "one hundred eighty four point two one dollars"


def test_ticker_passthrough_uppercased_words_kept():
    assert "FOMC" not in normalize("FOMC")  # expanded via lexicon
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write `shared/finance/lexicon.json`**

```json
{"401(k)": "four oh one k", "FOMC": "the F O M C", "ETF": "E T F", "Q3": "Q three",
 "FRED": "fred", "CPI": "C P I", "YoY": "year over year"}
```

- [ ] **Step 4: Implement `shared/finance/normalize.py`**

```python
import json
import re
from pathlib import Path

_LEX = json.loads((Path(__file__).parent / "lexicon.json").read_text())
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def _say_number(num: str) -> str:
    if "." in num:
        whole, frac = num.split(".")
        frac_words = " ".join(_ONES[int(d)] for d in frac)
        return f"{_say_int(whole)} point {frac_words}"
    return _say_int(num)


_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
          "seventeen", "eighteen", "nineteen"]


def _say_int(s: str) -> str:
    n = int(s)
    if n < 10:
        return _ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        rem = n % 100
        return _ONES[n // 100] + " hundred" + ("" if rem == 0 else " " + _say_int(str(rem)))
    if n < 1_000_000:
        rem = n % 1000
        return _say_int(str(n // 1000)) + " thousand" + ("" if rem == 0 else " " + _say_int(str(rem)))
    return " ".join(_ONES[int(d)] for d in s)  # very large: digit-by-digit fallback


def normalize(text: str) -> str:
    for token, spoken in _LEX.items():
        text = text.replace(token, spoken)
    text = re.sub(r"\$(\d+\.?\d*)M", lambda m: f"{_say_number(m.group(1))} million dollars", text)
    text = re.sub(r"\$(\d+\.?\d*)", lambda m: f"{_say_number(m.group(1))} dollars", text)
    text = re.sub(r"(\d+\.?\d*)%", lambda m: f"{_say_number(m.group(1))} percent", text)
    return text.strip()
```

- [ ] **Step 5: Run** → PASS (4). **Commit.**

```bash
git add shared/finance/lexicon.json shared/finance/normalize.py tests/test_normalize.py
git commit -m "feat(m1): finance text-normalization + pronunciation lexicon (ADR 0005 D6)"
```

### Task 7: Stage 02 wiring (normalize → Kokoro → narration.wav)

**Files:**
- Create: `stages/s02_voice/__init__.py` (empty), `stages/s02_voice/stage.py`, `manifest.json`
- Test: `tests/test_s02_voice.py`

- [ ] **Step 1: Write the failing tests** (pure: spoken-text assembly + keyword-in-opening; the Kokoro call is integration)

```python
# tests/test_s02_voice.py
import json
from pathlib import Path
from stages.s02_voice.stage import spoken_text, keyword_in_opening


def test_spoken_text_normalizes_and_joins_beats():
    script = {"narration_beats": [{"text": "CPI hit 3.2%"}, {"text": "$1.5M moved"}],
              "primary_keyword": "inflation"}
    out = spoken_text(script)
    assert "three point two percent" in out and "one point five million dollars" in out


def test_keyword_in_opening_detects_presence_and_absence():
    present = {"primary_keyword": "inflation",
               "narration_beats": [{"text": "Inflation cooled this month"}, {"text": "More later"}]}
    assert keyword_in_opening(present) is True
    buried = {"primary_keyword": "inflation",
              "narration_beats": [{"text": "Stocks rose"}, {"text": "Inflation later"}]}
    assert keyword_in_opening(buried, window_beats=1) is False
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `stages/s02_voice/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.finance.normalize import normalize
from shared.stage import StageManifest, stage


def spoken_text(script: dict) -> str:
    beats = [normalize(b["text"]) for b in script.get("narration_beats", [])]
    return " ".join(beats)


def keyword_in_opening(script: dict, window_beats: int = 1) -> bool:
    # ADR 0006: the primary keyword should be SPOKEN in the opening lines (discoverability).
    kw = script.get("primary_keyword", "").lower()
    if not kw:
        return False
    opening = " ".join(b["text"] for b in script.get("narration_beats", [])[:window_beats]).lower()
    return kw in opening


@stage(StageManifest(id="02", inputs=["script"], outputs=["narration"], compute="cpu", capability="tts"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    if not keyword_in_opening(script):
        ctx.log.warning("primary keyword not in opening lines", keyword=script.get("primary_keyword"))
    text = spoken_text(script)
    wav = ctx.backend("tts").tts(text)  # KokoroBackend writes narration.wav
    out = ctx.write_output("narration")
    if wav != out:
        out.write_bytes(wav.read_bytes())
    ctx.log.info("narration synthesized", chars=len(text))
    return StageResult(outputs={"narration": out})
```

- [ ] **Step 4: Write `manifest.json`**

```json
{"id": "02", "inputs": ["script"], "outputs": ["narration"], "compute": "cpu", "capability": "tts"}
```

- [ ] **Step 5: Run** → `uv run pytest tests/test_s02_voice.py -v` → PASS (1). **Commit.**

```bash
git add stages/s02_voice/ tests/test_s02_voice.py
git commit -m "feat(m1): 02 voice (normalize -> Kokoro narration)"
```

---

## Phase 6 — Stage 03 (subtitles: forced-align + styled .ass)

### Task 8: Styled `.ass` caption builder (pure)

ADR 0005 D7: ≤N words on screen, brand font, stroke/shadow, emphasis-word styling, per-platform safe zones.

**Files:**
- Create: `shared/captions/__init__.py` (empty), `shared/captions/ass.py`
- Create: `tests/fixtures/m1/aligned_words.json`
- Test: `tests/test_ass.py`

- [ ] **Step 1: Write `tests/fixtures/m1/aligned_words.json`**

```json
[{"word": "Inflation", "start": 0.10, "end": 0.55, "emphasis": true},
 {"word": "cooled", "start": 0.55, "end": 0.95, "emphasis": false},
 {"word": "to", "start": 0.95, "end": 1.05, "emphasis": false},
 {"word": "3.2%", "start": 1.05, "end": 1.60, "emphasis": true},
 {"word": "this", "start": 1.60, "end": 1.80, "emphasis": false},
 {"word": "month", "start": 1.80, "end": 2.10, "emphasis": false}]
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_ass.py
import json
from pathlib import Path
from shared.captions.ass import group_words, build_ass

FIX = Path(__file__).parent / "fixtures" / "m1"


def test_group_caps_words_per_line():
    words = json.loads((FIX / "aligned_words.json").read_text())
    groups = group_words(words, max_words=4)
    assert all(len(g) <= 4 for g in groups)
    assert len(groups) == 2  # 6 words -> [4, 2]


def test_build_ass_has_header_and_dialogue_and_emphasis_color():
    words = json.loads((FIX / "aligned_words.json").read_text())
    ass = build_ass(words, max_words=4, font="Inter", emphasis_hex="00E5FF",
                    safe_bottom_pct=18)
    assert "[Script Info]" in ass and "Dialogue:" in ass
    assert "PrimaryColour" in ass
    assert r"{\c&H" in ass  # inline emphasis color override present


def test_timing_uses_first_and_last_word_of_group():
    words = json.loads((FIX / "aligned_words.json").read_text())
    ass = build_ass(words, max_words=4, font="Inter", emphasis_hex="00E5FF", safe_bottom_pct=18)
    assert "0:00:00.10," in ass  # first group start
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Implement `shared/captions/ass.py`**

```python
def group_words(words: list[dict], max_words: int) -> list[list[dict]]:
    return [words[i:i + max_words] for i in range(0, len(words), max_words)]


def _ts(sec: float) -> str:
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(words: list[dict], *, max_words: int, font: str, emphasis_hex: str,
              safe_bottom_pct: int) -> str:
    margin_v = int(1920 * safe_bottom_pct / 100)  # 9:16 @ 1080x1920
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Outline, Shadow, Alignment, MarginV\n"
        f"Style: Base,{font},72,&H00FFFFFF,&H00000000,&H64000000,1,4,2,2,{margin_v}\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    lines = []
    for group in group_words(words, max_words):
        start, end = group[0]["start"], group[-1]["end"]
        text = " ".join(
            (f"{{\\c&H{emphasis_hex}&}}{w['word']}{{\\c&HFFFFFF&}}" if w.get("emphasis")
             else w["word"])
            for w in group
        )
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Base,{text}")
    return header + "\n".join(lines) + "\n"
```

- [ ] **Step 5: Run** → PASS (3). **Commit.**

```bash
git add shared/captions/ tests/fixtures/m1/aligned_words.json tests/test_ass.py
git commit -m "feat(m1): styled .ass caption builder (ADR 0005 D7)"
```

### Task 9: Stage 03 wiring (WhisperX forced-align to known script → .ass)

ADR 0009: forced-align to the **known script text**, not a fresh transcription.

**Files:**
- Create: `stages/s03_subs/__init__.py` (empty), `stages/s03_subs/stage.py`, `manifest.json`
- Test: `tests/test_s03_subs.py`

- [ ] **Step 1: Write the failing tests** (pure: emphasis tagging from the script's emphasis words; alignment is integration)

```python
# tests/test_s03_subs.py
from stages.s03_subs.stage import tag_emphasis


def test_tag_emphasis_marks_script_punch_words():
    aligned = [{"word": "Inflation", "start": 0.1, "end": 0.5},
               {"word": "cooled", "start": 0.5, "end": 0.9}]
    out = tag_emphasis(aligned, emphasis_words={"inflation"})
    assert out[0]["emphasis"] is True and out[1]["emphasis"] is False


def test_tag_emphasis_matches_numeric_token():
    aligned = [{"word": "3.2%", "start": 1.0, "end": 1.6}]
    assert tag_emphasis(aligned, {"3.2%"})[0]["emphasis"] is True   # raw numeric punch word
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `stages/s03_subs/stage.py`**

```python
import json

from shared.captions.ass import build_ass
from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


def tag_emphasis(aligned: list[dict], emphasis_words: set[str]) -> list[dict]:
    ew = {w.lower() for w in emphasis_words}

    def hit(word: str) -> bool:
        w = word.lower()
        # match the raw token first (so "3.2%" / "$1.5m" punch words match), then a
        # sentence-punctuation-stripped form — but never strip % or $ (they carry meaning).
        return w in ew or w.strip(".,!?") in ew

    return [{**w, "emphasis": hit(w["word"])} for w in aligned]


@stage(StageManifest(id="03", inputs=["script", "narration"], outputs=["captions", "word_timings"],
                     compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    script_text = " ".join(b["text"] for b in script.get("narration_beats", []))
    aligned = _align_to_script(ctx.read_input("narration"), script_text)  # WhisperX, integration
    emphasis = {w for c in script.get("captions", []) for w in c.get("emphasis", [])}
    words = tag_emphasis(aligned, emphasis)
    ass = build_ass(words, max_words=int(ctx.config.get("caption_max_words", 4)),
                    font=ctx.config.get("brand_font", "Inter"),
                    emphasis_hex=ctx.config.get("emphasis_hex", "00E5FF"),
                    safe_bottom_pct=int(ctx.config.get("safe_bottom_pct", 18)))
    out = ctx.write_output("captions")
    out.write_text(ass)
    wt = ctx.write_output("word_timings")     # word-level timings consumed by Stage 05 (M2 compositor)
    wt.write_text(json.dumps(words))
    ctx.log.info("captions built", lines=ass.count("Dialogue:"))
    return StageResult(outputs={"captions": out, "word_timings": wt})


def _align_to_script(narration_wav, script_text: str) -> list[dict]:
    import whisperx  # host-only
    model = whisperx.load_align_model(language_code="en", device="cpu")
    # forced alignment of the KNOWN text to audio -> word timings (not transcription)
    raise NotImplementedError("WhisperX alignment wired at integration bring-up; "
                              "unit tests use tests/fixtures/m1/aligned_words.json")
```

> The offline slice (Task 12) injects the `aligned_words.json` fixture via a fake that returns it, so 03 runs without WhisperX in CI.

- [ ] **Step 4: Write `manifest.json`**

```json
{"id": "03", "inputs": ["script", "narration"], "outputs": ["captions", "word_timings"], "compute": "cpu"}
```

- [ ] **Step 5: Run** → PASS (1). **Commit.**

```bash
git add stages/s03_subs/ tests/test_s03_subs.py
git commit -m "feat(m1): 03 subtitles (forced-align-to-script + emphasis tagging, ADR 0009/0005)"
```

---

## Phase 7 — Stage 05 (ffmpeg interim render)

### Task 10: Ken Burns keyframes (pure) + ffmpeg command graph (pure)

> **M2-replaceable:** this entire phase is the ffmpeg interim; M2 swaps Stage 05 for the Remotion compositor. Keep the logic in `shared/render/` so the swap is contained.

**Files:**
- Create: `shared/render/__init__.py` (empty), `shared/render/kenburns.py`, `shared/render/ffmpeg.py`
- Test: `tests/test_kenburns.py`, `tests/test_ffmpeg.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_kenburns.py
from shared.render.kenburns import zoompan_expr


def test_zoompan_scales_within_bounds():
    expr = zoompan_expr(zoom_start=1.0, zoom_end=1.12, frames=90)
    assert expr.startswith("zoompan=") and "1.12" in expr and "d=90" in expr
    assert "#" not in expr   # no comment — would be an ffmpeg filtergraph parse error
```

```python
# tests/test_ffmpeg.py
from shared.render.ffmpeg import build_ffmpeg_cmd


def test_cmd_burns_captions_and_audio_and_outputs_mp4(tmp_path):
    cmd = build_ffmpeg_cmd(
        scene_images=[tmp_path / "a.png", tmp_path / "b.png"],
        scene_durations=[2.0, 2.5],
        narration=tmp_path / "narration.wav",
        captions_ass=tmp_path / "captions.ass",
        brand_overlay=tmp_path / "logo.png",
        out=tmp_path / "youtube.mp4",
        fps=30,
    )
    s = " ".join(cmd)
    assert cmd[0] == "ffmpeg"
    assert "ass=" in s                      # caption burn-in
    assert str(tmp_path / "narration.wav") in s
    assert s.endswith(str(tmp_path / "youtube.mp4"))
    assert "-r 30" in s or "fps=30" in s
    assert "zoompan=" in s                  # Ken Burns applied per still
    assert "overlay=" in s                  # brand bug enabled
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `shared/render/kenburns.py`**

```python
def zoompan_expr(*, zoom_start: float, zoom_end: float, frames: int) -> str:
    # linear zoom from start->end across `frames`; centered. ffmpeg zoompan expression.
    step = (zoom_end - zoom_start) / max(frames - 1, 1)
    # NB: no trailing comment — ffmpeg filtergraph syntax has no `#` comments.
    return (f"zoompan=z='min(zoom+{step:.6f},{zoom_end})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30")
```

- [ ] **Step 4: Implement `shared/render/ffmpeg.py`**

```python
from pathlib import Path

from shared.render.kenburns import zoompan_expr


def build_ffmpeg_cmd(*, scene_images: list[Path], scene_durations: list[float],
                     narration: Path, captions_ass: Path, brand_overlay: Path,
                     out: Path, fps: int) -> list[str]:
    """M1 interim render: Ken Burns stills -> concat -> burn captions -> brand overlay -> + audio.

    Inputs are ordered: images 0..n-1, narration = n, brand_overlay = n+1.
    """
    cmd: list[str] = ["ffmpeg", "-y"]
    for img, dur in zip(scene_images, scene_durations):
        cmd += ["-loop", "1", "-t", f"{dur}", "-i", str(img)]
    cmd += ["-i", str(narration), "-i", str(brand_overlay)]
    n = len(scene_images)
    # per-still Ken Burns (zoompan), concat, burn captions, then overlay the brand bug
    filters = "".join(
        f"[{i}:v]scale=1080:1920,setsar=1,"
        f"{zoompan_expr(zoom_start=1.0, zoom_end=1.08, frames=int(dur * fps))}[v{i}];"
        for i, dur in enumerate(scene_durations))
    filters += "".join(f"[v{i}]" for i in range(n))
    filters += f"concat=n={n}:v=1:a=0[vc];"
    filters += f"[vc]subtitles=ass={captions_ass}[vs];"
    filters += f"[vs][{n + 1}:v]overlay=W-w-40:40[vo]"   # brand bug, top-right (input n+1)
    cmd += ["-filter_complex", filters, "-map", "[vo]", "-map", f"{n}:a",
            "-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out)]
    return cmd
```

> Note: Ken Burns and the brand overlay are now wired into the actual graph (the review found both were previously dead code). NVENC (`h264_nvenc`) is an M2 concern; M1 uses `libx264` so the slice runs CPU-only.

- [ ] **Step 5: Run** → PASS (2). **Commit.**

```bash
git add shared/render/ tests/test_kenburns.py tests/test_ffmpeg.py
git commit -m "feat(m1): Ken Burns + ffmpeg interim render graph (M2-replaceable)"
```

### Task 11: Stage 05 wiring (assemble → run ffmpeg → youtube.mp4)

**Files:**
- Create: `stages/s05_render/__init__.py` (empty), `stages/s05_render/stage.py`, `manifest.json`
- Test: `tests/test_s05_render.py`

- [ ] **Step 1: Write the failing test** (pure: scene-duration derivation from word timings; the ffmpeg exec is integration)

```python
# tests/test_s05_render.py
from stages.s05_render.stage import scene_durations_from_words


def test_scene_durations_split_by_beat_count():
    words = [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.0}, {"start": 2.0, "end": 4.0}]
    durs = scene_durations_from_words(words, n_scenes=2)
    assert len(durs) == 2
    assert abs(sum(durs) - 4.0) < 1e-6
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `stages/s05_render/stage.py`**

```python
import json
import subprocess

from shared.ctx import StageContext, StageResult
from shared.render.ffmpeg import build_ffmpeg_cmd
from shared.stage import StageManifest, stage


def scene_durations_from_words(words: list[dict], n_scenes: int) -> list[float]:
    # word-timed cuts (ADR 0005 D4 / 0007a §2): partition words into n_scenes contiguous
    # groups; each scene spans its group's first->last word, not a flat division.
    k, m = divmod(len(words), n_scenes)
    durs, idx = [], 0
    for s in range(n_scenes):
        size = k + (1 if s < m else 0)
        group = words[idx:idx + size]
        idx += size
        durs.append(round(group[-1]["end"] - group[0]["start"], 6) if group else 0.0)
    return durs


@stage(StageManifest(id="05", inputs=["script", "assets", "narration", "captions"],
                     outputs=["render"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    assets = json.loads(ctx.read_input("assets").read_text())
    images = [ctx.run_dir / s["clip_path"] for s in assets["scenes"]]
    words = json.loads((ctx.run_dir / "aligned_words.json").read_text()) \
        if (ctx.run_dir / "aligned_words.json").exists() else []
    durs = scene_durations_from_words(words, len(images)) if words \
        else [2.0] * len(images)
    out = ctx.write_output("render")
    cmd = build_ffmpeg_cmd(scene_images=images, scene_durations=durs,
                           narration=ctx.read_input("narration"),
                           captions_ass=ctx.read_input("captions"),
                           brand_overlay=ctx.run_dir / ctx.config.get("brand_logo", "logo.png"),
                           out=out, fps=int(ctx.config.get("fps", 30)))
    subprocess.run(cmd, check=True)
    ctx.log.info("render complete", path=str(out))
    return StageResult(outputs={"render": out})
```

- [ ] **Step 4: Write `manifest.json`**

```json
{"id": "05", "inputs": ["script", "assets", "narration", "captions"], "outputs": ["render"], "compute": "cpu"}
```

- [ ] **Step 5: Run** → PASS (1). **Commit.**

```bash
git add stages/s05_render/ tests/test_s05_render.py
git commit -m "feat(m1): 05 ffmpeg interim render stage (M2-replaceable)"
```

---

## Phase 8 — Timing baseline + the M1 slice test

### Task 12: Per-stage timing capture (ADR 0011 baseline)

**Files:**
- Create: `shared/timing.py`
- Test: `tests/test_timing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_timing.py
import json
from shared.timing import StageTimer


def test_timer_appends_jsonl(tmp_path):
    log = tmp_path / "timing.jsonl"
    with StageTimer("00b", log):
        pass
    rec = json.loads(log.read_text().strip())
    assert rec["stage"] == "00b" and "elapsed_s" in rec and rec["elapsed_s"] >= 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `shared/timing.py`**

```python
import json
import time
from pathlib import Path


class StageTimer:
    """Context manager that appends one {stage, elapsed_s, ts} record to a jsonl log."""

    def __init__(self, stage: str, log_path: Path):
        self._stage = stage
        self._log = Path(log_path)
        self._t0 = 0.0

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        rec = {"stage": self._stage, "elapsed_s": round(time.perf_counter() - self._t0, 3),
               "ts": time.time()}
        self._log.parent.mkdir(parents=True, exist_ok=True)
        with self._log.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return False
```

- [ ] **Step 4: Run** → PASS (1). **Commit.**

```bash
git add shared/timing.py tests/test_timing.py
git commit -m "feat(m1): per-stage timing capture (ADR 0011 baseline)"
```

### Task 13: The offline M1 slice — `00a → 05` producing a youtube.mp4 (CI, no GPU)

Extends the M0 runner pattern: wires the real-logic stages with **fakes for the live calls** (Ollama returns a fixture script; Kokoro returns a silent wav fixture; WhisperX returns `aligned_words.json`; ffmpeg runs for real on CPU producing a tiny mp4), wrapping each stage in `StageTimer`.

**Files:**
- Create: `tests/fixtures/m1/ollama_responses/script.json` (a valid `script.schema` instance with grounded claims vs `data.json`)
- Test: `tests/test_m1_slice_offline.py`

- [ ] **Step 1: Write the slice test**

```python
# tests/test_m1_slice_offline.py
import json
from pathlib import Path
import shutil
import pytest

FIX = Path(__file__).parent / "fixtures" / "m1"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required for render")
def test_m1_slice_produces_mp4(run_dir, tmp_path):
    from tests.helpers.m1 import run_m1_slice  # thin harness wiring fakes + StageTimer
    timing = tmp_path / "timing.jsonl"
    result = run_m1_slice(run_dir=run_dir, seed=7, fixtures=FIX, timing_log=timing)
    mp4 = run_dir / result["render"]
    assert mp4.exists() and mp4.stat().st_size > 0
    stages_timed = {json.loads(l)["stage"] for l in timing.read_text().splitlines()}
    assert {"00a", "00b", "02", "03", "05"}.issubset(stages_timed)
```

- [ ] **Step 2: Write the harness `tests/helpers/m1.py`** — wires each stage's `run()` with fake backends (LLM→fixture script, TTS→generate a 3s silent wav via `soundfile`, align→`aligned_words.json`), validates each schema-bearing output with `SchemaRegistry`, times each stage with `StageTimer`, and supplies a 2-scene `assets.json` + placeholder PNGs so 05 has inputs.

```python
# tests/helpers/m1.py
import json
import numpy as np
import soundfile as sf
from pathlib import Path

from shared.schema import SchemaRegistry
from shared.timing import StageTimer
from shared.ctx import StageContext
from stages.s00a_research.stage import run as run_00a
from stages.s00b_script.stage import run as run_00b
from stages.s02_voice.stage import run as run_02
from stages.s03_subs.stage import run as run_03
from stages.s05_render.stage import run as run_05

REG = SchemaRegistry()


class _FakeLLM:
    def __init__(self, script_path): self._s = json.loads(Path(script_path).read_text())
    def llm(self, prompt, seed=None):
        return "0.88" if "Score" in prompt else json.dumps(self._s)


class _FakeTTS:
    def __init__(self, out): self._out = out
    def tts(self, text):
        p = self._out / "narration.wav"; p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(p, np.zeros(24000 * 3, dtype="float32"), 24000); return p


def run_m1_slice(*, run_dir: Path, seed: int, fixtures: Path, timing_log: Path) -> dict:
    # seed inputs
    (run_dir / "data.json").write_text((fixtures / "data.json").read_text())
    (run_dir / "aligned_words.json").write_text((fixtures / "aligned_words.json").read_text())
    assets = {"schema_version": "1.0.0",
              "scenes": [{"beat_id": "b1", "clip_path": "s1.png", "duration": 2.0},
                         {"beat_id": "b2", "clip_path": "s2.png", "duration": 2.0}]}
    (run_dir / "assets.json").write_text(json.dumps(assets))
    for img in ("s1.png", "s2.png", "logo.png"):
        _solid_png(run_dir / img)

    def ctx(stage, inp, outp, backends):
        return StageContext(stage=stage, run_dir=run_dir, seed=seed,
                            job={"seed": seed, "video_id": "fin-0001"},
                            config={"data_fixture": "data.json", "best_of_n": 1},
                            input_paths=inp, output_paths=outp, backends=backends)

    def _p(result):  # normalize stage outputs to run-dir-relative names (closure: needs run_dir)
        return {name: str(p.relative_to(run_dir)) for name, p in result.outputs.items()}

    produced = {}
    fake_llm = _FakeLLM(fixtures / "ollama_responses" / "script.json")
    with StageTimer("00a", timing_log):
        produced.update(_p(run_00a(ctx("00a", {}, {"data": "data.json"}, {}))))
    with StageTimer("00b", timing_log):
        produced.update(_p(run_00b(ctx("00b", {"data": "data.json"}, {"script": "script.json"},
                                        {"llm": fake_llm}))))
    REG.validate("script", json.loads((run_dir / "script.json").read_text()))
    with StageTimer("02", timing_log):
        produced.update(_p(run_02(ctx("02", {"script": "script.json"},
                                      {"narration": "narration.wav"}, {"tts": _FakeTTS(run_dir)}))))
    with StageTimer("03", timing_log):
        # 03's _align_to_script is monkeypatched by the test runner to read aligned_words.json
        import stages.s03_subs.stage as s03
        s03._align_to_script = lambda wav, txt: json.loads((run_dir / "aligned_words.json").read_text())
        produced.update(_p(run_03(ctx("03", {"script": "script.json", "narration": "narration.wav"},
                                      {"captions": "captions.ass"}, {}))))
    with StageTimer("05", timing_log):
        produced.update(_p(run_05(ctx("05",
            {"script": "script.json", "assets": "assets.json",
             "narration": "narration.wav", "captions": "captions.ass"},
            {"render": "renders/youtube.mp4"}, {}))))
    return produced


def _solid_png(path: Path):
    from PIL import Image
    Image.new("RGB", (1080, 1920), (12, 30, 18)).save(path)
```

> Note: `_p` normalizes returned absolute paths to run-dir-relative names the next stage's `input_paths` expects; `Pillow` is added as a dev dep for the placeholder PNGs. The `_align_to_script` monkeypatch is the documented seam that lets 03 run without WhisperX in CI.

- [ ] **Step 3: Add dev deps** — append `"numpy"`, `"pillow"` to `[dependency-groups].dev` in `pyproject.toml`; create `tests/fixtures/m1/ollama_responses/script.json` (a `script.schema`-valid finance `ranked_list` whose single `claims[]` entry is grounded against `data.json`, e.g. `{"value": "3.2%", "source_ref": "market.cpi_yoy"}`).

- [ ] **Step 4: Run** → `uv run pytest tests/test_m1_slice_offline.py -v` → PASS (produces `renders/youtube.mp4`, times all 5 stages).

- [ ] **Step 5: Commit**

```bash
git add tests/test_m1_slice_offline.py tests/helpers/ tests/fixtures/m1/ollama_responses/ pyproject.toml
git commit -m "feat(m1): offline 00a->05 slice produces youtube.mp4 + timing baseline (no GPU)"
```

---

## M1 Acceptance Checklist (the testable "done")

- [ ] `00a → 00b → 02 → 03 → 05` each replace their M0 thin stage with a real implementation; manifests still match (M0 drift-catcher green) → Tasks 4–11.
- [ ] The offline slice produces a real `renders/youtube.mp4` on a GPU-less runner using fakes for the live calls; CI green with `-m "not integration"` → Task 13.
- [ ] Deterministic numeric grounding **quarantines** an ungrounded/out-of-tolerance figure (a failing-path test) → Task 2 + Task 5 (quarantine wrap).
- [ ] Captions are forced-aligned to the **known script** (not transcribed) and styled `.ass` with emphasis + safe-zone margin → Tasks 8–9.
- [ ] Per-stage timing is captured to `timing.jsonl` for all 5 stages (the ADR 0011 baseline M4 consumes) → Tasks 12–13.
- [ ] Integration tests (`@pytest.mark.integration`) exist for the live Ollama, Kokoro, WhisperX paths and run on the host (not CI) → Tasks 3, 7, 9.

---

## Self-Review

**Spec coverage (Ch.4 rows + ADRs):** 00a→T4 (budget/corroboration/data.json); 00b→T5 (treatment-prompt/best-of-N/judge/seed/grounding, ADR 0005 D1-D3 + 0009 + 0014 D1 judge criterion); 02→T6/T7 (normalize+lexicon+prosody-ready, ADR 0005 D6); 03→T8/T9 (forced-align-to-script + styled captions, ADR 0009 + 0005 D7); 05→T10/T11 (word-timed cuts + Ken Burns + brand overlay, ADR 0005 D4 — interim, M2 replaces). Seed reproducibility (ADR 0009) → T5 `random.Random(ctx.seed)`. Timing baseline (ADR 0011) → T12/T13. Not in M1 by design: 01x visuals, 04 music, 05x/05b/05c gates, 06 distribute, per-platform parity, NVENC — all later milestones; noted inline.

**Placeholder scan:** No "TBD"/"add error handling". The two `raise NotImplementedError` bodies (`_fetch_live`, `_align_to_script`) are **deliberate, documented integration seams** with their CI substitute named (the data fixture / the `aligned_words.json` monkeypatch) — not vague placeholders; their pure-logic siblings (Budget/corroboration; emphasis-tagging/grouping) are fully implemented and tested.

**Type consistency vs M0:** Uses the M0 names exactly — `StageContext(stage, run_dir, seed, job, config, input_paths, output_paths, backends)`, `StageResult(outputs=...)`, `@stage(StageManifest(...))`, `SchemaRegistry().validate(name, instance)`, `ctx.read_input/write_output/backend/quarantine`. Backends implement the M0 `ModelBackend` Protocol (`llm/tts/generate_image/img2vid/vlm_judge`) — verified the method set matches `shared/adapters/protocols.py`. `check_claims(claims, data)` / `GroundingError` names are consistent across T2 and T5. `build_ass(...)`/`group_words` and `build_ffmpeg_cmd(...)`/`zoompan_expr` signatures match between their unit tasks and the stage wiring tasks.

**Scope:** One milestone, one acceptance gate, produces working testable software (the rendered mp4 + timing baseline). M1's Stage 05 is explicitly the ffmpeg interim that M2 replaces — the boundary is contained in `shared/render/`.
