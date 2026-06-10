# M0 — Build Contract & Offline DAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the spec's prose stage-contracts into executable artifacts — 11 versioned JSON Schemas, a fail-loud validation harness, a thin Stage SDK (`run(ctx)`), typed adapter Protocols with fixture-backed fakes, a content-addressed cache, and CI that runs the whole `00a → 06` DAG with **no GPU** — satisfying the ADR 0012 M0 acceptance checklist.

**Architecture:** Stages are pure functions of their declared inputs (`run(ctx) -> StageResult`); `ctx` maps declared input/output *names* to PVC paths, exposes the resolved config, seed, logger, and capability-backends. Backends are `typing.Protocol`s with two implementations: real (HTTP to host GPU, **out of M0 scope**) and fakes that replay fixtures keyed by `(capability, input_hash)`. A content-addressed cache keyed `(stage, input_hash, seed)` skips already-computed work. Every artifact crossing a stage boundary is validated against a versioned JSON Schema; CI asserts no stage source branches on `platform ==` / `niche ==`.

**Tech Stack:** Python 3.12, `uv` (env + lockfile), `pytest`, `jsonschema` (Draft 2020-12), `typing.Protocol`, stdlib `hashlib`/`json` for canonical hashing. Bash lifecycle (`Makefile` + `scripts/`) already exists; this plan fills the `make test` body.

**Decisions made here (left open by ADR 0012, resolved for M0):**
- **Cache backend:** file-based content-addressed store under `runs/.cache/` (not sqlite). Sqlite remains deferred (ADR 0012 "out of scope").
- **Fake fidelity:** fixture replay only (no tiny-real CI model). Deferred per ADR 0012.
- **`layout.schema.json`:** deferred to M2/M3 (the compositor milestone, ADR 0007/0007a). M0 authors the 11 schemas named in spec Ch.10.
- **Schemas authored in M0 (11):** `job`, `script`, `assets`, `provenance`, `vision`, `qc`, `creative_qc`, `posts`, `profile`, `format`, `feature_record`.

---

## File Structure

```
pyproject.toml                      # uv project: deps (jsonschema, pytest), ruff, package config
shared/                             # the Stage SDK + cross-cutting plumbing (one Python package)
  __init__.py
  hashing.py                        # canonical_json(), input_hash(), cache_key()
  schema.py                         # SchemaRegistry, validate(), version-compat check
  ctx.py                            # StageContext (ctx), StageResult, Degrade/Quarantine signals
  stage.py                          # Stage base + @stage registry + StageManifest
  config.py                         # resolve_config(): global -> niche -> batch -> per-platform
  cache.py                          # file-based content-addressed cache (get/put by cache_key)
  logging.py                        # structured logger factory
  adapters/
    __init__.py
    protocols.py                    # DistributionAdapter, ModelBackend caps, LayoutEngine Protocols
    types.py                        # PostMeta, PostReceipt, Visibility, Judgment dataclasses
    fakes.py                        # FixtureBackend, FixtureDistributionAdapter (replay fixtures)
schemas/                            # the 11 versioned JSON Schemas (Draft 2020-12)
  job.schema.json  script.schema.json  assets.schema.json  provenance.schema.json
  vision.schema.json  qc.schema.json  creative_qc.schema.json  posts.schema.json
  profile.schema.json  format.schema.json  feature_record.schema.json
stages/                             # one package per pipeline stage; thin in M0 (read->backend->write)
  __init__.py
  registry.py                       # imports every stage module so @stage decorators register
  s00a_research/  s00b_script/  s01a_stock/  s01b_imagegen/  s01c_img2vid/
  s01d_upscale/   s01e_dataviz/  s02_voice/  s03_subs/  s04_music/
  s05_render/     s05x_vision/   s05b_safety/ s05c_qc/   s06_distribute/
    (each: __init__.py, stage.py [run(ctx)], manifest.json)
tests/
  conftest.py                       # fixtures: tmp run dir, golden-chain loader
  fixtures/
    golden/                         # ONE golden video's full chain (data -> ... -> posts)
    backends/                       # fake-backend replay fixtures keyed by (capability, input_hash)
  test_hashing.py  test_schema_harness.py  test_schemas_validate_golden.py
  test_ctx.py  test_config.py  test_cache.py  test_adapters_fakes.py
  test_stage_manifests.py          # drift-catcher: manifests <-> (M0) declared edges
  test_no_platform_branches.py     # CI assertion: no `platform ==` / `niche ==` in stages/
  test_full_dag_offline.py         # 00a -> 06 against fakes, no GPU, asserts golden posts record
.github/workflows/ci.yml            # GPU-less runner: uv sync + pytest
```

**Responsibility boundaries:** `shared/` owns *how a stage runs* (never domain logic); `schemas/` owns *what crosses a boundary*; `stages/<id>/` owns *one stage's transform* and is thin in M0 (the real GPU/LLM work lands M1+). Files split by responsibility, kept small enough to hold in context.

---

## Phase 0 — Project tooling

### Task 0: Python project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `shared/__init__.py`, `stages/__init__.py`, `tests/__init__.py` (empty)
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "shorts-creator"
version = "0.0.0"
requires-python = ">=3.12"
dependencies = ["jsonschema>=4.21"]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.4"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.setuptools]
packages = ["shared", "stages"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Create empty package files**

```bash
touch shared/__init__.py stages/__init__.py tests/__init__.py
```

- [ ] **Step 3: Write `tests/conftest.py` with a tmp-run-dir fixture**

```python
import json
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """An empty per-test run directory standing in for runs/<batch-id>/<video-id>/."""
    d = tmp_path / "run"
    d.mkdir()
    return d


def write_json(path: Path, obj: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))
    return path
```

- [ ] **Step 4: Verify the toolchain installs and pytest runs (zero tests is OK)**

Run: `uv sync && uv run pytest -q`
Expected: exit 0, "no tests ran" (or collected 0 items).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml shared/__init__.py stages/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: python project scaffold (uv + pytest + jsonschema)"
```

---

## Phase 1 — Primitives + schema-version harness (ADR 0012 §8.1)

### Task 1: Canonical JSON, `input_hash`, and `cache_key`

ADR 0012 §1: `input_hash = sha256(` canonical-JSON of `{declared_input_digests: {name: sha256(bytes)} (sorted), resolved_config, stage_version}` `)`; generative stages also fold in `model_id + graph_version`; cache key is `(stage, input_hash, seed)`. Status fields are excluded (caller passes only declared inputs).

**Files:**
- Create: `shared/hashing.py`
- Test: `tests/test_hashing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_hashing.py
from shared.hashing import canonical_json, sha256_bytes, input_hash, cache_key


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_has_no_insignificant_whitespace():
    assert canonical_json({"a": 1}) == '{"a":1}'


def test_input_hash_stable_and_order_independent():
    digests = {"data": sha256_bytes(b"x"), "job": sha256_bytes(b"y")}
    h1 = input_hash(declared_input_digests=digests, resolved_config={"k": 1}, stage_version="1.0.0")
    h2 = input_hash(declared_input_digests=dict(reversed(list(digests.items()))),
                    resolved_config={"k": 1}, stage_version="1.0.0")
    assert h1 == h2
    assert len(h1) == 64  # hex sha256


def test_input_hash_changes_on_config_change():
    digests = {"data": sha256_bytes(b"x")}
    a = input_hash(declared_input_digests=digests, resolved_config={"k": 1}, stage_version="1.0.0")
    b = input_hash(declared_input_digests=digests, resolved_config={"k": 2}, stage_version="1.0.0")
    assert a != b


def test_generative_hash_folds_in_model_and_graph():
    digests = {"img": sha256_bytes(b"x")}
    base = input_hash(declared_input_digests=digests, resolved_config={}, stage_version="1.0.0")
    gen = input_hash(declared_input_digests=digests, resolved_config={}, stage_version="1.0.0",
                     model_id="flux.1-schnell", graph_version="g1")
    assert base != gen


def test_cache_key_includes_seed():
    assert cache_key("00b", "abc", 1) != cache_key("00b", "abc", 2)
    assert cache_key("00b", "abc", 1) == ("00b", "abc", 1)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: FAIL — `ModuleNotFoundError: shared.hashing`.

- [ ] **Step 3: Implement `shared/hashing.py`**

```python
import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_hash(
    *,
    declared_input_digests: dict[str, str],
    resolved_config: Any,
    stage_version: str,
    model_id: str | None = None,
    graph_version: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "declared_input_digests": dict(sorted(declared_input_digests.items())),
        "resolved_config": resolved_config,
        "stage_version": stage_version,
    }
    if model_id is not None:
        payload["model_id"] = model_id
    if graph_version is not None:
        payload["graph_version"] = graph_version
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def cache_key(stage: str, input_hash_hex: str, seed: int) -> tuple[str, str, int]:
    return (stage, input_hash_hex, seed)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add shared/hashing.py tests/test_hashing.py
git commit -m "feat: canonical-json input_hash + cache_key (ADR 0012 §1)"
```

### Task 2: Schema registry + version-compatibility check

ADR 0012 §5: every schema + instance carries a semver `schema_version`; harness **fails** on a **major** mismatch, **warns** on a **minor** mismatch.

**Files:**
- Create: `shared/schema.py`
- Test: `tests/test_schema_harness.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schema_harness.py
import warnings
import pytest
from shared.schema import version_compatible, SchemaError


def test_same_version_ok():
    assert version_compatible(schema="1.2.0", instance="1.2.0") is True


def test_minor_mismatch_warns_but_ok():
    with pytest.warns(UserWarning):
        assert version_compatible(schema="1.3.0", instance="1.2.0") is True


def test_major_mismatch_raises():
    with pytest.raises(SchemaError):
        version_compatible(schema="2.0.0", instance="1.9.0")


def test_missing_instance_version_raises():
    with pytest.raises(SchemaError):
        version_compatible(schema="1.0.0", instance=None)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_schema_harness.py -v`
Expected: FAIL — `ModuleNotFoundError: shared.schema`.

- [ ] **Step 3: Implement `shared/schema.py`**

```python
import json
import warnings
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


class SchemaError(Exception):
    """Raised on validation failure or incompatible schema_version."""


def _parse_semver(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    if len(parts) != 3:
        raise SchemaError(f"bad semver: {v!r}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def version_compatible(*, schema: str, instance: str | None) -> bool:
    if instance is None:
        raise SchemaError("instance is missing schema_version")
    smaj, smin, _ = _parse_semver(schema)
    imaj, imin, _ = _parse_semver(instance)
    if smaj != imaj:
        raise SchemaError(f"major schema_version mismatch: schema {schema} vs instance {instance}")
    if smin != imin:
        warnings.warn(
            f"minor schema_version mismatch: schema {schema} vs instance {instance}",
            UserWarning,
            stacklevel=2,
        )
    return True


class SchemaRegistry:
    """Loads schemas/<name>.schema.json once and validates instances against them."""

    def __init__(self, schemas_dir: Path = SCHEMAS_DIR):
        self._dir = schemas_dir
        self._cache: dict[str, dict[str, Any]] = {}

    def schema(self, name: str) -> dict[str, Any]:
        if name not in self._cache:
            path = self._dir / f"{name}.schema.json"
            if not path.exists():
                raise SchemaError(f"no schema named {name!r} at {path}")
            self._cache[name] = json.loads(path.read_text())
        return self._cache[name]

    def validate(self, name: str, instance: dict[str, Any]) -> None:
        schema = self.schema(name)
        version_compatible(
            schema=schema.get("schema_version", "0.0.0"),
            instance=instance.get("schema_version"),
        )
        errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: e.json_path)
        if errors:
            msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise SchemaError(f"{name} instance invalid: {msgs}")
```

> Note: each schema JSON carries a top-level `"schema_version"` string (the schema's own version). Instances carry their own `"schema_version"` field. `validate()` checks compat first, then structural validity.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_schema_harness.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add shared/schema.py tests/test_schema_harness.py
git commit -m "feat: schema registry + semver compat (fail-major/warn-minor, ADR 0012 §5)"
```

---

## Phase 2 — The 11 schemas + golden fixtures (ADR 0012 §8.2)

> **Test design (DRY):** rather than one near-identical test per schema, `test_schemas_validate_golden.py` parametrizes over every `(schema, golden fixture)` pair and asserts each validates. Negative cases (wrong-typed field, missing required field, major-version mismatch) are asserted once against `job` as the representative — these exercise the *harness*, which is schema-agnostic. This is the ADR 0012 acceptance item "rejects a fixture with a wrong-typed field, a missing required field, and a major-version mismatch."

Each schema below uses Draft 2020-12, `"type": "object"`, `"additionalProperties": false` at the top level (forces the contract to be explicit), a required `"schema_version"`, and the field contract drawn from spec Ch.5.

### Task 3: Author `job.schema.json` + the negative harness tests

**Files:**
- Create: `schemas/job.schema.json`
- Create: `tests/fixtures/golden/job.json`
- Test: `tests/test_schemas_validate_golden.py` (negative cases)

- [ ] **Step 1: Write `schemas/job.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "job.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "batch_id", "video_id", "niche", "profile",
               "platform_targets", "seed", "stages", "paths"],
  "properties": {
    "schema_version": {"type": "string"},
    "batch_id": {"type": "string"},
    "video_id": {"type": "string"},
    "niche": {"type": "string"},
    "profile": {"type": "string"},
    "platform_targets": {"type": "array", "items": {"enum": ["youtube", "tiktok"]}, "minItems": 1},
    "seed": {"type": "integer"},
    "stages": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "additionalProperties": false,
        "required": ["status"],
        "properties": {
          "status": {"enum": ["pending", "running", "done", "quarantined", "failed"]},
          "detail": {"type": "string"}
        }
      }
    },
    "paths": {"type": "object", "additionalProperties": {"type": "string"}}
  }
}
```

- [ ] **Step 2: Write `tests/fixtures/golden/job.json`**

```json
{
  "schema_version": "1.0.0",
  "batch_id": "2026-06-09",
  "video_id": "fin-0001",
  "niche": "finance",
  "profile": "finance",
  "platform_targets": ["youtube", "tiktok"],
  "seed": 424242,
  "stages": {"00a": {"status": "done"}, "00b": {"status": "pending"}},
  "paths": {"data": "data/data.json", "script": "fin-0001/script.json"}
}
```

- [ ] **Step 3: Write the negative harness tests**

```python
# tests/test_schemas_validate_golden.py
import copy
import json
from pathlib import Path
import pytest
from shared.schema import SchemaRegistry, SchemaError

REG = SchemaRegistry()
GOLDEN = Path(__file__).parent / "fixtures" / "golden"


def _job():
    return json.loads((GOLDEN / "job.json").read_text())


def test_rejects_wrong_typed_field():
    bad = _job()
    bad["seed"] = "not-an-int"
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


def test_rejects_missing_required_field():
    bad = _job()
    del bad["video_id"]
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


def test_rejects_major_version_mismatch():
    bad = _job()
    bad["schema_version"] = "2.0.0"
    with pytest.raises(SchemaError):
        REG.validate("job", bad)


def test_rejects_unknown_status_enum():
    bad = _job()
    bad["stages"]["00a"]["status"] = "frozen"
    with pytest.raises(SchemaError):
        REG.validate("job", bad)
```

- [ ] **Step 4: Run to verify the negative tests pass**

Run: `uv run pytest tests/test_schemas_validate_golden.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add schemas/job.schema.json tests/fixtures/golden/job.json tests/test_schemas_validate_golden.py
git commit -m "feat: job.schema + negative harness tests (ADR 0012 acceptance #1)"
```

### Task 4: Author `script.schema.json` (the richest contract)

Spec Ch.5: `format`, per-beat structured layout data keyed to format, `treatment`, `hook` + scored variants, narration beats w/ prosody, captions w/ emphasis, music mood+energy, per-platform metadata, claims+citations with `{value, source_ref}`, disclaimer, optional affiliate. Per-format beat shapes: `ranked_list` → `items[]{rank,title,body,media_query,stat?}`; `head_to_head` → `{side_a,side_b,verdict,round[]}` with `side_*:{media_query,label}`, `verdict:{text}`, `round:{metrics}`.

**Files:**
- Create: `schemas/script.schema.json`
- Create: `tests/fixtures/golden/script.json`

- [ ] **Step 1: Write `schemas/script.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "script.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "format", "treatment", "hook", "narration_beats",
               "captions", "music", "platform_meta", "claims", "disclaimer", "layout_data"],
  "properties": {
    "schema_version": {"type": "string"},
    "format": {"type": "string"},
    "treatment": {
      "type": "object", "additionalProperties": false,
      "required": ["thesis", "angle", "tone", "visual_motif", "energy_curve"],
      "properties": {
        "thesis": {"type": "string"}, "angle": {"type": "string"}, "tone": {"type": "string"},
        "visual_motif": {"type": "array", "items": {"type": "string"}},
        "energy_curve": {"type": "array", "items": {"type": "number"}}
      }
    },
    "hook": {
      "type": "object", "additionalProperties": false,
      "required": ["spoken", "on_screen_text", "first_frame_visual", "duration"],
      "properties": {
        "spoken": {"type": "string"}, "on_screen_text": {"type": "string"},
        "first_frame_visual": {"type": "string"}, "duration": {"type": "number"}
      }
    },
    "hook_variants": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["spoken", "score"],
        "properties": {"spoken": {"type": "string"}, "score": {"type": "number"}}
      }
    },
    "narration_beats": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["text"],
        "properties": {
          "text": {"type": "string"},
          "prosody": {"type": "string"},
          "emphasis": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "captions": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["text"],
        "properties": {"text": {"type": "string"},
                       "emphasis": {"type": "array", "items": {"type": "string"}}}
      }
    },
    "music": {
      "type": "object", "additionalProperties": false,
      "required": ["mood", "energy"],
      "properties": {"mood": {"type": "string"}, "energy": {"type": "string"}}
    },
    "platform_meta": {
      "type": "object",
      "additionalProperties": {
        "type": "object", "additionalProperties": false,
        "required": ["title", "description", "hashtags"],
        "properties": {
          "title": {"type": "string"}, "description": {"type": "string"},
          "hashtags": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "claims": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["value", "source_ref"],
        "properties": {"value": {"type": "string"}, "source_ref": {"type": "string"}}
      }
    },
    "disclaimer": {"type": "string"},
    "primary_keyword": {"type": "string"},
    "affiliate": {"type": "object"},
    "layout_data": {
      "description": "per-beat structured data keyed to the format (ADR 0007 D3 / 0007a §7b)",
      "oneOf": [
        {
          "type": "object", "additionalProperties": false,
          "required": ["kind", "items"],
          "properties": {
            "kind": {"const": "ranked_list"},
            "items": {
              "type": "array",
              "items": {
                "type": "object", "additionalProperties": false,
                "required": ["rank", "title", "body", "media_query"],
                "properties": {
                  "rank": {"type": "integer"}, "title": {"type": "string"},
                  "body": {"type": "string"}, "media_query": {"type": "string"},
                  "stat": {"type": "string"}
                }
              }
            }
          }
        },
        {
          "type": "object", "additionalProperties": false,
          "required": ["kind", "side_a", "side_b", "verdict", "round"],
          "properties": {
            "kind": {"const": "head_to_head"},
            "side_a": {"$ref": "#/$defs/side"},
            "side_b": {"$ref": "#/$defs/side"},
            "verdict": {"type": "object", "additionalProperties": false,
                        "required": ["text"], "properties": {"text": {"type": "string"}}},
            "round": {"type": "array", "items": {
              "type": "object", "additionalProperties": false,
              "required": ["metrics"],
              "properties": {"metrics": {"type": "object"}}}}
          }
        }
      ]
    }
  },
  "$defs": {
    "side": {
      "type": "object", "additionalProperties": false,
      "required": ["media_query", "label"],
      "properties": {"media_query": {"type": "string"}, "label": {"type": "string"}}
    }
  }
}
```

- [ ] **Step 2: Write `tests/fixtures/golden/script.json`** (a `ranked_list` finance script)

```json
{
  "schema_version": "1.0.0",
  "format": "ranked_list",
  "treatment": {"thesis": "3 dividend stocks beating inflation", "angle": "data-first",
                "tone": "measured", "visual_motif": ["green-candles"], "energy_curve": [0.3, 0.7, 1.0]},
  "hook": {"spoken": "These 3 stocks quietly beat inflation.", "on_screen_text": "3 that beat inflation",
           "first_frame_visual": "typographic-card", "duration": 1.8},
  "hook_variants": [{"spoken": "Inflation lost to these 3.", "score": 0.81}],
  "narration_beats": [{"text": "Number three.", "prosody": "rising", "emphasis": ["three"]}],
  "captions": [{"text": "3 that beat inflation", "emphasis": ["beat"]}],
  "music": {"mood": "confident", "energy": "mid"},
  "platform_meta": {"youtube": {"title": "3 Stocks Beating Inflation",
                                "description": "Not financial advice. #investing",
                                "hashtags": ["investing"]}},
  "claims": [{"value": "7.2%", "source_ref": "data.market.cpi_yoy"}],
  "disclaimer": "Not financial advice.",
  "layout_data": {"kind": "ranked_list",
    "items": [{"rank": 1, "title": "ACME", "body": "Yield 4.1%", "media_query": "acme logo", "stat": "4.1%"}]}
}
```

- [ ] **Step 3: Add a positive validation assertion**

Add to `tests/test_schemas_validate_golden.py`:

```python
def test_script_golden_validates():
    REG.validate("script", json.loads((GOLDEN / "script.json").read_text()))
```

- [ ] **Step 4: Run**

Run: `uv run pytest tests/test_schemas_validate_golden.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add schemas/script.schema.json tests/fixtures/golden/script.json tests/test_schemas_validate_golden.py
git commit -m "feat: script.schema (treatment/hook/layout_data) + golden fixture"
```

### Task 5: Author the remaining 9 schemas + their golden fixtures

Each is a small object schema with `additionalProperties: false` and a required `schema_version`. Write all 9 schema files and 9 golden fixtures, using these field contracts (from spec Ch.5):

| schema | required fields (beyond `schema_version`) |
|---|---|
| `assets` | `scenes`: array of `{beat_id:str, clip_path:str, duration:number}` |
| `provenance` | `assets`: array of `{asset_id:str, source:str, url:str, license:str, fetch_date:str}` |
| `vision` | `keyframes`: array of `{frame_id:str, kind:enum[hook,end_card,beat], observations:string[]}` |
| `qc` | `verdict`: enum`[pass,quarantine]`; `checks`: object→`{pass:bool, detail?:str}` |
| `creative_qc` | `scores`: object→number; `overall`:number; `floor`:number; `pass`:bool |
| `posts` | `video_id`:str; `platform`:enum`[youtube,tiktok]`; `state`:enum`[intent,confirmed]`; `visibility`:enum`[private,self_only,public]`; `remote_post_id?`:str; `timestamp`:str |
| `profile` | `niche`:str; `persona`:object; `brand_kit`:`{palette:string[], font:str, logo:str}`; `defaults`:object |
| `format` | `id`:str; `beat_pattern`:string[]; `lane_support`:`{visual:bool, audio:bool}`; `data_shape`:enum`[ranked_list,head_to_head]` |
| `feature_record` | `video_id`:str; `format`:str; `seed`:int; `hook_variant_id`:str; `judge_scores`:object→number; `metrics`:object (reserved, may be empty) |

- [ ] **Step 1: Write all 9 `schemas/<name>.schema.json` files** following the `job`/`script` pattern (Draft 2020-12, `additionalProperties:false`, `"schema_version":"1.0.0"`, the required-field lists above). Example for `posts`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "posts.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "video_id", "platform", "state", "visibility", "timestamp"],
  "properties": {
    "schema_version": {"type": "string"},
    "video_id": {"type": "string"},
    "platform": {"enum": ["youtube", "tiktok"]},
    "state": {"enum": ["intent", "confirmed"]},
    "visibility": {"enum": ["private", "self_only", "public"]},
    "remote_post_id": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

- [ ] **Step 2: Write a matching `tests/fixtures/golden/<name>.json`** for each, with `schema_version:"1.0.0"` and a minimal valid instance. Example `posts.json`:

```json
{"schema_version": "1.0.0", "video_id": "fin-0001", "platform": "youtube",
 "state": "confirmed", "visibility": "public", "remote_post_id": "yt_abc123",
 "timestamp": "2026-06-09T08:00:00Z"}
```

- [ ] **Step 3: Replace the positive test with a parametrized sweep over all schemas**

Replace `test_script_golden_validates` in `tests/test_schemas_validate_golden.py` with:

```python
ALL_SCHEMAS = ["job", "script", "assets", "provenance", "vision", "qc",
               "creative_qc", "posts", "profile", "format", "feature_record"]


@pytest.mark.parametrize("name", ALL_SCHEMAS)
def test_golden_fixture_validates(name):
    REG.validate(name, json.loads((GOLDEN / f"{name}.json").read_text()))
```

- [ ] **Step 4: Run — all 11 schemas validate their golden fixtures**

Run: `uv run pytest tests/test_schemas_validate_golden.py -v`
Expected: PASS (4 negative + 11 parametrized = 15).

- [ ] **Step 5: Commit**

```bash
git add schemas/ tests/fixtures/golden/ tests/test_schemas_validate_golden.py
git commit -m "feat: author remaining 9 schemas + golden fixtures (11 total validate, ADR 0012 acceptance #2)"
```

---

## Phase 3 — Stage SDK: `ctx`, base, manifests (ADR 0012 §8.3)

### Task 6: `StageContext`, `StageResult`, and failure signals

ADR 0012 §2: `run(ctx) -> StageResult`; `ctx` exposes `read_input(name)`, `write_output(name)`, `job`, `seed`, `config`, `log`, `backend(capability)`, `quarantine(reason)`, `degrade(reason)`. Inputs/outputs by **declared name** mapped to paths by the SDK.

**Files:**
- Create: `shared/logging.py`, `shared/ctx.py`
- Test: `tests/test_ctx.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ctx.py
import json
from pathlib import Path
import pytest
from shared.ctx import StageContext, StageResult, Quarantined, Degraded


def _ctx(run_dir: Path) -> StageContext:
    (run_dir / "data.json").write_text(json.dumps({"hello": "world"}))
    return StageContext(
        stage="00b", run_dir=run_dir, seed=7,
        job={"seed": 7, "video_id": "v1"},
        config={"k": 1},
        input_paths={"data": "data.json"},
        output_paths={"script": "script.json"},
        backends={},
    )


def test_read_input_by_name(run_dir):
    ctx = _ctx(run_dir)
    assert json.loads(ctx.read_input("data").read_text()) == {"hello": "world"}


def test_read_undeclared_input_raises(run_dir):
    ctx = _ctx(run_dir)
    with pytest.raises(KeyError):
        ctx.read_input("not_declared")


def test_write_output_returns_path_under_run_dir(run_dir):
    ctx = _ctx(run_dir)
    p = ctx.write_output("script")
    p.write_text("{}")
    assert p == run_dir / "script.json" and p.exists()


def test_seed_and_job_exposed(run_dir):
    ctx = _ctx(run_dir)
    assert ctx.seed == 7 and ctx.job["video_id"] == "v1"


def test_quarantine_signal(run_dir):
    ctx = _ctx(run_dir)
    with pytest.raises(Quarantined):
        ctx.quarantine("safety failed")


def test_set_status_atomic_section_scoped(run_dir):
    (run_dir / "job.json").write_text(json.dumps({"seed": 7, "video_id": "v1", "stages": {}}))
    _ctx(run_dir).set_status("running")
    job = json.loads((run_dir / "job.json").read_text())
    assert job["stages"]["00b"]["status"] == "running"   # only this stage's section touched
    assert not (run_dir / "job.json.tmp").exists()        # temp renamed away
```

(Add `import json` at the top of `tests/test_ctx.py`.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ctx.py -v`
Expected: FAIL — `ModuleNotFoundError: shared.ctx`.

- [ ] **Step 3: Implement `shared/logging.py`**

```python
import json
import sys
from datetime import datetime, timezone


class StructuredLogger:
    def __init__(self, stage: str):
        self._stage = stage

    def _emit(self, level: str, msg: str, **kw):
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
               "stage": self._stage, "msg": msg, **kw}
        print(json.dumps(rec), file=sys.stderr)

    def info(self, msg: str, **kw): self._emit("info", msg, **kw)
    def warning(self, msg: str, **kw): self._emit("warning", msg, **kw)
    def error(self, msg: str, **kw): self._emit("error", msg, **kw)


def get_logger(stage: str) -> StructuredLogger:
    return StructuredLogger(stage)
```

- [ ] **Step 4: Implement `shared/ctx.py`**

```python
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.logging import StructuredLogger, get_logger


class Quarantined(Exception):
    """Stage signalled a hard quality/safety stop; the video is parked."""


class Degraded(Exception):
    """Stage signalled a soft degrade (e.g. budget tripped); run continues reduced."""


@dataclass
class StageResult:
    outputs: dict[str, Path] = field(default_factory=dict)
    cache_hit: bool = False


@dataclass
class StageContext:
    stage: str
    run_dir: Path
    seed: int
    job: dict[str, Any]
    config: dict[str, Any]
    input_paths: dict[str, str]
    output_paths: dict[str, str]
    backends: dict[str, Any]
    log: StructuredLogger = field(init=False)

    def __post_init__(self):
        self.log = get_logger(self.stage)

    def read_input(self, name: str) -> Path:
        if name not in self.input_paths:
            raise KeyError(f"{self.stage}: undeclared input {name!r}")
        return self.run_dir / self.input_paths[name]

    def write_output(self, name: str) -> Path:
        if name not in self.output_paths:
            raise KeyError(f"{self.stage}: undeclared output {name!r}")
        p = self.run_dir / self.output_paths[name]
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def backend(self, capability: str) -> Any:
        if capability not in self.backends:
            raise KeyError(f"{self.stage}: no backend for capability {capability!r}")
        return self.backends[capability]

    def quarantine(self, reason: str) -> None:
        self.log.warning("quarantine", reason=reason)
        raise Quarantined(reason)

    def degrade(self, reason: str) -> None:
        self.log.warning("degrade", reason=reason)
        raise Degraded(reason)

    def set_status(self, status: str) -> None:
        """Section-scoped atomic status update for THIS stage (ADR 0012 §4): read job.json,
        set stages[self.stage].status, write-temp + rename. One writer per <video-id>/ subtree."""
        job_path = self.run_dir / "job.json"
        job = json.loads(job_path.read_text())
        job.setdefault("stages", {})[self.stage] = {"status": status}
        tmp = job_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(job))
        tmp.rename(job_path)   # atomic rename (ADR 0003 D6)
```

- [ ] **Step 5: Run to verify pass, then commit**

Run: `uv run pytest tests/test_ctx.py -v` → PASS (5).

```bash
git add shared/logging.py shared/ctx.py tests/test_ctx.py
git commit -m "feat: StageContext/StageResult + quarantine/degrade signals (ADR 0012 §2)"
```

### Task 7: Stage base, `@stage` registry, and `StageManifest`

ADR 0012 §3: each stage ships `{id, inputs[], outputs[], compute: cpu|gpu, capability?, resources?}`; Argo templates hand-written; a CI drift-catcher asserts templates ⟷ manifests agree.

**Files:**
- Create: `shared/stage.py`
- Test: `tests/test_stage_manifests.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_stage_manifests.py
from shared.stage import stage, StageManifest, REGISTRY, load_manifest


def test_stage_decorator_registers():
    REGISTRY.clear()

    @stage(StageManifest(id="demo", inputs=["a"], outputs=["b"], compute="cpu"))
    def run(ctx):
        return None

    assert "demo" in REGISTRY
    assert REGISTRY["demo"].manifest.outputs == ["b"]


def test_manifest_requires_capability_for_gpu():
    import pytest
    with pytest.raises(ValueError):
        StageManifest(id="g", inputs=[], outputs=[], compute="gpu")  # no capability
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_stage_manifests.py -v`
Expected: FAIL — `ModuleNotFoundError: shared.stage`.

- [ ] **Step 3: Implement `shared/stage.py`**

```python
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from shared.ctx import StageContext, StageResult


@dataclass(frozen=True)
class StageManifest:
    id: str
    inputs: list[str]
    outputs: list[str]
    compute: Literal["cpu", "gpu"]
    capability: str | None = None
    resources: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.compute == "gpu" and not self.capability:
            raise ValueError(f"gpu stage {self.id} must declare a capability")


@dataclass
class RegisteredStage:
    manifest: StageManifest
    fn: Callable[[StageContext], StageResult | None]


REGISTRY: dict[str, RegisteredStage] = {}


def stage(manifest: StageManifest):
    def deco(fn: Callable[[StageContext], StageResult | None]):
        REGISTRY[manifest.id] = RegisteredStage(manifest=manifest, fn=fn)
        return fn
    return deco


def load_manifest(path: Path) -> StageManifest:
    raw = json.loads(path.read_text())
    return StageManifest(**raw)
```

- [ ] **Step 4: Run → PASS (2). Commit.**

```bash
git add shared/stage.py tests/test_stage_manifests.py
git commit -m "feat: Stage base + @stage registry + StageManifest (ADR 0012 §3)"
```

### Task 8: Typed config resolver

ADR 0010 D5: one resolver, precedence **global → niche → batch → per-platform**, deep-merge, so stages never branch on `platform ==` / `niche ==`.

**Files:**
- Create: `shared/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
from shared.config import resolve_config


def test_precedence_later_wins():
    cfg = resolve_config(
        global_defaults={"fps": 30, "cta": "follow"},
        niche={"cta": "subscribe"},
        batch={},
        per_platform={"cta": "subscribe+bell"},
    )
    assert cfg == {"fps": 30, "cta": "subscribe+bell"}


def test_deep_merge_nested():
    cfg = resolve_config(
        global_defaults={"render": {"fps": 30, "grade": "neutral"}},
        niche={"render": {"grade": "warm"}},
        batch={}, per_platform={},
    )
    assert cfg["render"] == {"fps": 30, "grade": "warm"}
```

- [ ] **Step 2: Run → FAIL (`ModuleNotFoundError`).**

- [ ] **Step 3: Implement `shared/config.py`**

```python
from typing import Any


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_config(*, global_defaults: dict[str, Any], niche: dict[str, Any],
                   batch: dict[str, Any], per_platform: dict[str, Any]) -> dict[str, Any]:
    """Precedence: global -> niche -> batch -> per-platform (later wins)."""
    cfg: dict[str, Any] = {}
    for layer in (global_defaults, niche, batch, per_platform):
        cfg = _deep_merge(cfg, layer)
    return cfg
```

- [ ] **Step 4: Run → PASS (2). Commit.**

```bash
git add shared/config.py tests/test_config.py
git commit -m "feat: typed config resolver (global->niche->batch->platform, ADR 0010 D5)"
```

---

## Phase 4 — Adapter Protocols + fakes (ADR 0012 §8.4)

### Task 9: Adapter Protocols + types

ADR 0012 §6: typed `Protocol`/ABC stubs. `DistributionAdapter.publish/confirm_posted/allowed_visibility`; model backends `generate_image/img2vid/tts/llm/vlm_judge`; `LayoutEngine.render(render_manifest)`.

**Files:**
- Create: `shared/adapters/__init__.py`, `shared/adapters/types.py`, `shared/adapters/protocols.py`
- Test: `tests/test_adapters_fakes.py` (Protocol conformance asserted in Task 10)

- [ ] **Step 1: Write `shared/adapters/types.py`**

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Visibility(str, Enum):
    PRIVATE = "private"
    SELF_ONLY = "self_only"
    PUBLIC = "public"


@dataclass(frozen=True)
class PostMeta:
    title: str
    description: str
    hashtags: tuple[str, ...]
    visibility: Visibility


@dataclass(frozen=True)
class PostReceipt:
    video_id: str
    platform: str
    remote_post_id: str
    visibility: Visibility


@dataclass(frozen=True)
class Judgment:
    overall: float
    scores: dict[str, float]
    passed: bool
    observations: tuple[str, ...] = ()   # per-pass VLM observations (ADR 0016 D5); verdicts stay in the gates
```

- [ ] **Step 2: Write `shared/adapters/protocols.py`**

```python
from pathlib import Path
from typing import Protocol, runtime_checkable

from shared.adapters.types import Judgment, PostMeta, PostReceipt, Visibility


@runtime_checkable
class DistributionAdapter(Protocol):
    def publish(self, render: Path, meta: PostMeta) -> PostReceipt: ...
    def confirm_posted(self, video_id: str, platform: str) -> PostReceipt | None: ...
    def allowed_visibility(self, audit_state: str) -> set[Visibility]: ...


@runtime_checkable
class ModelBackend(Protocol):
    def generate_image(self, prompt: str, seed: int) -> Path: ...
    def img2vid(self, image: Path, seed: int) -> Path: ...
    def tts(self, text: str) -> Path: ...
    def llm(self, prompt: str, seed: int | None = None) -> str: ...   # seed -> reproducible best-of-N (ADR 0009)
    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment: ...
    def restore(self, frames: list[Path]) -> list[Path]: ...   # ESRGAN/RIFE/GFPGAN (01d, M2)


@runtime_checkable
class LayoutEngine(Protocol):
    def render(self, render_manifest: dict) -> list[Path]: ...
```

- [ ] **Step 3: Write `shared/adapters/__init__.py`** re-exporting the public names.

```python
from shared.adapters.protocols import DistributionAdapter, LayoutEngine, ModelBackend
from shared.adapters.types import Judgment, PostMeta, PostReceipt, Visibility

__all__ = ["DistributionAdapter", "LayoutEngine", "ModelBackend",
           "Judgment", "PostMeta", "PostReceipt", "Visibility"]
```

- [ ] **Step 4: Verify import**

Run: `uv run python -c "import shared.adapters; print(shared.adapters.__all__)"`
Expected: prints the list, exit 0.

- [ ] **Step 5: Commit**

```bash
git add shared/adapters/
git commit -m "feat: typed adapter Protocols + value types (ADR 0012 §6)"
```

### Task 10: Fixture-backed fakes keyed by `(capability, input_hash)`

ADR 0012 §7: a fake backend resolves a request to a fixture by `(capability, input_hash)` → a file under `tests/fixtures/backends/`.

**Files:**
- Create: `shared/adapters/fakes.py`
- Create: `tests/fixtures/backends/` (fixtures added per capability as needed)
- Test: `tests/test_adapters_fakes.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_adapters_fakes.py
from pathlib import Path
from shared.adapters import DistributionAdapter, ModelBackend, PostMeta, Visibility
from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter


def test_fake_backend_satisfies_protocol(tmp_path):
    be = FixtureBackend(fixtures_dir=tmp_path)
    assert isinstance(be, ModelBackend)


def test_fake_distribution_satisfies_protocol():
    assert isinstance(FixtureDistributionAdapter(), DistributionAdapter)


def test_llm_replays_fixture_by_capability_and_hash(tmp_path):
    (tmp_path / "llm").mkdir()
    # fixture filename is the input_hash of the prompt payload
    from shared.hashing import input_hash, sha256_bytes
    h = input_hash(declared_input_digests={"prompt": sha256_bytes(b"hi")},
                   resolved_config={}, stage_version="fake")
    (tmp_path / "llm" / f"{h}.txt").write_text("canned response")
    be = FixtureBackend(fixtures_dir=tmp_path)
    assert be.llm("hi") == "canned response"


def test_publish_confirm_roundtrip():
    ad = FixtureDistributionAdapter()
    meta = PostMeta(title="t", description="d", hashtags=(), visibility=Visibility.PUBLIC)
    rec = ad.publish(Path("/tmp/x.mp4"), meta)
    assert ad.confirm_posted(rec.video_id, rec.platform) == rec


def test_allowed_visibility_degrades_when_unaudited():
    ad = FixtureDistributionAdapter()
    assert Visibility.PUBLIC not in ad.allowed_visibility("unaudited")
    assert Visibility.PUBLIC in ad.allowed_visibility("audited")
```

- [ ] **Step 2: Run → FAIL (`ModuleNotFoundError: shared.adapters.fakes`).**

- [ ] **Step 3: Implement `shared/adapters/fakes.py`**

```python
from pathlib import Path

from shared.adapters.types import Judgment, PostMeta, PostReceipt, Visibility
from shared.hashing import input_hash, sha256_bytes


class FixtureBackend:
    """Replays canned outputs from fixtures_dir/<capability>/<input_hash>.<ext>."""

    def __init__(self, fixtures_dir: Path):
        self._dir = Path(fixtures_dir)

    def _hash(self, **named_bytes: bytes) -> str:
        return input_hash(
            declared_input_digests={k: sha256_bytes(v) for k, v in named_bytes.items()},
            resolved_config={}, stage_version="fake",
        )

    def _path(self, capability: str, h: str, ext: str) -> Path:
        return self._dir / capability / f"{h}.{ext}"

    def llm(self, prompt: str, seed: int | None = None) -> str:
        return self._path("llm", self._hash(prompt=prompt.encode()), "txt").read_text()

    def generate_image(self, prompt: str, seed: int) -> Path:
        return self._path("generate_image", self._hash(prompt=prompt.encode()), "png")

    def img2vid(self, image: Path, seed: int) -> Path:
        return self._path("img2vid", self._hash(image=Path(image).read_bytes()), "mp4")

    def tts(self, text: str) -> Path:
        return self._path("tts", self._hash(text=text.encode()), "wav")

    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment:
        return Judgment(overall=0.82, scores={"hook": 0.8, "coherence": 0.85}, passed=True)

    def restore(self, frames: list[Path]) -> list[Path]:
        return list(frames)  # fake: passthrough


class FixtureDistributionAdapter:
    """In-memory exactly-once fake: publish records intent->confirm; confirm replays it."""

    def __init__(self):
        self._posted: dict[tuple[str, str], PostReceipt] = {}
        self._counter = 0

    def publish(self, render: Path, meta: PostMeta) -> PostReceipt:
        self._counter += 1
        rec = PostReceipt(video_id="fin-0001", platform="youtube",
                          remote_post_id=f"fake_{self._counter}", visibility=meta.visibility)
        self._posted[(rec.video_id, rec.platform)] = rec
        return rec

    def confirm_posted(self, video_id: str, platform: str) -> PostReceipt | None:
        return self._posted.get((video_id, platform))

    def allowed_visibility(self, audit_state: str) -> set[Visibility]:
        if audit_state == "audited":
            return {Visibility.PRIVATE, Visibility.SELF_ONLY, Visibility.PUBLIC}
        return {Visibility.PRIVATE, Visibility.SELF_ONLY}
```

- [ ] **Step 4: Run → PASS (5). Commit.**

```bash
git add shared/adapters/fakes.py tests/test_adapters_fakes.py
git commit -m "feat: fixture-backed fakes (replay by capability+input_hash, ADR 0012 §7)"
```

---

## Phase 5 — Content-addressed cache (ADR 0012 §8.5)

### Task 11: File-based cache keyed `(stage, input_hash, seed)`

ADR 0010 D4 / ADR 0012 §1: re-running an unchanged stage is a hit; changing a declared input or the seed is a miss.

**Files:**
- Create: `shared/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cache.py
from shared.cache import StageCache
from shared.hashing import cache_key


def test_miss_then_hit(tmp_path):
    c = StageCache(root=tmp_path)
    k = cache_key("00b", "hashA", 7)
    assert c.get(k) is None
    c.put(k, {"script": "s.json"})
    assert c.get(k) == {"script": "s.json"}


def test_different_seed_is_a_miss(tmp_path):
    c = StageCache(root=tmp_path)
    c.put(cache_key("00b", "hashA", 7), {"script": "s.json"})
    assert c.get(cache_key("00b", "hashA", 8)) is None


def test_different_input_hash_is_a_miss(tmp_path):
    c = StageCache(root=tmp_path)
    c.put(cache_key("00b", "hashA", 7), {"script": "s.json"})
    assert c.get(cache_key("00b", "hashB", 7)) is None
```

- [ ] **Step 2: Run → FAIL (`ModuleNotFoundError`).**

- [ ] **Step 3: Implement `shared/cache.py`**

```python
import json
from pathlib import Path
from typing import Any


class StageCache:
    """Content-addressed cache: key (stage, input_hash, seed) -> recorded output map.

    File-backed: one JSON file per key under root/<stage>/<input_hash>-<seed>.json.
    Stores the declared-output path map produced by a stage so a hit skips recompute.
    """

    def __init__(self, root: Path):
        self._root = Path(root)

    def _path(self, key: tuple[str, str, int]) -> Path:
        stage, ih, seed = key
        return self._root / stage / f"{ih}-{seed}.json"

    def get(self, key: tuple[str, str, int]) -> dict[str, Any] | None:
        p = self._path(key)
        return json.loads(p.read_text()) if p.exists() else None

    def put(self, key: tuple[str, str, int], outputs: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(outputs))
        tmp.rename(p)  # atomic write (ADR 0003 D6)
```

- [ ] **Step 4: Run → PASS (3). Commit.**

```bash
git add shared/cache.py tests/test_cache.py
git commit -m "feat: file-based content-addressed stage cache (ADR 0012 §8.5)"
```

---

## Phase 6 — The offline DAG + CI (ADR 0012 §8.6)

### Task 12: Thin M0 stages (read → fake/transform → write) + the registry

In M0 each stage is thin: read declared inputs, call a fake backend or transform, write declared outputs, return `StageResult`. Implement all 15 stages following the worked `00b` example below. Each `stages/<id>/manifest.json` mirrors the `StageManifest` fields.

The DAG edges (from spec Ch.4) — each stage's declared inputs→outputs:

| id | inputs | outputs | compute | capability |
|---|---|---|---|---|
| 00a | (none) | data | cpu | — |
| 00b | data | script | cpu | llm |
| 01a | script | scenes_stock, provenance | cpu | — |
| 01b | script, scenes_stock | scenes_gen | gpu | generate_image |
| 01c | scenes_gen | scenes_motion | gpu | img2vid |
| 01d | scenes_motion | assets | gpu | restore |
| 01e | data, script | scenes_viz | cpu | — |
| 02 | script | narration | cpu | tts |
| 03 | script, narration | captions | cpu | — |
| 04 | script | music | cpu | — |
| 05 | script, assets, narration, captions, music | render | cpu | — |
| 05x | render, script | vision | gpu | vlm_judge |
| 05b | render, vision, script | qc | cpu | llm |
| 05c | render, vision, script | creative_qc | cpu | llm |
| 06 | render, qc, creative_qc, script | posts, feature_record | cpu | — |

- [ ] **Step 1: Write the worked `stages/s00b_script/stage.py`** (the pattern every stage follows)

```python
import json

from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


@stage(StageManifest(id="00b", inputs=["data"], outputs=["script"], compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    data = json.loads(ctx.read_input("data").read_text())
    # M0: the LLM backend is a fake replaying a fixture; real Qwen lands in M1.
    _ = ctx.backend("llm").llm(json.dumps({"data": data, "seed": ctx.seed}))
    # In M0 the canonical script is the golden fixture content the fake encodes.
    out = ctx.write_output("script")
    out.write_text(json.dumps(_canonical_script(data, ctx.seed)))
    ctx.log.info("script written", path=str(out))
    return StageResult(outputs={"script": out})


def _canonical_script(data: dict, seed: int) -> dict:
    # Minimal valid script.schema instance; M1 replaces with real generation.
    return {
        "schema_version": "1.0.0", "format": "ranked_list",
        "treatment": {"thesis": "t", "angle": "a", "tone": "measured",
                      "visual_motif": ["m"], "energy_curve": [0.3, 1.0]},
        "hook": {"spoken": "h", "on_screen_text": "h", "first_frame_visual": "card", "duration": 1.8},
        "narration_beats": [{"text": "n"}], "captions": [{"text": "c"}],
        "music": {"mood": "confident", "energy": "mid"},
        "platform_meta": {"youtube": {"title": "t", "description": "Not advice.", "hashtags": ["x"]}},
        "claims": [{"value": "7.2%", "source_ref": "data.cpi"}],
        "disclaimer": "Not financial advice.",
        "layout_data": {"kind": "ranked_list",
            "items": [{"rank": 1, "title": "ACME", "body": "b", "media_query": "q"}]},
    }
```

- [ ] **Step 2: Write `stages/s00b_script/manifest.json`**

```json
{"id": "00b", "inputs": ["data"], "outputs": ["script"], "compute": "cpu", "capability": "llm"}
```

- [ ] **Step 3: Implement the other 14 stages** following the same pattern — read declared inputs, produce a minimal schema-valid output (or pass through a fixture file for binary artifacts like `narration.wav`), write it, return `StageResult`. Each gets a `stage.py` + `manifest.json`. Stages whose output has a schema must write a schema-valid instance (reuse the golden fixtures as the canonical M0 output). `01a` also emits `provenance` and `06` also emits `feature_record` (so all 11 schemas are *produced* by the DAG, not only golden-validated — closes the ADR 0010 D6 "written from the first run" requirement).

- [ ] **Step 3b: Worked `stages/s06_distribute/stage.py`** — the acceptance-critical exactly-once `posts` record (ADR 0003 D1) gets a worked example, since it is the artifact acceptance #3 asserts:

```python
import json
from shared.ctx import StageContext, StageResult
from shared.adapters import PostMeta, Visibility
from shared.stage import StageManifest, stage


@stage(StageManifest(id="06", inputs=["render", "qc", "creative_qc", "script"],
                     outputs=["posts", "feature_record"], compute="cpu", capability="distribution"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    ad = ctx.backend("distribution")
    plat = ctx.job["platform_targets"][0]
    # exactly-once: confirm first; only publish if not already posted (ADR 0003 D1)
    receipt = ad.confirm_posted(ctx.job["video_id"], plat) or ad.publish(
        ctx.read_input("render"),
        PostMeta(title=script["platform_meta"][plat]["title"],
                 description=script["platform_meta"][plat]["description"],
                 hashtags=tuple(script["platform_meta"][plat]["hashtags"]),
                 visibility=Visibility.PRIVATE))
    posts = ctx.write_output("posts")
    posts.write_text(json.dumps({"schema_version": "1.0.0", "video_id": receipt.video_id,
                                 "platform": receipt.platform, "state": "confirmed",
                                 "visibility": receipt.visibility.value,
                                 "remote_post_id": receipt.remote_post_id,
                                 "timestamp": "2026-06-09T00:00:00Z"}))
    fr = ctx.write_output("feature_record")
    fr.write_text(json.dumps({"schema_version": "1.0.0", "video_id": receipt.video_id,
                              "format": script["format"], "seed": ctx.seed,
                              "hook_variant_id": "chosen", "judge_scores": {}, "metrics": {}}))
    return StageResult(outputs={"posts": posts, "feature_record": fr})
```

Its `stages/s06_distribute/manifest.json` **must mirror the `capability`** — a cpu stage does not auto-require one, so the drift-catcher's full `StageManifest` equality fails if it's omitted (same for any cpu stage carrying a capability, e.g. `00b`/`05b`/`05c` with `llm`):

```json
{"id": "06", "inputs": ["render", "qc", "creative_qc", "script"], "outputs": ["posts", "feature_record"], "compute": "cpu", "capability": "distribution"}
```

- [ ] **Step 4: Write `stages/registry.py`** importing every stage module so decorators register

```python
import importlib

_STAGE_MODULES = [
    "stages.s00a_research.stage", "stages.s00b_script.stage", "stages.s01a_stock.stage",
    "stages.s01b_imagegen.stage", "stages.s01c_img2vid.stage", "stages.s01d_upscale.stage",
    "stages.s01e_dataviz.stage", "stages.s02_voice.stage", "stages.s03_subs.stage",
    "stages.s04_music.stage", "stages.s05_render.stage", "stages.s05x_vision.stage",
    "stages.s05b_safety.stage", "stages.s05c_qc.stage", "stages.s06_distribute.stage",
]


def load_all():
    for m in _STAGE_MODULES:
        importlib.import_module(m)
```

- [ ] **Step 5: Update the drift-catcher test** to assert every `manifest.json` matches its registered `StageManifest`

Add to `tests/test_stage_manifests.py`:

```python
from pathlib import Path
from shared.stage import REGISTRY, load_manifest
from stages.registry import load_all

STAGES_DIR = Path(__file__).resolve().parents[1] / "stages"


def test_manifests_match_registered_stages():
    load_all()
    manifest_files = sorted(STAGES_DIR.glob("s*/manifest.json"))
    assert len(manifest_files) == 15
    for mf in manifest_files:
        m = load_manifest(mf)
        assert m.id in REGISTRY, f"{m.id} declared in {mf} but not registered"
        assert REGISTRY[m.id].manifest == m, f"manifest drift for {m.id}"
```

- [ ] **Step 6: Run → PASS. Commit.**

```bash
git add stages/ tests/test_stage_manifests.py
git commit -m "feat: thin M0 stages 00a-06 + registry + manifest drift-catcher (ADR 0012 §3)"
```

### Task 13: The `00a → 06` DAG runner + end-to-end test

> **This runner is the production conductor (ADR 0015), not test scaffolding.** The stage
> manifests it executes are the single source of orchestration truth; M4 hardens it (concurrency,
> lockfile, systemd timer) rather than replacing it with Argo YAML.

ADR 0012 acceptance #3: `pytest` runs all stages against fakes with no GPU, producing the golden `posts` record; #4: re-run is a cache hit; changing input/seed is a miss.

**Files:**
- Create: `shared/runner.py`
- Test: `tests/test_full_dag_offline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_full_dag_offline.py
import json
from shared.runner import run_dag
from shared.cache import StageCache


def test_full_dag_produces_posts_record(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    result = run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    posts = json.loads((run_dir / result["posts"]).read_text())
    assert posts["state"] == "confirmed"
    assert posts["platform"] in ("youtube", "tiktok")


def test_rerun_is_cache_hit(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    second = run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    assert second["cache_hits"] > 0


def test_seed_change_is_a_miss(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    third = run_dag(run_dir=run_dir, seed=8, cache=cache, fixtures_dir=_backend_fixtures())
    assert third["cache_hits"] == 0


def _backend_fixtures():
    from pathlib import Path
    return Path(__file__).parent / "fixtures" / "backends"
```

- [ ] **Step 2: Run → FAIL (`ModuleNotFoundError: shared.runner`).**

- [ ] **Step 3: Implement `shared/runner.py`** — topologically ordered execution against fakes, validating each schema-bearing output, with cache get/put per stage

```python
import json
from pathlib import Path

from shared.adapters.fakes import FixtureBackend, FixtureDistributionAdapter
from shared.cache import StageCache
from shared.config import resolve_config
from shared.ctx import Quarantined, StageContext, StageResult
from shared.hashing import cache_key, input_hash, sha256_bytes
from shared.schema import SchemaRegistry
from shared.stage import REGISTRY
from stages.registry import load_all

# linear M0 order (lane-fork parallelism is an orchestration concern, ADR 0011; semantics identical)
ORDER = ["00a", "00b", "01a", "01b", "01c", "01d", "01e",
         "02", "03", "04", "05", "05x", "05b", "05c", "06"]

# which declared outputs carry a schema (validated at the boundary)
OUTPUT_SCHEMA = {"data": None, "script": "script", "assets": "assets", "provenance": "provenance",
                 "vision": "vision", "qc": "qc", "creative_qc": "creative_qc", "posts": "posts",
                 "feature_record": "feature_record"}

REG = SchemaRegistry()


def run_dag(*, run_dir: Path, seed: int, cache: StageCache, fixtures_dir: Path) -> dict:
    load_all()
    backend = FixtureBackend(fixtures_dir=fixtures_dir)
    dist = FixtureDistributionAdapter()
    produced: dict[str, str] = {}  # declared name -> path relative to run_dir
    cache_hits = 0

    # seed job.json
    job = {"schema_version": "1.0.0", "batch_id": "b", "video_id": "fin-0001",
           "niche": "finance", "profile": "finance", "platform_targets": ["youtube"],
           "seed": seed, "stages": {}, "paths": {}}
    (run_dir / "job.json").write_text(json.dumps(job))

    for sid in ORDER:
        reg = REGISTRY[sid]
        m = reg.manifest
        input_paths = {name: produced[name] for name in m.inputs if name in produced}
        output_paths = {name: _default_path(name) for name in m.outputs}

        digests = {name: sha256_bytes((run_dir / p).read_bytes())
                   for name, p in input_paths.items()}
        # ADR 0012 §1: resolved_config is part of the hash; generative stages also fold
        # in model_id + graph_version so a model/graph bump is a miss (ADR 0010 D4).
        resolved = resolve_config(global_defaults={}, niche={}, batch={}, per_platform={})
        gen = {"model_id": "m0-fake", "graph_version": "m0"} if m.compute == "gpu" else {}
        ih = input_hash(declared_input_digests=digests, resolved_config=resolved,
                        stage_version="m0", **gen)
        key = cache_key(sid, ih, seed)

        hit = cache.get(key)
        if hit is not None:
            produced.update(hit)
            cache_hits += 1
            continue

        ctx = StageContext(stage=sid, run_dir=run_dir, seed=seed, job=job, config=resolved,
                           input_paths=input_paths, output_paths=output_paths,
                           backends={"llm": backend, "generate_image": backend,
                                     "img2vid": backend, "tts": backend, "vlm_judge": backend,
                                     "restore": backend, "distribution": dist})
        ctx.set_status("running")                       # ADR 0012 §4 status transitions
        try:
            res = reg.fn(ctx) or StageResult()
        except Quarantined:
            ctx.set_status("quarantined")
            raise
        for name in m.outputs:
            p = run_dir / output_paths[name]
            schema = OUTPUT_SCHEMA.get(name)
            if schema:
                REG.validate(schema, json.loads(p.read_text()))
            produced[name] = output_paths[name]
        cache.put(key, {name: output_paths[name] for name in m.outputs})
        ctx.set_status("done")

    return {"posts": produced["posts"], "cache_hits": cache_hits}


def _default_path(name: str) -> str:
    binary = {"narration": "narration.wav", "music": "music.wav", "render": "renders/youtube.mp4"}
    return binary.get(name, f"{name}.json")
```

> Note: stages that emit binary artifacts (`narration`, `music`, `render`, `scenes_*`) write placeholder files in M0; only schema-bearing outputs are validated. The fixture backend's `llm`/`tts`/etc. fixtures live under `tests/fixtures/backends/<capability>/`; add the few the chain needs.

- [ ] **Step 4: Run → PASS (3). If a fixture is missing, the error names the exact `(capability, input_hash)` path to add under `tests/fixtures/backends/`.**

Run: `uv run pytest tests/test_full_dag_offline.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add shared/runner.py tests/test_full_dag_offline.py tests/fixtures/backends/
git commit -m "feat: offline 00a-06 DAG runner against fakes (ADR 0012 acceptance #3/#4)"
```

### Task 14: The "no `platform ==` / `niche ==` branches" CI assertion

ADR 0010 D5 / ADR 0012 acceptance #5: a stage authored against the SDK needs zero `platform ==` / `niche ==` branches.

**Files:**
- Test: `tests/test_no_platform_branches.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_no_platform_branches.py
import re
from pathlib import Path

STAGES = Path(__file__).resolve().parents[1] / "stages"
# matches the resolver-bypass smell: platform == "...", niche != '...'.
# `in` is intentionally NOT matched: `for niche in niches` / `platform in targets` are legitimate.
BAD = re.compile(r"\b(platform|niche)\b\s*(==|!=)")


def test_no_stage_branches_on_platform_or_niche():
    offenders = []
    for f in STAGES.rglob("*.py"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if BAD.search(line) and "noqa: resolver" not in line:
                offenders.append(f"{f}:{i}: {line.strip()}")
    assert not offenders, "stages must resolve platform/niche via config, not branch:\n" + "\n".join(offenders)
```

- [ ] **Step 2: Run → PASS (stages are clean by construction).**

Run: `uv run pytest tests/test_no_platform_branches.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_no_platform_branches.py
git commit -m "test: assert no stage branches on platform/niche (ADR 0012 acceptance #5)"
```

### Task 15: CI workflow (GPU-less runner) + wire `make test`

ADR 0012 acceptance #3: CI is green on a GPU-less runner.

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `Makefile` (the `test:` target body)

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  push:
    branches: ["**"]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest   # GPU-less by design (ADR 0012)
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Sync deps
        run: uv sync
      - name: Run the full GPU-free suite
        run: uv run pytest -q
```

- [ ] **Step 2: Wire the `make test` target** — replace the `exit 1` stub

Edit `Makefile`, the `test:` target:

```make
test: ## schema validation + golden fixtures + GPU-free full-DAG run via shared/fakes (ADR 0010)
	@uv run pytest -q
```

- [ ] **Step 3: Run the whole suite locally**

Run: `uv run pytest -q`
Expected: PASS — all tests green, no GPU touched.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml Makefile
git commit -m "ci: GPU-less pytest workflow + wire make test (ADR 0012 acceptance #3)"
```

---

## M0 Acceptance Checklist (verbatim from ADR 0012 — the testable "done")

- [ ] Every schema has `schema_version`; the harness **rejects** a wrong-typed field, a missing required field, and a major-version mismatch → **Task 3**.
- [ ] The 11 schemas validate the golden-fixture chain end to end → **Task 5** (parametrized sweep).
- [ ] `pytest` runs all stages `00a → 06` against the fakes with no GPU, producing the golden `posts` record; CI green on a GPU-less runner → **Tasks 13, 15**.
- [ ] Re-running an unchanged stage is a cache hit; changing a declared input or seed is a miss → **Tasks 11, 13**.
- [ ] A stage needs zero `platform ==` / `niche ==` branches → **Task 14**.

---

## Self-Review

**Spec coverage:** Each ADR 0012 numbered primitive maps to a task — §1 input_hash→T1, §5 version→T2, §2 ctx→T6, §3 manifest→T7/T12, §6 Protocols→T9, §7 fakes→T10, §8.5 cache→T11; the 5 acceptance items map as listed above. ADR 0010 D5 config resolver→T8. The 11 schemas (Ch.5)→T3/T4/T5. `layout.schema.json` is explicitly deferred to M2/M3 (header decision) — consistent with Ch.10's 11-schema list.

**Placeholder scan:** No "TBD"/"add error handling" steps; every code step shows complete code. The one breadth step (T5 authoring 9 schemas, T12 implementing 14 stages) gives the explicit field/edge contract for each plus a fully-worked example to copy — concrete, not vague.

**Type consistency:** `StageContext`/`StageResult`/`StageManifest`/`SchemaRegistry`/`StageCache` names and signatures are identical across T6–T13. `input_hash(...)` keyword signature is the same in T1, T10, T13. `cache_key` returns the `(stage, input_hash, seed)` tuple used identically in T11/T13. Adapter Protocol method names (`publish`/`confirm_posted`/`allowed_visibility`, `llm`/`tts`/…) match between T9 (Protocol), T10 (fake), and T13 (runner backends map).

**Scope:** One milestone (M0), one acceptance gate, produces working testable software (the green GPU-free DAG). Not decomposed further — the 6 phases share types and must ship together to pass the gate.
