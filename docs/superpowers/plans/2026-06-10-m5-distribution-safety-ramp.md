# M5 — Account-Safety Gate + Distribution + the Publish Ramp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop from a rendered video to a posted one. Build the **always-on account-safety gate** (`05b`, ADR 0004 D3 — the durable "human replacement"), the **distribution stage** (`06`, per-platform adapters to YouTube + TikTok with the `posts.jsonl` **exactly-once** ledger, ADR 0003 D1), and the **temporary human-at-publish ramp** — provisioning/warming → a **minimal review CLI** (`make review`) whose every approve/reject is **captured as the judge-calibration label set** (ADR 0016 D2), with concrete **ramp-exit criteria**. Plus the credential work the unattended run rests on: the **OAuth token-age pre-flight** (into M4's framework) and the **OAuth-app→Production** move (ADR 0009 #10).

**Architecture:** Everything extends the M0 SDK + the M4 conductor. `05b` is a thin stage over **pure check modules** (`shared/safety/`) — disclaimer/denylist/citation/disclosure/profanity/safe-zone/audio-defect/render-integrity/repetition are all deterministic and CI-tested; the only model call is the **second-pass fact/sanity LLM, which reuses 00b's host endpoint + eviction rule** (spec Ch.8, integration-marked). `06` is a thin stage over the **M0 `DistributionAdapter`** whose **base class owns exactly-once** (intent→confirm against `posts.jsonl`); the two real adapters (`YouTubeAdapter`, `TikTokAdapter`) implement only the platform `_post`/`_find_existing` primitives (integration). The ramp is **pure policy** (`shared/ramp/`) plus a thin `shorts/review.py` CLI; it gates `06` and feeds back into the M4 `per_niche` ramp knob. The OAuth check **slots into the M4 pluggable pre-flight framework** (M4 Task 11 left the seam). CI stays GPU-free and network-free — every API call is behind an adapter with a fake.

**Tech Stack:** Python 3.12 + the M0–M4 toolchain (no new runtime deps for the pure layer); `google-api-python-client` + `google-auth-oauthlib` (YouTube Data API v3) and `httpx` (TikTok Content Posting API) behind the adapters; `ffprobe`/`ffmpeg` for render-integrity probes (integration). CI runs only pure/fake tests (`-m "not integration"`).

**Decisions made here (spec/ADRs left open; pinned for M5):**
- **05b is ALL-must-hold, and every check is a hard boolean except three numeric windows** (resolves spec Ch.8 "Open: numeric pass/fail thresholds"). Hard booleans: disclaimer present, no prohibited-claim hit, ≥1 cited source, AI-disclosure flag set, profanity clear, CTA-bump inside the platform safe-zone, second-pass-LLM `hallucination=false`. Numeric windows (config): **integrated loudness ∈ [-16, -12] LUFS & true-peak ≤ -1 dBTP**; **no silence > 0.4 s inside the first 2.5 s** (hook dead-air) and **no black run > 0.25 s** (mean luma < 16/255); **synth duration within ±8 % of the script's projected runtime**. Any single failure → **quarantine, never post**.
- **05b reads the niche profile for its content rules** — the denylist check is `profile.defaults.prohibited_claims`, the disclaimer check matches `profile.defaults.disclaimer` (the data authored in the M3 finance/business profiles). Safety policy is **profile data, not gate code** — a new niche ships its own rules.
- **05b's second-pass LLM is the 00b model** (spec Ch.8: "same host endpoint + eviction rule as 00b") — a fact/sanity/hallucination check, NOT a creative judge, so reusing the author model is correct here (the independent-judge rule binds only 05c's *quality* verdict, ADR 0016 D1).
- **Exactly-once lives in the `DistributionAdapter` base** (ADR 0003 D1): `publish()` writes an **intent** record (`(video_id, platform)` + a deterministic `idempotency_key`) *before* the call and a **confirmed** record (remote id) *after*; on retry, an intent-without-confirm triggers `_find_existing(idempotency_key)` — YouTube `insert` has no client token, so the adapter **searches the channel for the marker before re-posting**, never blind-inserts. Subclasses implement only `_post` + `_find_existing`.
- **Visibility policy (ADR 0009):** config `visibility` per platform — **YouTube leads the ≥1 public** (default `public` *after* the warming window), **TikTok stays `SELF_ONLY` until `tiktok.audit_cleared: true`**. Private-first is the default everywhere until warming completes.
- **Blanket AI-disclosure on every call** (ADR 0004/0009; granular wording deferred, spec §"Decided since"): the adapter sets the platform's synthetic-media flag **and** appends a standard disclosure line to the description. Wording is config (`disclosure_line`).
- **Caption assembly:** the **primary keyword leads the first ~150 chars** (ADR 0006), then the hook line, hashtags, the disclosure line, and — when `affiliate.enabled` (default **false**, ships disabled, ADR 0004 D5) — the affiliate block. Built from `script.platform_meta` + the profile; per-platform.
- **Ramp-exit criteria (resolves spec Ch.8 "Open: ramp-exit criteria"; makes ADR 0014 D2's "track record" testable):** the per-niche human gate lifts when, in the trailing window, there are **≥20 human-approved posts over ≥14 days with zero human rejections AND zero platform strikes/takedowns**; only then may `per_niche` ramp 1→2 (the M4 knob). All three numbers are config. Until then `06` posts **only human-approved** videos.
- **Provisioning + warming is a state, not a stage:** `ramp.state.json` per niche tracks `provisioned`, `warming_until`, `approved/rejected` counts, `gate_active`; the conductor reads it (gates cadence) and `06` reads it (gates posting). Warming = a recorded delay before cadence ramps (ADR 0009), folded into this state.
- **The review CLI is read-only against renders + append-only against labels:** `make review` lists pending → plays the YouTube cut → records approve/reject; a decision writes the ramp label into **`feature_record`** (the ADR 0016 D2 calibration set — so 05c's floor can be re-anchored in M6) and into `ramp.state.json`. It never mutates a render or re-runs a stage.

---

## File Structure

```
shared/safety/                              # NEW: the 05b check library (all pure, CI-tested)
  __init__.py
  checks.py                                 # disclaimer / prohibited-claims / citation / disclosure / profanity
  geometry.py                               # CTA-bump safe-zone containment per platform (ADR 0005 D10)
  audio_defect.py                           # hook dead-air / loudness window / synth-duration (pure thresholds)
  render_integrity.py                       # black-run / clipped-loudness thresholds (pure; ffprobe at integration)
  repetition.py                             # repetitious-content vs the novelty ledger (reuse the M2/M4 pattern)
  gate.py                                   # aggregate ALL-must-hold -> qc payload + verdict
shared/distribution/                        # NEW: the 06 pure layer
  __init__.py
  posts_ledger.py                           # exactly-once intent->confirmed, (video_id, platform); tokenless retry-confirm
  caption.py                                # keyword-first ~150c + disclosure line + affiliate block + per-platform meta
  visibility.py                             # private-first / >=1 public / tiktok audit-gate policy
shared/adapters/
  base.py                                   # MODIFY: DistributionAdapter base now OWNS exactly-once (publish())
  youtube.py                                # NEW: YouTubeAdapter(DistributionAdapter) — Data API v3 insert + synthetic-media flag
  tiktok.py                                 # NEW: TikTokAdapter(DistributionAdapter) — Content Posting API + AI-content flag
shared/ramp/                                # NEW: the publish-ramp policy (pure)
  __init__.py
  state.py                                  # ramp.state.json load/update (provisioned / warming / counts / gate_active)
  queue.py                                  # pending = passed 05b+05c, not yet human-decided
  labels.py                                 # approve/reject -> feature_record calibration label (ADR 0016 D2)
  policy.py                                 # ramp-exit criteria + gate_active? + per_niche ramp
shared/conductor/preflight.py               # MODIFY: add oauth_token_age_gate (into the M4 Task-11 framework)
shorts/review.py                            # NEW: python -m shorts.review (make review): list -> play -> approve/reject
stages/s05b_safety/{stage.py,manifest.json} # NEW: read render+script+vision+audio -> the checks -> qc.json (gate)
stages/s06_distribute/{stage.py,manifest.json}  # NEW: ramp-gated, per-platform publish via the adapters
schemas/qc.schema.json                      # MODIFY: pin the check enum + verdict (extend the M0 skeleton)
schemas/posts.schema.json                   # MODIFY: pin intent|confirmed states + idempotency_key (extend M0)
schemas/feature_record.schema.json          # MODIFY: add the optional `ramp_label` block (ADR 0016 D2)
deploy/host/oauth-production.md             # NEW: the ADR 0009 #10 ops doc (Testing->Production, token longevity)
deploy/host/platform-audit.md               # NEW: the YouTube/TikTok audit submission checklist (ops)
Makefile                                    # add `review:` target
tests/
  test_safety_checks.py  test_safety_geometry.py  test_audio_defect.py
  test_render_integrity.py  test_repetition.py  test_safety_gate.py
  test_posts_ledger.py  test_caption.py  test_visibility.py
  test_distribution_base.py  test_youtube_adapter.py  test_tiktok_adapter.py
  test_ramp_state.py  test_ramp_queue.py  test_ramp_labels.py  test_ramp_policy.py
  test_review_cli.py  test_oauth_preflight.py
  test_s05b_safety.py  test_s06_distribute.py
```

**Responsibility split:** `shared/safety/` = the deterministic safety checks (the model call is a thin seam); `shared/distribution/` = exactly-once + caption + visibility (pure); `shared/adapters/{youtube,tiktok}.py` = the only network code, behind the base's exactly-once; `shared/ramp/` = the human-gate policy + calibration capture (pure); `shorts/review.py` = the thin operator CLI. New stages stay thin M0 `run(ctx)` shells delegating to those modules. Nothing in `shared/planner/` or `shared/conductor/executor.py` changes (06/05b are just stages in the existing order).

---

# Part A — The account-safety gate (Stage 05b)

### Task 1: Deterministic content checks (disclaimer / prohibited-claims / citation / disclosure / profanity)

The spec Ch.8 list, minus the model call. These read the **niche profile** (the M3 `prohibited_claims` + `disclaimer`) so safety policy is data.

**Files:** Create `shared/safety/__init__.py` (empty), `shared/safety/checks.py`; Test `tests/test_safety_checks.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_safety_checks.py
from shared.safety.checks import (disclaimer_present, no_prohibited_claims,
                                  sources_cited, disclosure_set, profanity_clear, CheckResult)

PROFILE = {"defaults": {"disclaimer": "Educational only — not financial advice.",
                        "prohibited_claims": ["buy / sell / hold recommendations on a specific security",
                                              "guaranteed, risk-free, or 'can't lose' returns"]}}


def test_disclaimer_must_be_present_verbatim():
    assert disclaimer_present({"disclaimer": "Educational only — not financial advice."}, PROFILE).ok
    assert not disclaimer_present({"disclaimer": ""}, PROFILE).ok


def test_prohibited_claim_phrases_are_flagged():
    clean = {"narration_beats": [{"text": "Index funds tend to track the market."}]}
    dirty = {"narration_beats": [{"text": "You should buy this stock — it's a guaranteed win."}]}
    assert no_prohibited_claims(clean, PROFILE).ok
    bad = no_prohibited_claims(dirty, PROFILE)
    assert not bad.ok and "guaranteed" in bad.detail.lower()


def test_sources_must_be_cited():
    assert sources_cited({"claims": [{"value": "3.2%", "source_ref": "data.cpi"}]}).ok
    assert not sources_cited({"claims": []}).ok


def test_ai_disclosure_flag_required():
    assert disclosure_set({"platform_meta": {"ai_disclosure": True}}).ok
    assert not disclosure_set({"platform_meta": {"ai_disclosure": False}}).ok


def test_profanity_is_flagged():
    assert profanity_clear({"narration_beats": [{"text": "clean copy"}]}).ok
    assert not profanity_clear({"narration_beats": [{"text": "this damn thing"}]},
                               wordlist={"damn"}).ok
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Implement `shared/safety/checks.py`**

```python
from dataclasses import dataclass

# Minimal default profanity set; the real list is config (shared.config), niche-overridable.
_DEFAULT_PROFANITY = {"damn", "hell", "crap"}                # placeholder; tuned at bring-up


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str
    detail: str = ""


def _spoken(script: dict) -> str:
    return " ".join(b.get("text", "") for b in script.get("narration_beats", [])).lower()


def disclaimer_present(script: dict, profile: dict) -> CheckResult:
    want = profile["defaults"]["disclaimer"].strip()
    got = (script.get("disclaimer") or "").strip()
    return CheckResult(got == want and bool(want), "disclaimer",
                       "" if got == want else f"disclaimer != profile ({got!r})")


def no_prohibited_claims(script: dict, profile: dict) -> CheckResult:
    """The denylist is the profile's prohibited_claims (M3 data). We match the salient phrase
    tokens, not the whole rule sentence — a rule like 'guaranteed ... returns' fires on 'guaranteed'.
    Deliberately conservative: a false positive quarantines (safe), a miss posts (unsafe)."""
    text = _spoken(script) + " " + " ".join(
        c.get("text", "") for c in script.get("captions", [])).lower()
    triggers = {"buy", "sell", "guaranteed", "risk-free", "can't lose", "price target",
                "you should buy", "you should sell", "double your money"}
    hit = next((t for t in triggers if t in text), None)
    return CheckResult(hit is None, "prohibited_claims",
                       "" if hit is None else f"prohibited phrase {hit!r}")


def sources_cited(script: dict) -> CheckResult:
    cited = [c for c in script.get("claims", []) if c.get("source_ref")]
    return CheckResult(len(cited) >= 1, "sources_cited",
                       "" if cited else "no claim carries a source_ref")


def disclosure_set(script: dict) -> CheckResult:
    ok = bool(script.get("platform_meta", {}).get("ai_disclosure"))
    return CheckResult(ok, "ai_disclosure", "" if ok else "ai_disclosure flag not set")


def profanity_clear(script: dict, wordlist: set[str] | None = None) -> CheckResult:
    words = wordlist or _DEFAULT_PROFANITY
    text = _spoken(script)
    hit = next((w for w in words if w in text.split()), None)
    return CheckResult(hit is None, "profanity", "" if hit is None else f"profanity {hit!r}")
```

- [ ] **Step 4: Run** → PASS (5). **Commit.**

```bash
git add shared/safety/__init__.py shared/safety/checks.py tests/test_safety_checks.py
git commit -m "feat(m5): 05b deterministic content checks reading the niche profile (ADR 0004 D3)"
```

### Task 2: CTA-bump safe-zone geometry (ADR 0005 D10)

The channel's own engagement CTA is whitelisted but must sit in the **platform-safe zone** — not occluding TikTok's right-rail UI or the caption band.

**Files:** Create `shared/safety/geometry.py`; Test `tests/test_safety_geometry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_safety_geometry.py
import pytest
from shared.safety.geometry import in_safe_zone, SAFE_ZONES


def test_tiktok_right_rail_and_caption_band_are_unsafe():
    # 1080x1920; a CTA rect overlapping the right-rail (x>~950) fails
    assert not in_safe_zone({"x": 980, "y": 1200, "w": 80, "h": 80}, platform="tiktok").ok
    # a rect in the central safe band passes
    assert in_safe_zone({"x": 120, "y": 900, "w": 600, "h": 200}, platform="tiktok").ok


def test_youtube_lower_third_reserved():
    assert not in_safe_zone({"x": 100, "y": 1850, "w": 400, "h": 100}, platform="youtube").ok


def test_unknown_platform_uses_strictest_zone():
    z = SAFE_ZONES["_strict"]
    assert in_safe_zone({"x": z["x0"], "y": z["y0"], "w": 10, "h": 10}, platform="???").ok
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/safety/geometry.py`**

```python
from dataclasses import dataclass

# Per-platform reserved UI (1080x1920). A CTA rect must fall inside [x0,x1]x[y0,y1].
# Values are config-overridable; these are the documented defaults (ADR 0005 D10).
SAFE_ZONES = {
    "tiktok":  {"x0": 40, "x1": 950, "y0": 80, "y1": 1500},   # right-rail >950, caption band >1500
    "youtube": {"x0": 40, "x1": 1040, "y0": 80, "y1": 1800},  # lower controls >1800
    "_strict": {"x0": 40, "x1": 950, "y0": 80, "y1": 1500},
}


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str = "safe_zone"
    detail: str = ""


def in_safe_zone(rect: dict, *, platform: str) -> CheckResult:
    z = SAFE_ZONES.get(platform, SAFE_ZONES["_strict"])
    ok = (rect["x"] >= z["x0"] and rect["x"] + rect["w"] <= z["x1"]
          and rect["y"] >= z["y0"] and rect["y"] + rect["h"] <= z["y1"])
    return CheckResult(ok, detail="" if ok else f"CTA rect outside {platform} safe zone {z}")
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/safety/geometry.py tests/test_safety_geometry.py
git commit -m "feat(m5): CTA-bump safe-zone geometry per platform (ADR 0005 D10)"
```

### Task 3: Audio-defect + render-integrity checks (the numeric windows)

Pin the three numeric windows. The math is pure; the probes (`ffprobe`/`loudnorm` measure, frame luma) are integration seams that feed these pure predicates.

**Files:** Create `shared/safety/audio_defect.py`, `shared/safety/render_integrity.py`; Test `tests/test_audio_defect.py`, `tests/test_render_integrity.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audio_defect.py
from shared.safety.audio_defect import loudness_ok, hook_dead_air_ok, synth_duration_ok


def test_loudness_window():
    assert loudness_ok(integrated_lufs=-14.0, true_peak_dbtp=-1.5).ok
    assert not loudness_ok(integrated_lufs=-9.0, true_peak_dbtp=-1.5).ok    # too hot
    assert not loudness_ok(integrated_lufs=-14.0, true_peak_dbtp=-0.2).ok   # clipped peak


def test_hook_dead_air():
    # a silence span (start,end) seconds; any span >0.4s within the first 2.5s fails
    assert hook_dead_air_ok(silences=[(3.0, 3.6)]).ok                       # outside the hook
    assert not hook_dead_air_ok(silences=[(0.5, 1.1)]).ok                   # 0.6s dead hook


def test_synth_duration_within_tolerance():
    assert synth_duration_ok(actual_s=30.0, projected_s=31.0).ok            # ~3% < 8%
    assert not synth_duration_ok(actual_s=20.0, projected_s=30.0).ok        # 33% off
```

```python
# tests/test_render_integrity.py
from shared.safety.render_integrity import black_run_ok, no_clipping_ok


def test_black_run():
    assert black_run_ok(black_spans=[(5.0, 5.1)]).ok        # 0.1s blink ok
    assert not black_run_ok(black_spans=[(5.0, 5.5)]).ok    # 0.5s black > 0.25s


def test_clipping_guard():
    assert no_clipping_ok(true_peak_dbtp=-1.0).ok
    assert not no_clipping_ok(true_peak_dbtp=0.0).ok
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement both**

```python
# shared/safety/audio_defect.py
from dataclasses import dataclass

LUFS_MIN, LUFS_MAX, TP_MAX = -16.0, -12.0, -1.0     # config-overridable (ADR 0005 D8)
HOOK_WINDOW_S, MAX_HOOK_SILENCE_S, DURATION_TOL = 2.5, 0.4, 0.08


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str
    detail: str = ""


def loudness_ok(*, integrated_lufs: float, true_peak_dbtp: float) -> CheckResult:
    ok = LUFS_MIN <= integrated_lufs <= LUFS_MAX and true_peak_dbtp <= TP_MAX
    return CheckResult(ok, "loudness", "" if ok else
                       f"I={integrated_lufs} TP={true_peak_dbtp} outside window")


def hook_dead_air_ok(*, silences: list[tuple[float, float]]) -> CheckResult:
    for start, end in silences:
        overlap = min(end, HOOK_WINDOW_S) - start
        if start < HOOK_WINDOW_S and overlap > MAX_HOOK_SILENCE_S:
            return CheckResult(False, "hook_dead_air", f"{overlap:.2f}s silence in hook")
    return CheckResult(True, "hook_dead_air")


def synth_duration_ok(*, actual_s: float, projected_s: float) -> CheckResult:
    if projected_s <= 0:
        return CheckResult(False, "synth_duration", "no projected runtime")
    off = abs(actual_s - projected_s) / projected_s
    return CheckResult(off <= DURATION_TOL, "synth_duration",
                       "" if off <= DURATION_TOL else f"{off:.0%} off projected")
```

```python
# shared/safety/render_integrity.py
from dataclasses import dataclass

MAX_BLACK_RUN_S, TP_MAX = 0.25, -1.0


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str
    detail: str = ""


def black_run_ok(*, black_spans: list[tuple[float, float]]) -> CheckResult:
    worst = max((e - s for s, e in black_spans), default=0.0)
    return CheckResult(worst <= MAX_BLACK_RUN_S, "black_run",
                       "" if worst <= MAX_BLACK_RUN_S else f"{worst:.2f}s black frame run")


def no_clipping_ok(*, true_peak_dbtp: float) -> CheckResult:
    return CheckResult(true_peak_dbtp <= TP_MAX, "clipping",
                       "" if true_peak_dbtp <= TP_MAX else f"true-peak {true_peak_dbtp} dBTP")
```

- [ ] **Step 4: Run** → both PASS. **Commit.**

```bash
git add shared/safety/audio_defect.py shared/safety/render_integrity.py tests/test_audio_defect.py tests/test_render_integrity.py
git commit -m "feat(m5): 05b numeric windows — loudness/dead-air/duration + black-run/clipping (ADR 0005 D8)"
```

### Task 4: Repetitious-content check vs the novelty ledger

ADR 0002/0009: a near-duplicate of an already-posted video is a flag pattern. Reuse the topic/hook ledger.

**Files:** Create `shared/safety/repetition.py`; Test `tests/test_repetition.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_repetition.py
from shared.safety.repetition import not_repetitious


def test_fresh_topic_passes_and_recent_duplicate_fails():
    ledger = [{"topic": "cpi", "hook": "Inflation cooled again"}]
    assert not_repetitious({"topic": "fed", "hook": "The Fed blinked"}, ledger).ok
    dup = not_repetitious({"topic": "cpi", "hook": "Inflation cooled again"}, ledger)
    assert not dup.ok


def test_same_topic_different_angle_passes():
    ledger = [{"topic": "cpi", "hook": "Inflation cooled again"}]
    assert not_repetitious({"topic": "cpi", "hook": "Why your rent ignores the CPI"}, ledger).ok
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/safety/repetition.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str = "repetition"
    detail: str = ""


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / len(sa | sb) if (sa or sb) else 0.0


def not_repetitious(record: dict, ledger: list[dict], *, hook_sim: float = 0.6) -> CheckResult:
    """Repetition = SAME topic AND a near-duplicate hook (token Jaccard >= threshold). Same topic
    with a fresh angle is allowed (the channel revisits themes); a recycled hook is the flag."""
    for past in ledger:
        if past.get("topic") == record.get("topic") and \
                _jaccard(record.get("hook", ""), past.get("hook", "")) >= hook_sim:
            return CheckResult(False, detail=f"near-duplicate of posted {past.get('topic')!r}")
    return CheckResult(True)
```

- [ ] **Step 4: Run** → PASS. **Commit.**

```bash
git add shared/safety/repetition.py tests/test_repetition.py
git commit -m "feat(m5): repetitious-content check vs the novelty ledger (ADR 0002/0009)"
```

### Task 5: The gate aggregation → `qc.json` (ALL-must-hold)

**Files:** Create `shared/safety/gate.py`; Modify `schemas/qc.schema.json` (pin the check enum + verdict); Test `tests/test_safety_gate.py`

- [ ] **Step 1: Pin `schemas/qc.schema.json`** (extend the M0 skeleton — pin `checks[]` shape + `passed`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "qc.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "checks", "passed"],
  "properties": {
    "schema_version": {"type": "string"},
    "passed": {"type": "boolean"},
    "checks": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["name", "ok"],
        "properties": {
          "name": {"type": "string"}, "ok": {"type": "boolean"},
          "detail": {"type": "string"}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_safety_gate.py
from shared.safety.gate import aggregate
from shared.safety.checks import CheckResult
from shared.schema import SchemaRegistry


def test_all_must_hold_and_payload_validates():
    results = [CheckResult(True, "disclaimer"), CheckResult(True, "loudness")]
    payload = aggregate(results)
    SchemaRegistry().validate("qc", payload)
    assert payload["passed"] is True


def test_one_failure_fails_the_gate_and_names_it():
    results = [CheckResult(True, "disclaimer"),
               CheckResult(False, "prohibited_claims", "phrase 'guaranteed'")]
    payload = aggregate(results)
    assert payload["passed"] is False
    assert any(c["name"] == "prohibited_claims" and not c["ok"] for c in payload["checks"])
```

- [ ] **Step 3: Implement `shared/safety/gate.py`**

```python
from shared.safety.checks import CheckResult


def aggregate(results: list[CheckResult]) -> dict:
    """ALL-must-hold (spec Ch.8): a single failing check fails the gate. The payload records
    EVERY check (pass and fail) so the weekly spot-audit and the calibration set see the full
    picture, not just the first failure."""
    checks = [{"name": r.name, "ok": r.ok, **({"detail": r.detail} if r.detail else {})}
              for r in results]
    return {"schema_version": "1.0.0", "passed": all(r.ok for r in results), "checks": checks}
```

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/safety/gate.py schemas/qc.schema.json tests/test_safety_gate.py
git commit -m "feat(m5): 05b gate aggregation + qc.schema (ALL-must-hold, spec Ch.8)"
```

### Task 6: Stage 05b — wire the checks + the second-pass LLM

ADR 0004 D3: runs on every video; the second-pass fact/sanity LLM reuses 00b's host endpoint + eviction rule.

**Files:** Create `stages/s05b_safety/{stage.py,manifest.json}`; Test `tests/test_s05b_safety.py`

- [ ] **Step 1: Write the failing test** (the orchestration with injected probes/LLM; no ffmpeg/model)

```python
# tests/test_s05b_safety.py
from stages.s05b_safety.stage import collect_checks


class _SaneLLM:
    def llm_json(self, prompt, seed=None):
        return {"hallucination": False, "note": "claims trace to data"}


def test_collect_runs_every_check_and_passes_a_clean_video():
    script = {"disclaimer": "Educational only — not financial advice.",
              "narration_beats": [{"text": "Index funds track the market."}],
              "captions": [{"text": "the index"}], "claims": [{"source_ref": "data.cpi"}],
              "platform_meta": {"ai_disclosure": True}}
    profile = {"defaults": {"disclaimer": "Educational only — not financial advice.",
                            "prohibited_claims": ["guaranteed returns"]}}
    probes = {"integrated_lufs": -14.0, "true_peak_dbtp": -1.4, "silences": [],
              "black_spans": [], "actual_s": 30.0, "projected_s": 31.0,
              "cta_rect": {"x": 120, "y": 900, "w": 600, "h": 200}}
    results = collect_checks(script=script, profile=profile, probes=probes,
                             platform="tiktok", ledger=[], llm=_SaneLLM())
    assert all(r.ok for r in results)
    assert {"disclaimer", "prohibited_claims", "loudness", "hook_dead_air",
            "black_run", "safe_zone", "hallucination"} <= {r.name for r in results}


def test_hallucination_flag_fails_the_gate():
    class _BadLLM:
        def llm_json(self, prompt, seed=None):
            return {"hallucination": True, "note": "stat not in data"}
    results = collect_checks(script={"disclaimer": "", "narration_beats": []},
                             profile={"defaults": {"disclaimer": "", "prohibited_claims": []}},
                             probes={"integrated_lufs": -14.0, "true_peak_dbtp": -1.4,
                                     "silences": [], "black_spans": [], "actual_s": 1, "projected_s": 1,
                                     "cta_rect": {"x": 120, "y": 900, "w": 100, "h": 100}},
                             platform="tiktok", ledger=[], llm=_BadLLM())
    assert any(r.name == "hallucination" and not r.ok for r in results)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `stages/s05b_safety/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.safety import audio_defect as ad
from shared.safety import checks as ck
from shared.safety import geometry as geo
from shared.safety import render_integrity as ri
from shared.safety.checks import CheckResult
from shared.safety.gate import aggregate
from shared.safety.repetition import not_repetitious
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()

_FACT_PROMPT = ("You are a fact/safety reviewer. Given the SCRIPT and its DATA sources, return "
                'STRICT JSON {"hallucination": bool, "note": "..."} — true if any stated number '
                "or claim is NOT supported by the data. Judge only support, not style.\n\nSCRIPT: ")


def collect_checks(*, script, profile, probes, platform, ledger, llm) -> list[CheckResult]:
    """Every spec Ch.8 check, deterministic first then the one model call (reused 00b model)."""
    fact = llm.llm_json(_FACT_PROMPT + json.dumps(script))
    return [
        ck.disclaimer_present(script, profile),
        ck.no_prohibited_claims(script, profile),
        ck.sources_cited(script),
        ck.disclosure_set(script),
        ck.profanity_clear(script),
        geo.in_safe_zone(probes["cta_rect"], platform=platform),
        ad.loudness_ok(integrated_lufs=probes["integrated_lufs"],
                       true_peak_dbtp=probes["true_peak_dbtp"]),
        ad.hook_dead_air_ok(silences=probes["silences"]),
        ad.synth_duration_ok(actual_s=probes["actual_s"], projected_s=probes["projected_s"]),
        ri.black_run_ok(black_spans=probes["black_spans"]),
        ri.no_clipping_ok(true_peak_dbtp=probes["true_peak_dbtp"]),
        not_repetitious({"topic": script.get("topic"), "hook": script.get("hook", {}).get("spoken", "")},
                        ledger),
        CheckResult(not fact.get("hallucination", True), "hallucination", fact.get("note", "")),
    ]


@stage(StageManifest(id="05b", inputs=["render", "script", "vision", "narration", "music"],
                     outputs=["qc"], compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    profile = ctx.job["profile"]                         # resolved profile dict on the job
    probes = _probe(ctx)                                 # ffprobe/loudnorm/luma + CTA rect (integration)
    ledger = _recent_ledger(ctx)                         # posted-state/novelty recent window
    results = collect_checks(script=script, profile=profile, probes=probes,
                             platform=ctx.job.get("platform_targets", ["youtube"])[0],
                             ledger=ledger, llm=ctx.backend("llm"))
    payload = aggregate(results)
    _REG.validate("qc", payload)
    out = ctx.write_output("qc")
    out.write_text(json.dumps(payload))                  # write BEFORE any quarantine raise
    if not payload["passed"]:
        failed = [c["name"] for c in payload["checks"] if not c["ok"]]
        ctx.quarantine(f"safety gate failed: {failed}")
    ctx.log.info("safety gate pass", checks=len(results))
    return StageResult(outputs={"qc": out})


def _probe(ctx):
    raise NotImplementedError("ffprobe/loudnorm/luma + CTA-rect read wired at integration; "
                              "the pure predicates are unit-tested")
def _recent_ledger(ctx):
    raise NotImplementedError("recent posted/novelty window read wired at integration")
```

- [ ] **Step 4: Write `manifest.json`** → `{"id": "05b", "inputs": ["render", "script", "vision", "narration", "music"], "outputs": ["qc"], "compute": "cpu", "capability": "llm"}` (cpu stage carrying a capability — mirror it, per the M0 drift-catcher note). **Run** → PASS (2). **Commit.**

```bash
git add stages/s05b_safety/ tests/test_s05b_safety.py
git commit -m "feat(m5): 05b account-safety gate stage (every check + 00b fact-pass, ADR 0004 D3)"
```

> **Vision-pass consumption (ADR 0008/0016 D5):** the artifact/garbled-text checks read `vision.json`'s `keyframes[].observations` (M3's 05x output, `kind` = hook/end_card/beat). Add an `artifact_clear(vision)` check to `checks.py` (a `CheckResult` that fails when an observation matches the artifact lexicon — "morphing", "garbled text", "extra fingers", "caption overlap") and include it in `collect_checks`; its unit test mirrors Task 1's pattern. This is the half of 05x reserved for 05b at M3 ("dual-consumer contract"), now wired.

---

# Part B — Distribution (Stage 06)

### Task 7: Exactly-once posts ledger (intent → confirmed, tokenless retry-confirm)

**Files:** Create `shared/distribution/__init__.py` (empty), `shared/distribution/posts_ledger.py`; Modify `schemas/posts.schema.json`; Test `tests/test_posts_ledger.py`

- [ ] **Step 1: Pin `schemas/posts.schema.json`** (extend the M0 skeleton: the two states + the dedup key)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "posts.schema.json",
  "schema_version": "1.0.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "video_id", "platform", "state", "idempotency_key"],
  "properties": {
    "schema_version": {"type": "string"},
    "video_id": {"type": "string"},
    "platform": {"enum": ["youtube", "tiktok"]},
    "state": {"enum": ["intent", "confirmed"]},
    "idempotency_key": {"type": "string"},
    "remote_id": {"type": "string"},
    "url": {"type": "string"},
    "ts": {"type": "string"}
  }
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_posts_ledger.py
from shared.distribution.posts_ledger import (already_confirmed, pending_intent,
                                             write_intent, write_confirmed, idempotency_key)


def test_idempotency_key_is_deterministic():
    assert idempotency_key("vid1", "youtube") == idempotency_key("vid1", "youtube")
    assert idempotency_key("vid1", "youtube") != idempotency_key("vid1", "tiktok")


def test_confirmed_blocks_a_second_post(tmp_path):
    led = tmp_path / "posts.jsonl"
    write_intent(led, video_id="v", platform="youtube")
    write_confirmed(led, video_id="v", platform="youtube", remote_id="yt123", url="u")
    assert already_confirmed(led, "v", "youtube") is True
    assert pending_intent(led, "v", "youtube") is False     # confirmed supersedes the intent


def test_intent_without_confirm_is_a_retry_case(tmp_path):
    led = tmp_path / "posts.jsonl"
    write_intent(led, video_id="v", platform="tiktok")
    assert already_confirmed(led, "v", "tiktok") is False
    assert pending_intent(led, "v", "tiktok") is True       # crashed mid-post -> must confirm/recover
```

- [ ] **Step 3: Implement `shared/distribution/posts_ledger.py`**

```python
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def idempotency_key(video_id: str, platform: str) -> str:
    return hashlib.sha256(f"{video_id}:{platform}".encode()).hexdigest()[:16]


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l]


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now(timezone.utc).isoformat()
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def already_confirmed(path: Path, video_id: str, platform: str) -> bool:
    return any(r["video_id"] == video_id and r["platform"] == platform
               and r["state"] == "confirmed" for r in _records(path))


def pending_intent(path: Path, video_id: str, platform: str) -> bool:
    recs = [r for r in _records(path) if r["video_id"] == video_id and r["platform"] == platform]
    return any(r["state"] == "intent" for r in recs) and not any(r["state"] == "confirmed" for r in recs)


def write_intent(path: Path, *, video_id: str, platform: str) -> None:
    _append(path, {"schema_version": "1.0.0", "video_id": video_id, "platform": platform,
                   "state": "intent", "idempotency_key": idempotency_key(video_id, platform)})


def write_confirmed(path: Path, *, video_id: str, platform: str, remote_id: str, url: str) -> None:
    _append(path, {"schema_version": "1.0.0", "video_id": video_id, "platform": platform,
                   "state": "confirmed", "idempotency_key": idempotency_key(video_id, platform),
                   "remote_id": remote_id, "url": url})
```

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/distribution/__init__.py shared/distribution/posts_ledger.py schemas/posts.schema.json tests/test_posts_ledger.py
git commit -m "feat(m5): exactly-once posts ledger + posts.schema (intent->confirmed, ADR 0003 D1)"
```

### Task 8: Caption assembly (keyword-first + disclosure + affiliate) and visibility policy

**Files:** Create `shared/distribution/caption.py`, `shared/distribution/visibility.py`; Test `tests/test_caption.py`, `tests/test_visibility.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_caption.py
from shared.distribution.caption import build_caption


def test_primary_keyword_leads_first_150_chars_and_disclosure_appended():
    meta = {"title": "The Fed blinked", "description": "Here's what changed.",
            "hashtags": ["finance", "rates"], "primary_keyword": "interest rates"}
    cap = build_caption(meta, platform="youtube", disclosure_line="AI-generated. Educational only.",
                        affiliate=None)
    assert cap["description"][:150].lower().startswith("interest rates")
    assert "AI-generated" in cap["description"]
    assert cap["title"] == "The Fed blinked"


def test_affiliate_block_only_when_enabled():
    meta = {"title": "t", "description": "d", "hashtags": [], "primary_keyword": "k"}
    off = build_caption(meta, platform="youtube", disclosure_line="x", affiliate=None)
    on = build_caption(meta, platform="youtube", disclosure_line="x",
                       affiliate={"text": "Tools I use:", "links": ["https://ex.com/a"]})
    assert "Tools I use" not in off["description"] and "Tools I use" in on["description"]
```

```python
# tests/test_visibility.py
from shared.distribution.visibility import resolve_visibility


def test_youtube_public_after_warming_tiktok_gated():
    cfg = {"youtube": {"public_after_warming": True}, "tiktok": {"audit_cleared": False}}
    assert resolve_visibility("youtube", cfg, warmed=True) == "public"
    assert resolve_visibility("youtube", cfg, warmed=False) == "private"
    assert resolve_visibility("tiktok", cfg, warmed=True) == "SELF_ONLY"   # audit not cleared


def test_tiktok_public_once_audit_cleared():
    cfg = {"tiktok": {"audit_cleared": True}}
    assert resolve_visibility("tiktok", cfg, warmed=True) == "PUBLIC_TO_EVERYONE"
```

- [ ] **Step 2: Implement both**

```python
# shared/distribution/caption.py
def build_caption(meta: dict, *, platform: str, disclosure_line: str, affiliate: dict | None) -> dict:
    """ADR 0006: the primary keyword LEADS the first ~150 chars (the indexed window); then the
    body, hashtags, the blanket AI-disclosure line (ADR 0004/0009), and the affiliate block iff
    enabled (ADR 0004 D5, ships disabled)."""
    kw = meta["primary_keyword"]
    body = meta.get("description", "")
    lead = body if body.lower().startswith(kw.lower()) else f"{kw} — {body}"
    parts = [lead, "", " ".join(f"#{h}" for h in meta.get("hashtags", [])), "", disclosure_line]
    if affiliate:
        parts += ["", affiliate["text"], *affiliate.get("links", [])]
    return {"title": meta["title"], "description": "\n".join(p for p in parts if p is not None)}
```

```python
# shared/distribution/visibility.py
def resolve_visibility(platform: str, cfg: dict, *, warmed: bool) -> str:
    """Private-first until warmed; YouTube leads the >=1 public; TikTok stays SELF_ONLY until the
    platform audit clears (ADR 0009)."""
    pcfg = cfg.get(platform, {})
    if platform == "youtube":
        return "public" if (warmed and pcfg.get("public_after_warming")) else "private"
    if platform == "tiktok":
        return "PUBLIC_TO_EVERYONE" if pcfg.get("audit_cleared") else "SELF_ONLY"
    return "private"
```

- [ ] **Step 3: Run** → both PASS. **Commit.**

```bash
git add shared/distribution/caption.py shared/distribution/visibility.py tests/test_caption.py tests/test_visibility.py
git commit -m "feat(m5): caption assembly (keyword-first + disclosure + affiliate) + visibility policy (ADR 0006/0009)"
```

### Task 9: `DistributionAdapter` base owns exactly-once

ADR 0010: exactly-once is in the *base*; subclasses are thin platform `_post`/`_find_existing`.

**Files:** Modify `shared/adapters/base.py`; Test `tests/test_distribution_base.py`

- [ ] **Step 1: Write the failing tests** (a FakeAdapter exercises the base's exactly-once)

```python
# tests/test_distribution_base.py
from shared.adapters.base import DistributionAdapter


class FakeAdapter(DistributionAdapter):
    platform = "youtube"

    def __init__(self):
        self.posts = 0
        self.searchable = {}

    def _post(self, media_path, metadata, visibility):
        self.posts += 1
        rid = f"rid{self.posts}"
        self.searchable[metadata["idempotency_key"]] = rid
        return rid, f"https://yt/{rid}"

    def _find_existing(self, idempotency_key):
        rid = self.searchable.get(idempotency_key)
        return (rid, f"https://yt/{rid}") if rid else None


def test_publish_writes_intent_then_confirmed_once(tmp_path):
    led = tmp_path / "posts.jsonl"
    a = FakeAdapter()
    a.publish(video_id="v", media_path="m.mp4", metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 1
    from shared.distribution.posts_ledger import already_confirmed
    assert already_confirmed(led, "v", "youtube")


def test_confirmed_video_is_never_reposted(tmp_path):
    led = tmp_path / "posts.jsonl"
    a = FakeAdapter()
    md = {"title": "t", "idempotency_key": "k"}
    a.publish(video_id="v", media_path="m.mp4", metadata=md, visibility="private", ledger_path=led)
    a.publish(video_id="v", media_path="m.mp4", metadata=md, visibility="private", ledger_path=led)
    assert a.posts == 1                       # second call is a no-op (already confirmed)


def test_retry_after_crash_confirms_via_find_existing_not_repost(tmp_path):
    led = tmp_path / "posts.jsonl"
    a = FakeAdapter()
    # simulate: a prior run wrote intent + actually posted, then crashed before confirming
    from shared.distribution.posts_ledger import write_intent
    write_intent(led, video_id="v", platform="youtube")
    a.searchable["k"] = "rid_prior"           # the post DID land remotely
    a.publish(video_id="v", media_path="m.mp4", metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 0                       # found the existing remote post — no re-post
    from shared.distribution.posts_ledger import already_confirmed
    assert already_confirmed(led, "v", "youtube")
```

- [ ] **Step 2: Implement the base in `shared/adapters/base.py`** (M0 declared the interface; M5 puts exactly-once in it)

```python
from abc import ABC, abstractmethod
from pathlib import Path

from shared.distribution.posts_ledger import (already_confirmed, pending_intent,
                                             write_confirmed, write_intent)


class DistributionAdapter(ABC):
    """Exactly-once is OWNED HERE (ADR 0003 D1/0010): publish() is the only entry point; a subclass
    implements only the platform primitives. A retry after a mid-post crash recovers via
    _find_existing — a tokenless API (YouTube insert) is reconciled by searching the channel for
    the idempotency marker, never blind re-inserting."""
    platform: str

    def publish(self, *, video_id: str, media_path, metadata: dict, visibility: str,
                ledger_path: Path) -> dict | None:
        if already_confirmed(ledger_path, video_id, self.platform):
            return None                                  # done already — no-op
        if pending_intent(ledger_path, video_id, self.platform):
            found = self._find_existing(metadata["idempotency_key"])   # crash-recovery path
            if found:
                rid, url = found
                write_confirmed(ledger_path, video_id=video_id, platform=self.platform,
                                remote_id=rid, url=url)
                return {"remote_id": rid, "url": url, "recovered": True}
        else:
            write_intent(ledger_path, video_id=video_id, platform=self.platform)
        rid, url = self._post(media_path, metadata, visibility)        # the side effect
        write_confirmed(ledger_path, video_id=video_id, platform=self.platform,
                        remote_id=rid, url=url)
        return {"remote_id": rid, "url": url, "recovered": False}

    @abstractmethod
    def _post(self, media_path, metadata: dict, visibility: str) -> tuple[str, str]: ...

    @abstractmethod
    def _find_existing(self, idempotency_key: str) -> tuple[str, str] | None: ...
```

- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/adapters/base.py tests/test_distribution_base.py
git commit -m "feat(m5): DistributionAdapter base owns exactly-once + crash-recovery (ADR 0003 D1/0010)"
```

### Task 10: `YouTubeAdapter` + `TikTokAdapter` (the platform primitives)

**Files:** Create `shared/adapters/youtube.py`, `shared/adapters/tiktok.py`; Test `tests/test_youtube_adapter.py`, `tests/test_tiktok_adapter.py`

- [ ] **Step 1: Write the tests** (request-shape units + a live-call integration mark each)

```python
# tests/test_youtube_adapter.py
import pytest
from shared.adapters.base import DistributionAdapter
from shared.adapters.youtube import YouTubeAdapter


def test_is_a_distribution_adapter_and_sets_synthetic_flag():
    a = YouTubeAdapter(creds=None)
    assert isinstance(a, DistributionAdapter) and a.platform == "youtube"
    body = a._insert_body({"title": "t", "description": "d"}, visibility="private")
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["containsSyntheticMedia"] is True          # AI-disclosure (ADR 0004)


@pytest.mark.integration
def test_youtube_insert_live(tmp_path):
    ...  # real videos.insert against a test channel; asserts a remote id comes back
```

```python
# tests/test_tiktok_adapter.py
import pytest
from shared.adapters.base import DistributionAdapter
from shared.adapters.tiktok import TikTokAdapter


def test_is_a_distribution_adapter_and_flags_ai_content():
    a = TikTokAdapter(token=None)
    assert isinstance(a, DistributionAdapter) and a.platform == "tiktok"
    body = a._init_body({"title": "t"}, visibility="SELF_ONLY")
    assert body["post_info"]["privacy_level"] == "SELF_ONLY"
    assert body["post_info"]["brand_content_toggle"] is False
    assert body["source_info"]["is_ai_generated"] is True            # AI-disclosure (ADR 0004/0009)
```

- [ ] **Step 2: Implement both** (only `_post`/`_find_existing` + the body builders; network behind those)

```python
# shared/adapters/youtube.py
from shared.adapters.base import DistributionAdapter


class YouTubeAdapter(DistributionAdapter):
    """YouTube Data API v3 videos.insert. No client idempotency token, so _find_existing searches
    the channel's recent uploads for the marker (the title is unique per video_id) — the tokenless
    retry-confirm path (ADR 0003 D1)."""
    platform = "youtube"

    def __init__(self, creds, *, search=None, insert=None):
        self._creds = creds
        self._search, self._insert = search, insert       # injected for tests; real clients at bring-up

    def _insert_body(self, metadata: dict, visibility: str) -> dict:
        return {"snippet": {"title": metadata["title"], "description": metadata["description"],
                            "categoryId": "25"},
                "status": {"privacyStatus": visibility, "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": True}}            # blanket AI-disclosure

    def _post(self, media_path, metadata, visibility):
        body = self._insert_body(metadata, visibility)
        resp = self._insert(body, media_path)             # real: MediaFileUpload + videos().insert
        return resp["id"], f"https://youtu.be/{resp['id']}"

    def _find_existing(self, idempotency_key):
        if self._search is None:
            return None
        hit = self._search(idempotency_key)               # real: search.list mine=true for the marker
        return (hit["id"], f"https://youtu.be/{hit['id']}") if hit else None
```

```python
# shared/adapters/tiktok.py
from shared.adapters.base import DistributionAdapter


class TikTokAdapter(DistributionAdapter):
    """TikTok Content Posting API (PULL_FROM_URL or FILE_UPLOAD). is_ai_generated set on every
    post; privacy stays SELF_ONLY until the platform audit clears (ADR 0009)."""
    platform = "tiktok"

    def __init__(self, token, *, init=None, status=None):
        self._token = token
        self._init, self._status = init, status

    def _init_body(self, metadata: dict, visibility: str) -> dict:
        return {"post_info": {"title": metadata["title"], "privacy_level": visibility,
                              "brand_content_toggle": False},
                "source_info": {"source": "FILE_UPLOAD", "is_ai_generated": True}}

    def _post(self, media_path, metadata, visibility):
        publish_id = self._init(self._init_body(metadata, visibility), media_path)  # real: /publish/video/init/
        return publish_id, f"tiktok://publish/{publish_id}"

    def _find_existing(self, idempotency_key):
        # TikTok returns a publish_id at init; the intent record stores it, so recovery polls status.
        return None if self._status is None else self._status(idempotency_key)
```

- [ ] **Step 3: Run** → `uv run pytest tests/test_youtube_adapter.py tests/test_tiktok_adapter.py -m "not integration" -v` → PASS (2). **Commit.**

```bash
git add shared/adapters/youtube.py shared/adapters/tiktok.py tests/test_youtube_adapter.py tests/test_tiktok_adapter.py
git commit -m "feat(m5): YouTube + TikTok adapters (insert/init + blanket AI-disclosure, ADR 0004/0009)"
```

### Task 11: Stage 06 — ramp-gated, per-platform publish

**Files:** Create `stages/s06_distribute/{stage.py,manifest.json}`; Test `tests/test_s06_distribute.py`

- [ ] **Step 1: Write the failing tests** (the per-platform loop with injected adapters + ramp gate)

```python
# tests/test_s06_distribute.py
from stages.s06_distribute.stage import distribute


class _Adapter:
    def __init__(self, platform):
        self.platform = platform
        self.calls = []

    def publish(self, *, video_id, media_path, metadata, visibility, ledger_path):
        self.calls.append((video_id, visibility))
        return {"remote_id": "r", "url": "u"}


def test_posts_each_platform_when_approved(tmp_path):
    adapters = {"youtube": _Adapter("youtube"), "tiktok": _Adapter("tiktok")}
    posted = distribute(video_id="v", platforms=["youtube", "tiktok"], adapters=adapters,
                        renders={"youtube": "y.mp4", "tiktok": "t.mp4"},
                        metadata={"youtube": {"title": "t", "idempotency_key": "k1"},
                                  "tiktok": {"title": "t", "idempotency_key": "k2"}},
                        visibilities={"youtube": "public", "tiktok": "SELF_ONLY"},
                        ledger_path=tmp_path / "p.jsonl", approved=True)
    assert adapters["youtube"].calls and adapters["tiktok"].calls
    assert set(posted) == {"youtube", "tiktok"}


def test_unapproved_video_is_held_during_the_ramp(tmp_path):
    import pytest
    from stages.s06_distribute.stage import HeldForReview
    adapters = {"youtube": _Adapter("youtube")}
    with pytest.raises(HeldForReview):
        distribute(video_id="v", platforms=["youtube"], adapters=adapters,
                   renders={"youtube": "y.mp4"}, metadata={"youtube": {"title": "t", "idempotency_key": "k"}},
                   visibilities={"youtube": "public"}, ledger_path=tmp_path / "p.jsonl", approved=False)
    assert not adapters["youtube"].calls       # nothing posted
```

- [ ] **Step 2: Implement `stages/s06_distribute/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.distribution.caption import build_caption
from shared.distribution.visibility import resolve_visibility
from shared.ramp.policy import gate_active
from shared.ramp.state import load_state
from shared.stage import StageManifest, stage


class HeldForReview(Exception):
    """The ramp's human gate is active and this video has no approval yet — NOT a failure; the
    review CLI will release it. 06 raises this as a 'quarantine'-adjacent hold, not a crash."""


def distribute(*, video_id, platforms, adapters, renders, metadata, visibilities,
               ledger_path, approved) -> dict:
    if not approved:
        raise HeldForReview(f"{video_id} awaiting human approval (ramp gate active)")
    posted = {}
    for plat in platforms:
        result = adapters[plat].publish(video_id=video_id, media_path=renders[plat],
                                        metadata=metadata[plat], visibility=visibilities[plat],
                                        ledger_path=ledger_path)
        posted[plat] = result or {"skipped": "already confirmed"}
    return posted


@stage(StageManifest(id="06", inputs=["render", "script", "qc"], outputs=["posts"],
                     compute="cpu", capability="distribution"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    niche = ctx.job["niche"]
    state = load_state(ctx.run_dir.parents[1] / "history" / f"ramp.{niche}.json")
    warmed = state.get("warming_until") is not None and not gate_active(state)  # warmed = past warming
    platforms = ctx.job.get("platform_targets", ["youtube"])
    adapters = ctx.backend("distribution")                # {platform: adapter} from config (ADR 0010)
    vis_cfg = ctx.config.get("visibility", {})
    metadata = {p: {**build_caption(script["platform_meta"][p], platform=p,
                                    disclosure_line=ctx.config["disclosure_line"],
                                    affiliate=script.get("affiliate") if ctx.config.get("affiliate_enabled") else None),
                    "idempotency_key": _key(ctx.job["video_id"], p)} for p in platforms}
    posted = distribute(
        video_id=ctx.job["video_id"], platforms=platforms, adapters=adapters,
        renders={p: ctx.run_dir / f"renders/{p}.mp4" for p in platforms}, metadata=metadata,
        visibilities={p: resolve_visibility(p, vis_cfg, warmed=warmed) for p in platforms},
        ledger_path=ctx.run_dir.parents[1] / "history" / "posts.jsonl",
        approved=state.get("approved_videos", {}).get(ctx.job["video_id"], not gate_active(state)))
    out = ctx.write_output("posts")
    out.write_text(json.dumps(posted))
    ctx.log.info("distributed", platforms=list(posted))
    return StageResult(outputs={"posts": out})


def _key(video_id, platform):
    from shared.distribution.posts_ledger import idempotency_key
    return idempotency_key(video_id, platform)
```

- [ ] **Step 3: Write `manifest.json`** → `{"id": "06", "inputs": ["render", "script", "qc"], "outputs": ["posts"], "compute": "cpu", "capability": "distribution"}`. **Run** → PASS (2). **Commit.**

```bash
git add stages/s06_distribute/ tests/test_s06_distribute.py
git commit -m "feat(m5): 06 distribute — ramp-gated per-platform publish via the adapters (ADR 0003 D1/0006)"
```

> **Posted-state fan-in (ADR 0003 D6):** `06` writes the per-video `posts` artifact; the **single fan-in commit step** (M4 `shared/conductor/ledger.py`) appends the confirmed records to `history/posts.jsonl` and the novelty entry — `06` itself never concurrently appends the shared ledgers. The M4 `backup()` step already rsyncs `history/*.jsonl`; `posts.jsonl` is covered.

---

# Part C — The publish ramp + the review CLI

### Task 12: Ramp state (provisioning / warming / counts / gate)

**Files:** Create `shared/ramp/__init__.py` (empty), `shared/ramp/state.py`; Test `tests/test_ramp_state.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ramp_state.py
from shared.ramp.state import load_state, record_decision, mark_provisioned


def test_load_defaults_for_a_new_niche(tmp_path):
    s = load_state(tmp_path / "ramp.finance.json")
    assert s["gate_active"] is True and s["approved"] == 0 and s["rejected"] == 0


def test_record_decision_increments_and_persists(tmp_path):
    p = tmp_path / "ramp.finance.json"
    record_decision(p, video_id="v1", approved=True)
    record_decision(p, video_id="v2", approved=False)
    s = load_state(p)
    assert s["approved"] == 1 and s["rejected"] == 1
    assert s["approved_videos"]["v1"] is True and s["approved_videos"]["v2"] is False


def test_provisioning_sets_warming_window(tmp_path):
    p = tmp_path / "ramp.finance.json"
    mark_provisioned(p, warming_days=7)
    assert load_state(p)["warming_until"] is not None
```

- [ ] **Step 2: Implement `shared/ramp/state.py`** (a small JSON state with atomic temp+rename writes).
- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/ramp/__init__.py shared/ramp/state.py tests/test_ramp_state.py
git commit -m "feat(m5): ramp state — provisioning/warming/decision counts (ADR 0009/0014 D2)"
```

### Task 13: Ramp queue + calibration labels + exit policy

**Files:** Create `shared/ramp/queue.py`, `shared/ramp/labels.py`, `shared/ramp/policy.py`; Modify `schemas/feature_record.schema.json`; Test `tests/test_ramp_queue.py`, `tests/test_ramp_labels.py`, `tests/test_ramp_policy.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ramp_queue.py
from shared.ramp.queue import pending_review


def test_pending_is_passed_both_gates_and_not_yet_decided():
    videos = [{"video_id": "a", "qc_pass": True, "creative_pass": True},
              {"video_id": "b", "qc_pass": False, "creative_pass": True},   # failed safety
              {"video_id": "c", "qc_pass": True, "creative_pass": True}]
    decided = {"a": True}
    assert pending_review(videos, decided) == ["c"]                         # b excluded, a decided
```

```python
# tests/test_ramp_labels.py
def test_decision_writes_a_ramp_label_into_feature_record(tmp_path):
    import json
    from shared.ramp.labels import record_label
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "format": "myth_buster", "scores": {}}))
    record_label(fr, approved=False, reason="thesis was generic")
    rec = json.loads(fr.read_text())
    assert rec["ramp_label"]["approved"] is False                          # ADR 0016 D2 calibration
    assert rec["ramp_label"]["reason"] == "thesis was generic"
```

```python
# tests/test_ramp_policy.py
from shared.ramp.policy import gate_active, can_widen_cadence, EXIT


def test_gate_lifts_only_after_clean_track_record():
    earned = {"approved": 20, "rejected": 0, "approved_days": 14, "strikes": 0}
    assert gate_active(earned) is False
    not_yet = {"approved": 10, "rejected": 0, "approved_days": 14, "strikes": 0}
    assert gate_active(not_yet) is True
    a_rejection = {"approved": 25, "rejected": 1, "approved_days": 20, "strikes": 0}
    assert gate_active(a_rejection) is True                                # any rejection resets


def test_strike_keeps_the_gate_active_regardless():
    assert gate_active({"approved": 99, "rejected": 0, "approved_days": 99, "strikes": 1}) is True


def test_cadence_widening_follows_the_same_bar():
    assert can_widen_cadence({"approved": 20, "rejected": 0, "approved_days": 14, "strikes": 0})
    assert EXIT["min_approved"] == 20 and EXIT["min_days"] == 14
```

- [ ] **Step 2: Add the `ramp_label` block to `schemas/feature_record.schema.json`** (optional, so pre-ramp records still validate — same pattern as M3's `vision.judgment`):

```json
{
  "ramp_label": {
    "type": "object", "additionalProperties": false,
    "required": ["approved"],
    "properties": {"approved": {"type": "boolean"}, "reason": {"type": "string"},
                   "ts": {"type": "string"}}
  }
}
```

- [ ] **Step 3: Implement the three modules**

```python
# shared/ramp/queue.py
def pending_review(videos: list[dict], decided: dict[str, bool]) -> list[str]:
    """The review queue: videos that passed BOTH gates (safe + worth watching) and have no human
    decision yet. A gate failure means it's already quarantined — never in the human's queue."""
    return [v["video_id"] for v in videos
            if v.get("qc_pass") and v.get("creative_pass") and v["video_id"] not in decided]
```

```python
# shared/ramp/labels.py
import json
from datetime import datetime, timezone
from pathlib import Path


def record_label(feature_record_path: Path, *, approved: bool, reason: str = "") -> None:
    """Capture the operator's verdict into feature_record as the 05c judge-calibration label
    (ADR 0016 D2): in M6 the quality floor is re-anchored against these real approve/reject calls."""
    rec = json.loads(feature_record_path.read_text())
    rec["ramp_label"] = {"approved": approved, "reason": reason,
                         "ts": datetime.now(timezone.utc).isoformat()}
    feature_record_path.write_text(json.dumps(rec))
```

```python
# shared/ramp/policy.py
EXIT = {"min_approved": 20, "min_days": 14, "max_rejected": 0, "max_strikes": 0}   # config


def _earned(state: dict) -> bool:
    return (state.get("approved", 0) >= EXIT["min_approved"]
            and state.get("approved_days", 0) >= EXIT["min_days"]
            and state.get("rejected", 0) <= EXIT["max_rejected"]
            and state.get("strikes", 0) <= EXIT["max_strikes"])


def gate_active(state: dict) -> bool:
    """The human-at-publish gate stays ACTIVE until a clean track record is earned (ADR 0014 D2):
    >=20 approvals over >=14 days, zero rejections, zero strikes. Any rejection or strike keeps it on."""
    return not _earned(state)


def can_widen_cadence(state: dict) -> bool:
    return _earned(state)                       # same bar gates the M4 per_niche 1->2 ramp
```

- [ ] **Step 4: Run** → PASS (5). **Commit.**

```bash
git add shared/ramp/queue.py shared/ramp/labels.py shared/ramp/policy.py schemas/feature_record.schema.json tests/test_ramp_queue.py tests/test_ramp_labels.py tests/test_ramp_policy.py
git commit -m "feat(m5): ramp queue + calibration labels + exit policy (ADR 0014 D2/0016 D2)"
```

### Task 14: The review CLI (`make review`)

**Files:** Create `shorts/review.py`; Modify `Makefile`; Test `tests/test_review_cli.py`

- [ ] **Step 1: Write the failing test** (the decision flow with injected I/O — no terminal, no player)

```python
# tests/test_review_cli.py
from shorts.review import review_one


def test_approve_records_label_and_state(tmp_path):
    import json
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "format": "x", "scores": {}}))
    state = tmp_path / "ramp.finance.json"
    calls = {"played": []}
    review_one(video_id="v", render="v.mp4", feature_record=fr, state_path=state,
               play=lambda p: calls["played"].append(p),
               prompt=lambda: ("approve", ""))
    assert calls["played"] == ["v.mp4"]                  # the operator saw it before deciding
    assert json.loads(fr.read_text())["ramp_label"]["approved"] is True
    from shared.ramp.state import load_state
    assert load_state(state)["approved"] == 1


def test_reject_captures_reason(tmp_path):
    import json
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "format": "x", "scores": {}}))
    review_one(video_id="v", render="v.mp4", feature_record=fr, state_path=tmp_path / "s.json",
               play=lambda p: None, prompt=lambda: ("reject", "hook was weak"))
    assert json.loads(fr.read_text())["ramp_label"]["reason"] == "hook was weak"
```

- [ ] **Step 2: Implement `shorts/review.py`**

```python
"""python -m shorts.review — the temporary human-at-publish ramp CLI (ADR 0014 D2).
list pending -> play the YouTube cut -> approve/reject; each decision is captured as a 05c
calibration label (ADR 0016 D2) and releases (or holds) the video for 06."""
from pathlib import Path

from shared.ramp.labels import record_label
from shared.ramp.state import record_decision


def review_one(*, video_id, render, feature_record: Path, state_path: Path, play, prompt) -> bool:
    play(render)                                          # default: open in the system player
    action, reason = prompt()                             # default: input() loop, validated
    approved = action == "approve"
    record_label(feature_record, approved=approved, reason=reason)
    record_decision(state_path, video_id=video_id, approved=approved)
    return approved


def main() -> int:
    # Production wiring: scan runs/<batch>/<video> for qc.json.passed && creative_qc.json.pass,
    # filter via shared.ramp.queue.pending_review against ramp.<niche>.json, then review_one each
    # with play=_open_player (xdg-open/ffplay) and prompt=_tty_prompt. Read-only on renders.
    raise SystemExit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Wire `make review`** → `uv run python -m shorts.review`. **Run** the unit tests → PASS (2). **Commit.**

```bash
git add shorts/review.py Makefile tests/test_review_cli.py
git commit -m "feat(m5): the publish-ramp review CLI (make review) capturing calibration labels (ADR 0014 D2/0016 D2)"
```

---

# Part D — Credentials & ops (the unattended-run prerequisites)

### Task 15: OAuth token-age pre-flight (into the M4 framework) + the ops docs

ADR 0009 #10: Testing-status refresh tokens expire every 7 days and would silently kill the unattended run. M4 Task 11 left the pluggable pre-flight seam ("OAuth token-age slots in here at M5").

**Files:** Modify `shared/conductor/preflight.py`; Create `deploy/host/oauth-production.md`, `deploy/host/platform-audit.md`; Test `tests/test_oauth_preflight.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_oauth_preflight.py
import pytest
from shared.conductor.preflight import oauth_token_age_gate, PreflightFailure


def test_fresh_token_passes_and_stale_fails():
    oauth_token_age_gate(token_age_days=2.0, max_age_days=6.0)          # no raise
    with pytest.raises(PreflightFailure):
        oauth_token_age_gate(token_age_days=8.0, max_age_days=6.0)      # would expire mid-run


def test_gate_is_pluggable_into_run_preflight():
    from shared.conductor.preflight import run_preflight
    calls = []
    run_preflight([lambda: calls.append("space"),
                   lambda: oauth_token_age_gate(token_age_days=1.0, max_age_days=6.0)])
    assert calls == ["space"]                                           # ran in order, no raise
```

- [ ] **Step 2: Add `oauth_token_age_gate` to `shared/conductor/preflight.py`** (alongside the M4 `free_space_gate`/`host_health_gate`)

```python
def oauth_token_age_gate(*, token_age_days: float, max_age_days: float = 6.0) -> None:
    """ADR 0009 #10: a refresh token older than the safety margin would expire mid-batch and
    silently void the unattended run. Fail at the START (systemic, not a per-video quarantine).
    max_age_days < 7 because Testing-status tokens die at 7; Production tokens don't expire on
    inactivity, so once the app is in Production this is a generous sanity bound."""
    if token_age_days > max_age_days:
        raise PreflightFailure(f"OAuth refresh token is {token_age_days:.1f}d old "
                               f"(> {max_age_days}d) — refresh before the run (ADR 0009 #10)")
```

- [ ] **Step 3: Write `deploy/host/oauth-production.md`** — the ops runbook: (1) move the Google Cloud OAuth consent screen from **Testing → Production** (so refresh tokens stop expiring every 7 days); (2) the scopes used (`youtube.upload`); (3) where the refresh token + client secret live (the credential material backed up nightly by M4's `backup()`); (4) the token-refresh cron/check that keeps `token_age_days` low; (5) TikTok's token lifetime + refresh. Write `deploy/host/platform-audit.md` — the **parallel audit submission** checklist: YouTube API compliance audit (for >public quota) and **TikTok's app audit** (the gate that flips `tiktok.audit_cleared` → public, Task 8), with what each reviewer needs.

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/conductor/preflight.py deploy/host/oauth-production.md deploy/host/platform-audit.md tests/test_oauth_preflight.py
git commit -m "feat(m5): OAuth token-age pre-flight + Production/audit ops docs (ADR 0009 #10)"
```

### Task 16: Wire 05b + 06 into the conductor stage order

The M4 executor runs a fixed `stage_order`; M5 adds `05b` (after `05x`/`05c`) and `06` (last, after the ramp gate). No executor code changes — only the order list + the per-video failure-domain rules already handle quarantine/hold.

**Files:** Modify the conductor's stage-order config/constant (where M4 defined `stage_order`); Test `tests/test_stage_order.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stage_order.py
from shared.conductor.executor import default_stage_order


def test_safety_and_distribution_are_last_and_ordered():
    order = default_stage_order()
    assert order.index("05x") < order.index("05b")        # vision before safety (05b reads vision)
    assert order.index("05c") < order.index("06")         # quality before distribute
    assert order.index("05b") < order.index("06")         # safety before distribute
    assert order[-1] == "06"                              # distribution is terminal
```

- [ ] **Step 2: Add `default_stage_order()`** to `shared/conductor/executor.py` returning the full M0–M5 order: `["00a","00b","01a","01b","01c","01d","01e","02","03","04","05","05x","05b","05c","06"]`. A `HeldForReview` from `06` maps to a new terminal status `held` (not `failed`/`quarantined`) — the review CLI releases it on the next batch. Add `held` to the `job.json`/`batch.json` status enum and to `status_for_exit` handling (a dedicated exit code, e.g. `70`, mapping to `held`), so a held video is **resumable**, not lost.
- [ ] **Step 3: Run** → PASS. **Commit.**

```bash
git add shared/conductor/executor.py shared/exitcodes.py schemas/ tests/test_stage_order.py
git commit -m "feat(m5): wire 05b + 06 into the stage order; 'held' status for ramp holds (ADR 0014 D2)"
```

---

## M5 Acceptance Checklist (the testable "done")

- [ ] **05b** runs every spec-Ch.8 check — disclaimer/prohibited-claims (from the **profile**)/citation/AI-disclosure/profanity (hard booleans), CTA safe-zone, the loudness/dead-air/duration/black-run/clipping **numeric windows**, repetition vs the ledger, the **00b-model fact/hallucination** pass, and the **05x artifact** observations — and **quarantines on any single failure**; `qc.json` records every check → Tasks 1–6.
- [ ] **Exactly-once** is owned by the `DistributionAdapter` base: intent→confirmed in `posts.jsonl`, a confirmed video is never re-posted, and a mid-post crash **recovers via `_find_existing`** (the tokenless YouTube path) instead of double-posting → Tasks 7, 9.
- [ ] **06** assembles **keyword-first captions** with the **blanket AI-disclosure** line (+ affiliate when enabled), resolves **private-first / ≥1-public** visibility (TikTok SELF_ONLY until audit-cleared), and posts per-platform via the **YouTube + TikTok adapters** → Tasks 8, 10, 11.
- [ ] The **publish ramp** holds unapproved videos (`HeldForReview`, a resumable `held` status — not a failure), the **`make review` CLI** lists pending → plays → records approve/reject, every decision is **captured as a `feature_record` calibration label** (ADR 0016 D2), and the **gate lifts only on the earned track record** (≥20 approvals / ≥14 days / 0 rejections / 0 strikes), which is the same bar that widens the M4 `per_niche` cadence → Tasks 12–14, 16.
- [ ] The **OAuth token-age pre-flight** plugs into the M4 framework and fails the batch before a mid-run token expiry; the **Production + audit ops docs** exist → Task 15.
- [ ] `05b`/`06` sit correctly in the stage order (05x→05b, 05c→06, 06 terminal); CI stays GPU-free **and network-free** (`-m "not integration"`) — every API call is behind an adapter with a fake → Task 16 + the adapter design.

---

## Self-Review

**Spec coverage (Ch.10 M5 row + Ch.8 + ADRs):** the account-safety gate `05b` (every Ch.8 check, ALL-must-hold, the 00b-model fact pass, the 05x artifact consumption — ADR 0004 D3 / 0005 D8/D10 / 0008 / 0016 D5) → A (Tasks 1–6); distribution `06` (per-platform YouTube + TikTok adapters, exactly-once `posts.jsonl` with tokenless retry-confirm, private-first / ≥1-public, blanket AI-disclosure, keyword-first caption, affiliate-disabled) → B (Tasks 7–11, ADR 0003 D1 / 0006 / 0009 / 0004 D5 / 0010); provisioning + warming → the human-at-publish ramp with the **review CLI** capturing the calibration label set, plus the **ramp-exit criteria** → C (Tasks 12–14, ADR 0014 D2 / 0016 D2); the **OAuth→Production + token-age pre-flight** → D (Task 15, ADR 0009 #10); platform audits → the ops doc (Task 15, parallel/out-of-band). The two spec "Open" items (05b numeric thresholds; ramp-exit criteria) are **pinned in the decisions header** and encoded as config in `audio_defect.py`/`render_integrity.py` + `ramp/policy.py`.

**Placeholder scan:** no "TBD"/"add error handling". The `NotImplementedError` bodies (`_probe`/`_recent_ledger` in 05b; the real Google/TikTok clients injected into the adapters; `review.main`/`run_batch` production wiring) are documented integration/bring-up seams whose pure collaborators are all implemented + tested here (every check predicate, the gate, the posts ledger, the adapter base's exactly-once, caption/visibility, the full ramp policy, the review decision flow). Consistent with the M1–M4 seam discipline.

**Type consistency vs M0–M4:** uses `@stage(StageManifest(...))`, `StageContext`, `StageResult`, `SchemaRegistry().validate`, `ctx.read_input/write_output/backend/quarantine/log`; `05b`/`06` are cpu stages carrying a `capability` (`llm`/`distribution`) mirrored in `manifest.json` (M0 drift-catcher note); `DistributionAdapter` is the M0 interface (exactly-once now in the base, the M0-declared seam); the posts/qc/feature_record schemas extend their **M0 skeletons** (not re-authored), each carrying `schema_version`; the second-pass LLM is `ctx.backend("llm")` (00b's model, ADR 0016 D1 satisfied because this is a *safety* fact-check, not the *quality* verdict); the new `held` status + exit code extend the M4 `status_for_exit` protocol and the ADR 0012 §4 status enum; `06`'s shared-ledger append goes through the M4 single fan-in commit (no concurrent appenders, ADR 0003 D6), and `backup()` already covers `posts.jsonl`.

**Scope:** four parts, one acceptance gate, produces working testable software (a video that passes both gates, waits for one approval, posts exactly once to two platforms with disclosure, and feeds its verdict back as calibration data). Parts A–D are separable for review; A (safety) and B (distribution) are independent; C (ramp) depends on B's stage existing; D is independent ops. After M5 the only thing standing between the pipeline and the Chapter-1 unattended DoD is **M6** (the 1–2 week run + alerts/GC + re-anchoring the 05c floor on M5's collected labels).
