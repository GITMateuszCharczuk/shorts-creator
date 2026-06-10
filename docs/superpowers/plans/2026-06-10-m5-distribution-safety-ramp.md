# M5 — Account-Safety Gate + Distribution + the Publish Ramp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop from a rendered video to a posted one. Build the **always-on account-safety gate** (`05b`, ADR 0004 D3 — the durable "human replacement"), the **distribution stage** (`06`, per-platform adapters to YouTube + TikTok with the `posts.jsonl` **exactly-once** ledger, ADR 0003 D1), and the **temporary human-at-publish ramp** — provisioning/warming → a **minimal review CLI** (`make review`) whose every approve/reject is **captured as the judge-calibration label set** (ADR 0016 D2), with concrete **ramp-exit criteria**. Plus the credential work the unattended run rests on: the **OAuth token-age pre-flight** (into M4's framework) and the **OAuth-app→Production** move (ADR 0009 #10).

**Architecture:** Everything extends the M0 SDK + the M4 conductor. `05b` is a thin stage over **pure check modules** (`shared/safety/`) — disclaimer/denylist/citation/disclosure/profanity/safe-zone/audio-defect/render-integrity/repetition/artifact are all deterministic and CI-tested; the only model call is the **second-pass fact/sanity LLM, which reuses 00b's host endpoint + eviction rule** (spec Ch.8, integration-marked). `06` is a thin stage over the **M0 `DistributionAdapter`** whose **base class owns exactly-once** (intent→confirm against a **per-video posts ledger**, merged into `history/posts.jsonl` by the M4 single fan-in commit — ADR 0003 D6); the two real adapters (`YouTubeAdapter`, `TikTokAdapter`) implement only the platform `_post`/`_find_existing` primitives (integration). The ramp is **pure policy** (`shared/ramp/`) plus a thin `shorts/review.py` CLI; it gates `06` and feeds back into the M4 `per_niche` ramp knob. The OAuth check **slots into the M4 pluggable pre-flight framework** (M4 Task 11 left the seam). CI stays GPU-free and network-free — every API call is behind an adapter with a fake.

**Tech Stack:** Python 3.12 + the M0–M4 toolchain (no new runtime deps for the pure layer); `google-api-python-client` + `google-auth-oauthlib` (YouTube Data API v3) and `httpx` (TikTok Content Posting API) behind the adapters; `ffprobe`/`ffmpeg` for render-integrity probes (integration). CI runs only pure/fake tests (`-m "not integration"`).

**Decisions made here (spec/ADRs left open; pinned for M5):**
- **One `CheckResult` type** lives in `shared/safety/types.py`; every check module and `gate.py` import it (so `aggregate(list[CheckResult])` is honest and `isinstance` holds). The numeric thresholds also live here as a single `SafetyThresholds` dataclass — no duplicated constants across modules.
- **05b is ALL-must-hold, and every check is a hard boolean except the numeric windows** (resolves spec Ch.8 "Open: numeric pass/fail thresholds"). Hard booleans: disclaimer present, no prohibited-claim hit, ≥1 cited source, AI-disclosure flag set, profanity clear, no artifact observation, CTA-bump inside the platform safe-zone, second-pass-LLM `hallucination=false`. Numeric windows (config via `SafetyThresholds`): **integrated loudness ∈ [-16, -12] LUFS & true-peak ≤ -1 dBTP**; **no silence > 0.4 s inside the first 2.5 s** (hook dead-air) and **no black run > 0.25 s** (mean luma < 16/255); **synth duration within ±8 % of the script's projected runtime**. Any single failure → **quarantine, never post**.
- **All safety policy is profile/config data, not gate code.** The denylist is `profile.defaults.denylist_terms` (literal trigger phrases — the machine-readable companion to the human-readable `prohibited_claims`); the disclaimer is `profile.defaults.disclaimer`; the profanity wordlist is `profile.defaults.profanity_wordlist` (falling back to a global default); the thresholds come from `ctx.config["safety"]`; the per-platform safe-zones come from `ctx.config["safe_zones"]` (defaults in `geometry.py`). **No stage source carries a hardcoded policy wordlist** — the M0 `test_no_platform_branches` rule is extended to forbid this.
- **05b's second-pass LLM is the 00b model** (spec Ch.8: "same host endpoint + eviction rule as 00b") — a fact/sanity/**hallucination-only** check. Its prompt returns **only** `{"hallucination": bool, "note": str}`; the stage **rejects** any response carrying a quality-adjacent key (`score`/`quality`/`interesting`). Reusing the author model is correct here because this is a *support* check, not a *quality* verdict — the ADR 0016 D1 independent-judge rule binds only 05c's quality survival criterion.
- **AI-disclosure uses only API-available channels — we do NOT invent an API field** (corrects the earlier `containsSyntheticMedia` mistake; that flag has **no** YouTube Data API v3 surface — it is Studio-UI-only as of 2026). The blanket disclosure is: (1) the **disclosure line appended to the description** on both platforms (API-settable, always applied); (2) **TikTok's `post_info` AI-content flag** (`AIGC` toggle — the correct object, not `source_info`). YouTube's Studio "altered/synthetic content" toggle is a **recorded out-of-band ops step** (`platform-audit.md`); a video whose internal `ai_disclosure` intent can't be satisfied via API still carries the description line (the available disclosure) and the gap is documented, never silently dropped.
- **Exactly-once lives in the `DistributionAdapter` base** (ADR 0003 D1): `publish()` writes an **intent** record (`(video_id, platform)` + a deterministic `idempotency_key`) to the **per-video** posts ledger *before* the call, an optional **publishing** record for async platforms, and a **confirmed** record (remote id) *after* the post is verified live. The **shared `history/posts.jsonl` is written only by the M4 fan-in commit** (no concurrent appenders, ADR 0003 D6) — `06` emits a per-video `posts` artifact that fan-in merges. Cross-batch dedup reads the shared ledger **read-only**.
- **Crash-recovery is platform-correct:** on an intent-without-confirm retry, **YouTube** `_find_existing` searches the **uploads playlist** (`channels.list`→`playlistItems.list`, near-real-time, 1 unit) for the marker — **never `search.list`** (minutes-to-hours index lag → blind double-post risk). **TikTok** `_find_existing` **polls publish status** by the stored `publish_id`; a `confirmed` record is written **only** after `PUBLISH_COMPLETE` (init-time acceptance ≠ published).
- **Visibility is a `DistributionAdapter.allowed_visibility(cfg)` seam, not per-platform branches** (ADR 0010 D3): each adapter declares its legal visibility set; `resolve_visibility` picks from it via generic config keys (`default_visibility`, `public_after_warming`, `audit_cleared`). **YouTube leads the ≥1 public** (`public` after warming); **TikTok stays `SELF_ONLY` until `audit_cleared`**; private-first everywhere until warmed. Adding a platform = a new adapter + config, no edit to `resolve_visibility`.
- **Caption assembly:** the **primary keyword leads the first ~150 chars** (ADR 0006), then the hook line, hashtags, the disclosure line, and — when `affiliate.enabled` (default **false**, ships disabled, ADR 0004 D5) — the affiliate block. Built from `script.platform_meta` + the profile; per-platform.
- **Two-tier ramp criteria (resolves spec Ch.8 "Open: ramp-exit criteria"; makes ADR 0014 D2's "track record" testable, and achievable in a PoC window):** the **gate-lift bar** (lifts the per-post human gate) = **≥10 approvals over ≥7 days, ≤1 rejection in the trailing window, 0 strikes**; the stricter **cadence-widening bar** (allows `per_niche` 1→2) = **≥20 approvals over ≥14 days, 0 rejections, 0 strikes**. Rejections count in a **trailing rolling window** (they don't hard-reset the counter to zero). All numbers are config (`ctx.config["ramp"]`). Until the gate lifts, `06` posts **only human-approved** videos.
- **Provisioning + warming is a state, not a stage:** `history/ramp.<niche>.json` tracks `provisioned`, `warming_until` (a timestamp), `approved`/`rejected` counts + `first_approval_ts`, and `approved_videos`. **"Warmed" is a calendar predicate** (`now ≥ warming_until`) — independent of the gate-lift track record. The conductor reads it (gates cadence) and `06` reads it (gates posting + visibility). Its path is passed via `ctx.config["ramp_state_path"]` (not derived from run-dir depth).
- **A held video is first-class and resumable:** `06` raising `HeldForReview` maps to a new **`held`** status + exit code **70**, threaded through `status_for_exit`, the `batch.schema`/`job.schema` status enums, the executor's skip set, **and** the boot reconciler (`resume_plan` re-queues `held` — safe, because the adapter's exactly-once makes a re-run idempotent). A held video waits for the review CLI; it is never silently dropped or re-posted.
- **The review CLI is read-only against renders + append-only against labels:** `make review` lists pending → plays the YouTube cut → records approve/reject; a decision writes the ramp label into **`feature_record`** (the ADR 0016 D2 calibration set — so 05c's floor can be re-anchored in M6) and into the ramp state. It never mutates a render or re-runs a stage.
- **`feature_record` authorship is pinned (the M0 06-output, restored).** M0 designed **Stage 06 to emit `feature_record`**; this milestone keeps that (06's `outputs` are `["posts", "feature_record"]`). The field writers, end to end: **00b** stamps `niche` + `format` + `seed` + `hook_variant_id` + `judge_scores` (its best-of-N pick, M1); **06** copies the **`creative_qc.overall`** it already reads into **`feature_record.creative_qc_overall`** (the scalar M6's calibration consumes); the **review CLI** appends `ramp_label`. So `creative_qc` is a **06 input** and `feature_record` a **06 output** — both restored vs the earlier draft that dropped them. Per the M0 living-contracts rule, this task **updates `schemas/feature_record.schema.json`** (add `niche` + the optional `creative_qc_overall` + the optional `ramp_label` block — pre-ramp/pre-distribute records still validate), **the M0 stage-06 edge-table row**, and the golden fixture.
- **This milestone evolves three M0 contracts and syncs them in-task (the M0 living-contracts rule):** `qc.schema` (M0 `{verdict, checks:object}` → `{passed, checks:array}` — Task 7 rewrites the schema **and** the M0 `qc.json` golden fixture), `posts.schema` (M0 `{remote_post_id, timestamp, visibility, state:[intent,confirmed]}` → `{remote_id, url, ts, idempotency_key, state:[intent,publishing,confirmed]}`, platform open — Task 9 updates the fixture), and the **`DistributionAdapter` Protocol** (M0's `publish(render, meta)/confirm_posted/allowed_visibility` → the exactly-once base of Task 11 — this task **updates the M0 Protocol + the M1 adapter stubs** to the new surface). Each bumps its `schema_version` and re-runs the drift-catcher + fixture sweep. Also: **`script.platform_meta.ai_disclosure`** (read by 05b) is added to `script.schema` here (the M0 `platform_meta` object gains the boolean), and **`render_manifest`** is declared a named `05`→`05b` input (the cache-correct edge, matching M3's `05x`).

---

## File Structure

```
shared/safety/                              # NEW: the 05b check library (all pure, CI-tested)
  __init__.py
  types.py                                  # the ONE CheckResult + SafetyThresholds (no duplicated constants)
  checks.py                                 # disclaimer / prohibited-claims / citation / disclosure / profanity / artifact
  geometry.py                               # CTA-bump safe-zone containment per platform (config-driven, ADR 0005 D10)
  audio_defect.py                           # hook dead-air / loudness window / synth-duration (pure, threshold-injected)
  render_integrity.py                       # black-run / clipped-loudness (pure, threshold-injected)
  repetition.py                             # repetitious-content vs the novelty ledger (reuse the M2/M4 pattern)
  probe.py                                  # the ProbeResult contract (the 05b<->ffprobe/loudnorm seam) + the integration probe
  gate.py                                   # aggregate ALL-must-hold -> qc payload + verdict
shared/distribution/                        # NEW: the 06 pure layer
  __init__.py
  posts_ledger.py                           # exactly-once intent/publishing/confirmed; (video_id, platform); hard-fail on corrupt JSONL
  caption.py                                # keyword-first ~150c + disclosure line + affiliate block + per-platform meta
  visibility.py                             # resolve_visibility via the adapter's allowed_visibility() seam (ADR 0010 D3)
shared/adapters/
  base.py                                   # MODIFY: DistributionAdapter base OWNS exactly-once (publish()) + allowed_visibility()
  youtube.py                                # NEW: YouTubeAdapter — Data API v3 insert; uploads-playlist retry-confirm
  tiktok.py                                 # NEW: TikTokAdapter — Content Posting API; post_info AIGC flag; status-poll confirm
shared/ramp/                                # NEW: the publish-ramp policy (pure)
  __init__.py
  state.py                                  # ramp.<niche>.json load/update (provisioned/warming/counts/first_approval_ts)
  queue.py                                  # pending = passed 05b+05c, not yet human-decided
  labels.py                                 # approve/reject -> feature_record calibration label (ADR 0016 D2)
  policy.py                                 # the two-tier bars: gate_active? + can_widen_cadence? (config-driven)
shared/conductor/preflight.py               # MODIFY: oauth_token_age_gate (mode-aware) + youtube_quota_gate
shared/conductor/reconcile.py               # MODIFY: resume_plan re-queues 'held'
shared/conductor/executor.py                # MODIFY: default_stage_order() incl. 05b/06; skip set incl. 'held'
shared/exitcodes.py                         # MODIFY: EXIT_HELD = 70; status_for_exit -> 'held'
shorts/review.py                            # NEW: python -m shorts.review (make review): list -> play -> approve/reject
stages/s05b_safety/{stage.py,manifest.json} # NEW: read render+script+vision+narration+music -> the checks -> qc.json (gate)
stages/s06_distribute/{stage.py,manifest.json}  # NEW: ramp-gated, per-platform publish; emits the per-video posts artifact
schemas/qc.schema.json                      # MODIFY: pin checks[] {name,ok,detail} + passed (extend the M0 skeleton)
schemas/posts.schema.json                   # MODIFY: state enum intent|publishing|confirmed; platform open (registry-validated)
schemas/feature_record.schema.json          # MODIFY: add the optional `ramp_label` block (ADR 0016 D2)
schemas/job.schema.json schemas/batch.schema.json  # MODIFY: add 'held' to the status enum
profiles/finance/profile.yaml profiles/business/profile.yaml  # MODIFY: add defaults.denylist_terms (+ optional profanity_wordlist)
deploy/host/oauth-production.md             # NEW: the ADR 0009 #10 ops doc (Testing->Production, token longevity, Studio disclosure)
deploy/host/platform-audit.md               # NEW: the YouTube/TikTok audit submission checklist (ops)
Makefile                                    # add `review:` target
tests/
  test_safety_types.py  test_safety_checks.py  test_safety_geometry.py  test_audio_defect.py
  test_render_integrity.py  test_repetition.py  test_safety_probe.py  test_safety_gate.py
  test_posts_ledger.py  test_caption.py  test_visibility.py
  test_distribution_base.py  test_youtube_adapter.py  test_tiktok_adapter.py
  test_ramp_state.py  test_ramp_queue.py  test_ramp_labels.py  test_ramp_policy.py
  test_review_cli.py  test_oauth_preflight.py  test_quota_preflight.py
  test_held_status.py  test_stage_order.py  test_reconcile_held.py
  test_s05b_safety.py  test_s06_distribute.py
```

**Responsibility split:** `shared/safety/` = the deterministic safety checks (the model call + ffprobe are thin seams behind a typed contract); `shared/distribution/` = exactly-once + caption + visibility (pure); `shared/adapters/{youtube,tiktok}.py` = the only network code, behind the base's exactly-once; `shared/ramp/` = the human-gate policy + calibration capture (pure); `shorts/review.py` = the thin operator CLI. New stages stay thin M0 `run(ctx)` shells. The only M4 modules touched are the additive seams M4 left open (exitcodes, executor stage-order/skip-set, reconcile, preflight).

---

# Part A — The account-safety gate (Stage 05b)

### Task 1: The shared safety types (the ONE `CheckResult` + `SafetyThresholds`)

**Files:** Create `shared/safety/__init__.py` (empty), `shared/safety/types.py`; Test `tests/test_safety_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_safety_types.py
from shared.safety.types import CheckResult, SafetyThresholds


def test_check_result_shape():
    r = CheckResult(ok=False, name="disclaimer", detail="missing")
    assert (r.ok, r.name, r.detail) == (False, "disclaimer", "missing")


def test_thresholds_have_documented_defaults_and_are_overridable():
    t = SafetyThresholds()
    assert (t.lufs_min, t.lufs_max, t.tp_max) == (-16.0, -12.0, -1.0)
    assert t.hook_window_s == 2.5 and t.max_hook_silence_s == 0.4
    assert t.max_black_run_s == 0.25 and t.duration_tol == 0.08
    custom = SafetyThresholds.from_config({"lufs_max": -10.0})
    assert custom.lufs_max == -10.0 and custom.lufs_min == -16.0      # partial override keeps defaults
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `shared/safety/types.py`**

```python
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str
    detail: str = ""


@dataclass(frozen=True)
class SafetyThresholds:
    """The single home for every 05b numeric window (ADR 0005 D8). Loaded from
    ctx.config['safety'] via from_config(); the constructor defaults ARE the documented defaults."""
    lufs_min: float = -16.0
    lufs_max: float = -12.0
    tp_max: float = -1.0
    hook_window_s: float = 2.5
    max_hook_silence_s: float = 0.4
    max_black_run_s: float = 0.25
    duration_tol: float = 0.08

    @classmethod
    def from_config(cls, cfg: dict) -> "SafetyThresholds":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (cfg or {}).items() if k in known})
```

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/safety/__init__.py shared/safety/types.py tests/test_safety_types.py
git commit -m "feat(m5): the shared safety types — one CheckResult + SafetyThresholds (ADR 0005 D8)"
```

### Task 2: Content checks (disclaimer / prohibited-claims / citation / disclosure / profanity / artifact)

Every Ch.8 *content* check, all reading **profile/config data** (the M3 `denylist_terms`/`disclaimer`/`profanity_wordlist`). The artifact check reads the M3 `vision.json` observations (the 05x dual-consumer contract, ADR 0008/0016 D5).

**Files:** Create `shared/safety/checks.py`; Modify `profiles/finance/profile.yaml` + `profiles/business/profile.yaml` (add `defaults.denylist_terms`); Test `tests/test_safety_checks.py`

- [ ] **Step 1: Add `denylist_terms` to the profiles** (the literal phrases the gate matches — the machine-readable companion to the human-readable `prohibited_claims` already authored in M3). Finance example:

```yaml
defaults:
  # ... existing disclaimer / prohibited_claims ...
  denylist_terms: ["buy", "sell", "guaranteed", "risk-free", "can't lose",
                   "price target", "you should buy", "you should sell", "double your money"]
  # profanity_wordlist: optional per-niche override; omitted -> the global default applies
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_safety_checks.py
from shared.safety.checks import (disclaimer_present, no_prohibited_claims, sources_cited,
                                  disclosure_set, profanity_clear, artifact_clear)

PROFILE = {"defaults": {"disclaimer": "Educational only — not financial advice.",
                        "denylist_terms": ["guaranteed", "you should buy"]}}


def test_disclaimer_must_match_the_profile():
    assert disclaimer_present({"disclaimer": "Educational only — not financial advice."}, PROFILE).ok
    assert not disclaimer_present({"disclaimer": ""}, PROFILE).ok


def test_prohibited_terms_come_FROM_THE_PROFILE_not_hardcoded():
    # a term the profile does NOT list must pass; a listed term must fail -> proves data-driven
    p = {"defaults": {"disclaimer": "d", "denylist_terms": ["sasquatch"]}}
    assert no_prohibited_claims({"narration_beats": [{"text": "you should buy this"}]}, p).ok
    bad = no_prohibited_claims({"narration_beats": [{"text": "a wild sasquatch appears"}]}, p)
    assert not bad.ok and "sasquatch" in bad.detail


def test_sources_must_be_cited():
    assert sources_cited({"claims": [{"value": "3.2%", "source_ref": "data.cpi"}]}).ok
    assert not sources_cited({"claims": []}).ok


def test_ai_disclosure_flag_required():
    assert disclosure_set({"platform_meta": {"ai_disclosure": True}}).ok
    assert not disclosure_set({"platform_meta": {"ai_disclosure": False}}).ok


def test_profanity_uses_profile_wordlist_then_default():
    assert profanity_clear({"narration_beats": [{"text": "clean copy"}]}, wordlist={"badword"}).ok
    assert not profanity_clear({"narration_beats": [{"text": "a badword here"}]}, wordlist={"badword"}).ok


def test_artifact_check_reads_vision_observations():
    clean = {"judgment": {"observations": ["clean composition", "text legible"]}}
    dirty = {"judgment": {"observations": ["hand morphing in frame 3", "garbled text on end card"]}}
    assert artifact_clear(clean).ok
    bad = artifact_clear(dirty)
    assert not bad.ok and ("morph" in bad.detail or "garbled" in bad.detail)
```

- [ ] **Step 3: Implement `shared/safety/checks.py`**

```python
from shared.safety.types import CheckResult

_DEFAULT_PROFANITY = {"damn", "hell", "crap"}            # global default; profile may override
_ARTIFACT_LEXICON = ("morph", "garbled", "extra finger", "warp", "melted",
                     "caption overlap", "occlud", "distorted text")


def _text(script: dict) -> str:
    spoken = " ".join(b.get("text", "") for b in script.get("narration_beats", []))
    captions = " ".join(c.get("text", "") for c in script.get("captions", []))
    return f"{spoken} {captions}".lower()


def disclaimer_present(script: dict, profile: dict) -> CheckResult:
    want = profile["defaults"]["disclaimer"].strip()
    got = (script.get("disclaimer") or "").strip()
    return CheckResult(got == want and bool(want), "disclaimer",
                       "" if got == want else f"disclaimer != profile ({got!r})")


def no_prohibited_claims(script: dict, profile: dict) -> CheckResult:
    """The denylist is the PROFILE's denylist_terms (data, not code, ADR 0010 D5). Conservative by
    design: a match quarantines (safe); the list is the niche's responsibility to keep complete."""
    terms = [t.lower() for t in profile["defaults"].get("denylist_terms", [])]
    text = _text(script)
    hit = next((t for t in terms if t in text), None)
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
    words = wordlist if wordlist is not None else _DEFAULT_PROFANITY
    tokens = set(_text(script).split())
    hit = next((w for w in words if w in tokens), None)
    return CheckResult(hit is None, "profanity", "" if hit is None else f"profanity {hit!r}")


def artifact_clear(vision: dict) -> CheckResult:
    """The 05x dual-consumer contract (ADR 0008/0016 D5): fail on any artifact observation
    (morphing/garbled text/caption occlusion). 05c judged its visual *quality*; 05b judges *safety*."""
    obs = [o.lower() for o in vision.get("judgment", {}).get("observations", [])]
    hit = next((o for o in obs if any(k in o for k in _ARTIFACT_LEXICON)), None)
    return CheckResult(hit is None, "artifact", "" if hit is None else f"artifact: {hit}")
```

- [ ] **Step 4: Run** → PASS (6). **Commit.**

```bash
git add shared/safety/checks.py profiles/finance/profile.yaml profiles/business/profile.yaml tests/test_safety_checks.py
git commit -m "feat(m5): 05b content + artifact checks, all profile-data-driven (ADR 0004 D3/0010 D5/0016 D5)"
```

### Task 3: CTA-bump safe-zone geometry (config-driven, ADR 0005 D10)

**Files:** Create `shared/safety/geometry.py`; Test `tests/test_safety_geometry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_safety_geometry.py
from shared.safety.geometry import in_safe_zone, DEFAULT_SAFE_ZONES


def test_tiktok_right_rail_and_caption_band_are_unsafe():
    assert not in_safe_zone({"x": 980, "y": 1200, "w": 80, "h": 80}, platform="tiktok").ok
    assert in_safe_zone({"x": 120, "y": 900, "w": 600, "h": 200}, platform="tiktok").ok


def test_zones_are_config_overridable():
    zones = {"reels": {"x0": 0, "x1": 1080, "y0": 0, "y1": 1920}}     # a new platform via config
    assert in_safe_zone({"x": 10, "y": 10, "w": 10, "h": 10}, platform="reels", zones=zones).ok


def test_unknown_platform_uses_strictest_zone():
    z = DEFAULT_SAFE_ZONES["_strict"]
    assert in_safe_zone({"x": z["x0"], "y": z["y0"], "w": 10, "h": 10}, platform="???").ok
```

- [ ] **Step 2: Implement `shared/safety/geometry.py`** (defaults here; the stage passes `ctx.config["safe_zones"]`)

```python
from shared.safety.types import CheckResult

DEFAULT_SAFE_ZONES = {
    "tiktok":  {"x0": 40, "x1": 950, "y0": 80, "y1": 1500},   # right-rail >950, caption band >1500
    "youtube": {"x0": 40, "x1": 1040, "y0": 80, "y1": 1800},  # lower controls >1800
    "_strict": {"x0": 40, "x1": 950, "y0": 80, "y1": 1500},
}


def in_safe_zone(rect: dict, *, platform: str, zones: dict | None = None) -> CheckResult:
    table = zones or DEFAULT_SAFE_ZONES
    z = table.get(platform) or table.get("_strict") or DEFAULT_SAFE_ZONES["_strict"]
    ok = (rect["x"] >= z["x0"] and rect["x"] + rect["w"] <= z["x1"]
          and rect["y"] >= z["y0"] and rect["y"] + rect["h"] <= z["y1"])
    return CheckResult(ok, "safe_zone", "" if ok else f"CTA rect outside {platform} safe zone {z}")
```

- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/safety/geometry.py tests/test_safety_geometry.py
git commit -m "feat(m5): CTA-bump safe-zone geometry, config-driven per platform (ADR 0005 D10)"
```

### Task 4: Audio-defect + render-integrity (thresholds injected, not module constants)

**Files:** Create `shared/safety/audio_defect.py`, `shared/safety/render_integrity.py`; Test `tests/test_audio_defect.py`, `tests/test_render_integrity.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audio_defect.py
from shared.safety.audio_defect import loudness_ok, hook_dead_air_ok, synth_duration_ok
from shared.safety.types import SafetyThresholds

T = SafetyThresholds()


def test_loudness_window():
    assert loudness_ok(integrated_lufs=-14.0, true_peak_dbtp=-1.5, t=T).ok
    assert not loudness_ok(integrated_lufs=-9.0, true_peak_dbtp=-1.5, t=T).ok    # too hot
    assert not loudness_ok(integrated_lufs=-14.0, true_peak_dbtp=-0.2, t=T).ok   # clipped peak


def test_hook_dead_air():
    assert hook_dead_air_ok(silences=[(3.0, 3.6)], t=T).ok                       # outside the hook
    assert not hook_dead_air_ok(silences=[(0.5, 1.1)], t=T).ok                   # 0.6s dead hook


def test_synth_duration_within_tolerance():
    assert synth_duration_ok(actual_s=30.0, projected_s=31.0, t=T).ok            # ~3% < 8%
    assert not synth_duration_ok(actual_s=20.0, projected_s=30.0, t=T).ok        # 33% off
```

```python
# tests/test_render_integrity.py
from shared.safety.render_integrity import black_run_ok, no_clipping_ok
from shared.safety.types import SafetyThresholds

T = SafetyThresholds()


def test_black_run():
    assert black_run_ok(black_spans=[(5.0, 5.1)], t=T).ok        # 0.1s blink ok
    assert not black_run_ok(black_spans=[(5.0, 5.5)], t=T).ok    # 0.5s black > 0.25s


def test_clipping_guard():
    assert no_clipping_ok(true_peak_dbtp=-1.0, t=T).ok
    assert not no_clipping_ok(true_peak_dbtp=0.0, t=T).ok
```

- [ ] **Step 2: Implement both** (every threshold comes from the injected `SafetyThresholds`)

```python
# shared/safety/audio_defect.py
from shared.safety.types import CheckResult, SafetyThresholds


def loudness_ok(*, integrated_lufs: float, true_peak_dbtp: float, t: SafetyThresholds) -> CheckResult:
    ok = t.lufs_min <= integrated_lufs <= t.lufs_max and true_peak_dbtp <= t.tp_max
    return CheckResult(ok, "loudness", "" if ok else f"I={integrated_lufs} TP={true_peak_dbtp} outside window")


def hook_dead_air_ok(*, silences: list[tuple[float, float]], t: SafetyThresholds) -> CheckResult:
    for start, end in silences:
        if start < t.hook_window_s and (min(end, t.hook_window_s) - start) > t.max_hook_silence_s:
            return CheckResult(False, "hook_dead_air", f"silence in first {t.hook_window_s}s")
    return CheckResult(True, "hook_dead_air")


def synth_duration_ok(*, actual_s: float, projected_s: float, t: SafetyThresholds) -> CheckResult:
    if projected_s <= 0:
        return CheckResult(False, "synth_duration", "no projected runtime")
    off = abs(actual_s - projected_s) / projected_s
    return CheckResult(off <= t.duration_tol, "synth_duration",
                       "" if off <= t.duration_tol else f"{off:.0%} off projected")
```

```python
# shared/safety/render_integrity.py
from shared.safety.types import CheckResult, SafetyThresholds


def black_run_ok(*, black_spans: list[tuple[float, float]], t: SafetyThresholds) -> CheckResult:
    worst = max((e - s for s, e in black_spans), default=0.0)
    return CheckResult(worst <= t.max_black_run_s, "black_run",
                       "" if worst <= t.max_black_run_s else f"{worst:.2f}s black run")


def no_clipping_ok(*, true_peak_dbtp: float, t: SafetyThresholds) -> CheckResult:
    return CheckResult(true_peak_dbtp <= t.tp_max, "clipping",
                       "" if true_peak_dbtp <= t.tp_max else f"true-peak {true_peak_dbtp} dBTP")
```

- [ ] **Step 3: Run** → both PASS. **Commit.**

```bash
git add shared/safety/audio_defect.py shared/safety/render_integrity.py tests/test_audio_defect.py tests/test_render_integrity.py
git commit -m "feat(m5): 05b numeric windows with injected thresholds (ADR 0005 D8)"
```

### Task 5: Repetitious-content check vs the novelty ledger

**Files:** Create `shared/safety/repetition.py`; Test `tests/test_repetition.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_repetition.py
from shared.safety.repetition import not_repetitious


def test_fresh_topic_passes_and_recent_duplicate_fails():
    ledger = [{"topic": "cpi", "hook": "Inflation cooled again"}]
    assert not_repetitious({"topic": "fed", "hook": "The Fed blinked"}, ledger).ok
    assert not not_repetitious({"topic": "cpi", "hook": "Inflation cooled again"}, ledger).ok


def test_same_topic_different_angle_passes():
    ledger = [{"topic": "cpi", "hook": "Inflation cooled again"}]
    assert not_repetitious({"topic": "cpi", "hook": "Why your rent ignores the CPI"}, ledger).ok
```

- [ ] **Step 2: Implement `shared/safety/repetition.py`**

```python
from shared.safety.types import CheckResult


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / len(sa | sb) if (sa or sb) else 0.0


def not_repetitious(record: dict, ledger: list[dict], *, hook_sim: float = 0.6) -> CheckResult:
    """Repetition = SAME topic AND a near-duplicate hook. Same topic, fresh angle is allowed."""
    for past in ledger:
        if past.get("topic") == record.get("topic") and \
                _jaccard(record.get("hook", ""), past.get("hook", "")) >= hook_sim:
            return CheckResult(False, "repetition", f"near-duplicate of posted {past.get('topic')!r}")
    return CheckResult(True, "repetition")
```

- [ ] **Step 3: Run** → PASS. **Commit.**

```bash
git add shared/safety/repetition.py tests/test_repetition.py
git commit -m "feat(m5): repetitious-content check vs the novelty ledger (ADR 0002/0009)"
```

### Task 6: The probe contract (the 05b↔ffprobe seam)

The numeric checks need measured inputs. Pin a typed contract so the integration wiring can't drift.

**Files:** Create `shared/safety/probe.py`; Test `tests/test_safety_probe.py`

- [ ] **Step 1: Write the failing test** (the contract shape + a fake builder; the real ffprobe path is integration)

```python
# tests/test_safety_probe.py
from shared.safety.probe import ProbeResult


def test_probe_result_carries_every_numeric_input_05b_needs():
    p = ProbeResult(integrated_lufs=-14.0, true_peak_dbtp=-1.4, silences=[(0.0, 0.1)],
                    black_spans=[], actual_s=30.0, projected_s=31.0,
                    cta_rect={"x": 120, "y": 900, "w": 600, "h": 200})
    assert p.integrated_lufs == -14.0 and p.cta_rect["w"] == 600
    assert isinstance(p.silences, list) and isinstance(p.black_spans, list)
```

- [ ] **Step 2: Implement `shared/safety/probe.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    """The 05b measurement contract. Field names match the check signatures exactly so the
    integration probe (ffprobe/loudnorm/luma + render_manifest read) can't silently drift."""
    integrated_lufs: float           # ffmpeg -af loudnorm=print_format=json (input_i)
    true_peak_dbtp: float            # loudnorm input_tp
    silences: list                   # ffmpeg silencedetect -> [(start_s, end_s)]
    black_spans: list                # ffprobe/blackdetect -> [(start_s, end_s)] (luma < 16/255)
    actual_s: float                  # ffprobe format.duration of renders/youtube.mp4
    projected_s: float               # script's projected runtime (sum of segment durations)
    cta_rect: dict                   # the end_card region from render_manifest.json (x,y,w,h)


def probe(run_dir: Path, *, narration, music, render, render_manifest) -> ProbeResult:
    raise NotImplementedError(
        "Integration seam: run loudnorm on `music` (the final mix), silencedetect on `narration`, "
        "blackdetect + duration on `render`, and read the end_card rect from `render_manifest`. "
        "CI uses a fixture ProbeResult; the pure checks (Tasks 3-4) are unit-tested.")
```

- [ ] **Step 3: Run** → PASS. **Commit.**

```bash
git add shared/safety/probe.py tests/test_safety_probe.py
git commit -m "feat(m5): the 05b ProbeResult contract (the ffprobe/loudnorm seam, no drift)"
```

### Task 7: The gate aggregation → `qc.json` (ALL-must-hold)

**Files:** Create `shared/safety/gate.py`; Modify `schemas/qc.schema.json`; Test `tests/test_safety_gate.py`

- [ ] **Step 1: Pin `schemas/qc.schema.json`** (extend the M0 skeleton — **keep `schema_version`**, pin `checks[]` incl. the optional `detail`)

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
        "properties": {"name": {"type": "string"}, "ok": {"type": "boolean"},
                       "detail": {"type": "string"}}
      }
    }
  }
}
```

> Confirm M0's skeleton fields (`schema_version`) survive — this extends, never re-authors. `detail` is in `properties` so `gate.aggregate`'s conditional detail validates.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_safety_gate.py
from shared.safety.gate import aggregate
from shared.safety.types import CheckResult
from shared.schema import SchemaRegistry


def test_all_must_hold_and_payload_validates():
    payload = aggregate([CheckResult(True, "disclaimer"), CheckResult(True, "loudness", "ok")])
    SchemaRegistry().validate("qc", payload)             # incl. the detail field
    assert payload["passed"] is True


def test_one_failure_fails_the_gate_and_names_it():
    payload = aggregate([CheckResult(True, "disclaimer"),
                         CheckResult(False, "prohibited_claims", "phrase 'guaranteed'")])
    assert payload["passed"] is False
    assert any(c["name"] == "prohibited_claims" and not c["ok"] for c in payload["checks"])
```

- [ ] **Step 3: Implement `shared/safety/gate.py`**

```python
from shared.safety.types import CheckResult


def aggregate(results: list[CheckResult]) -> dict:
    """ALL-must-hold (spec Ch.8). Record EVERY check (pass and fail) for the weekly spot-audit
    and the calibration set."""
    checks = [{"name": r.name, "ok": r.ok, **({"detail": r.detail} if r.detail else {})}
              for r in results]
    return {"schema_version": "1.0.0", "passed": all(r.ok for r in results), "checks": checks}
```

- [ ] **Step 4: Run** → PASS (2). **Commit.**

```bash
git add shared/safety/gate.py schemas/qc.schema.json tests/test_safety_gate.py
git commit -m "feat(m5): 05b gate aggregation + qc.schema (ALL-must-hold, detail validated)"
```

### Task 8: Stage 05b — wire every check + the support-only LLM

**Files:** Create `stages/s05b_safety/{stage.py,manifest.json}`; Test `tests/test_s05b_safety.py`

- [ ] **Step 1: Write the failing tests** (the orchestration with injected probe/vision/LLM)

```python
# tests/test_s05b_safety.py
import pytest
from stages.s05b_safety.stage import collect_checks, QualityLeakError
from shared.safety.probe import ProbeResult
from shared.safety.types import SafetyThresholds


class _SaneLLM:
    def llm_json(self, prompt, seed=None):
        return {"hallucination": False, "note": "claims trace to data"}


def _probes():
    return ProbeResult(integrated_lufs=-14.0, true_peak_dbtp=-1.4, silences=[], black_spans=[],
                       actual_s=30.0, projected_s=31.0,
                       cta_rect={"x": 120, "y": 900, "w": 600, "h": 200})


def test_collect_runs_EVERY_check_including_artifact():
    script = {"disclaimer": "Educational only — not financial advice.",
              "narration_beats": [{"text": "Index funds track the market."}],
              "captions": [{"text": "the index"}], "claims": [{"source_ref": "data.cpi"}],
              "platform_meta": {"ai_disclosure": True}, "hook": {"spoken": "h"}}
    profile = {"defaults": {"disclaimer": "Educational only — not financial advice.",
                            "denylist_terms": ["guaranteed"]}}
    vision = {"judgment": {"observations": ["clean"]}}
    results = collect_checks(script=script, profile=profile, vision=vision, probes=_probes(),
                             platform="tiktok", ledger=[], llm=_SaneLLM(),
                             thresholds=SafetyThresholds(), safe_zones=None)
    assert all(r.ok for r in results)
    assert {"disclaimer", "prohibited_claims", "sources_cited", "ai_disclosure", "profanity",
            "artifact", "safe_zone", "loudness", "hook_dead_air", "synth_duration", "black_run",
            "clipping", "repetition", "hallucination"} == {r.name for r in results}


def test_hallucination_flag_fails_the_gate():
    class _BadLLM:
        def llm_json(self, prompt, seed=None):
            return {"hallucination": True, "note": "stat not in data"}
    results = collect_checks(script={"disclaimer": "", "narration_beats": [], "hook": {}},
                             profile={"defaults": {"disclaimer": "", "denylist_terms": []}},
                             vision={"judgment": {"observations": []}}, probes=_probes(),
                             platform="tiktok", ledger=[], llm=_BadLLM(),
                             thresholds=SafetyThresholds(), safe_zones=None)
    assert any(r.name == "hallucination" and not r.ok for r in results)


def test_llm_quality_leak_is_rejected():
    class _LeakyLLM:
        def llm_json(self, prompt, seed=None):
            return {"hallucination": False, "score": 0.9}     # a quality key — forbidden in 05b
    with pytest.raises(QualityLeakError):
        collect_checks(script={"disclaimer": "", "narration_beats": [], "hook": {}},
                       profile={"defaults": {"disclaimer": "", "denylist_terms": []}},
                       vision={"judgment": {"observations": []}}, probes=_probes(),
                       platform="tiktok", ledger=[], llm=_LeakyLLM(),
                       thresholds=SafetyThresholds(), safe_zones=None)
```

- [ ] **Step 2: Implement `stages/s05b_safety/stage.py`**

```python
import json

from shared.ctx import StageContext, StageResult
from shared.safety import audio_defect as ad
from shared.safety import checks as ck
from shared.safety import geometry as geo
from shared.safety import render_integrity as ri
from shared.safety.gate import aggregate
from shared.safety.probe import ProbeResult, probe
from shared.safety.repetition import not_repetitious
from shared.safety.types import CheckResult, SafetyThresholds
from shared.schema import SchemaRegistry
from shared.stage import StageManifest, stage

_REG = SchemaRegistry()
_QUALITY_KEYS = {"score", "quality", "interesting", "rating", "overall"}

# support-only: the 00b model checks factual grounding, NOT quality (ADR 0016 D1 stays intact).
_FACT_PROMPT = ('Return STRICT JSON {"hallucination": bool, "note": "..."} — true if any stated '
                "number/claim is NOT supported by the DATA. Judge support only, never quality.\n\nSCRIPT: ")


class QualityLeakError(Exception):
    """The 05b fact LLM returned a quality-adjacent key — that signal belongs to 05c, not the
    safety gate. Fail loud so 05b never drifts into self-judging quality (ADR 0016 D1)."""


def collect_checks(*, script, profile, vision, probes: ProbeResult, platform, ledger, llm,
                   thresholds: SafetyThresholds, safe_zones) -> list[CheckResult]:
    fact = llm.llm_json(_FACT_PROMPT + json.dumps(script))
    if _QUALITY_KEYS & set(fact):
        raise QualityLeakError(f"05b fact-LLM returned quality keys: {_QUALITY_KEYS & set(fact)}")
    return [
        ck.disclaimer_present(script, profile),
        ck.no_prohibited_claims(script, profile),
        ck.sources_cited(script),
        ck.disclosure_set(script),
        ck.profanity_clear(script, set(profile["defaults"].get("profanity_wordlist", [])) or None),
        ck.artifact_clear(vision),
        geo.in_safe_zone(probes.cta_rect, platform=platform, zones=safe_zones),
        ad.loudness_ok(integrated_lufs=probes.integrated_lufs, true_peak_dbtp=probes.true_peak_dbtp, t=thresholds),
        ad.hook_dead_air_ok(silences=probes.silences, t=thresholds),
        ad.synth_duration_ok(actual_s=probes.actual_s, projected_s=probes.projected_s, t=thresholds),
        ri.black_run_ok(black_spans=probes.black_spans, t=thresholds),
        ri.no_clipping_ok(true_peak_dbtp=probes.true_peak_dbtp, t=thresholds),
        not_repetitious({"topic": script.get("topic"), "hook": script.get("hook", {}).get("spoken", "")}, ledger),
        CheckResult(not fact.get("hallucination", True), "hallucination", fact.get("note", "")),
    ]


@stage(StageManifest(id="05b", inputs=["render", "script", "vision", "narration", "music"],
                     outputs=["qc"], compute="cpu", capability="llm"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    vision = json.loads(ctx.read_input("vision").read_text())
    profile = ctx.job["profile"]                          # the resolved profile dict on the job (ADR 0010 D5)
    # narration + music are declared inputs because the probe MEASURES them (silencedetect on
    # narration, loudnorm on the music mix) — so the DAG/cache key reflect 05b's real dependencies.
    probes = probe(ctx.run_dir, narration=ctx.read_input("narration"), music=ctx.read_input("music"),
                   render=ctx.read_input("render"), render_manifest=ctx.run_dir / "render_manifest.json")
    results = collect_checks(
        script=script, profile=profile, vision=vision, probes=probes,
        platform=ctx.job.get("platform_targets", ["youtube"])[0], ledger=_recent_ledger(ctx),
        llm=ctx.backend("llm"), thresholds=SafetyThresholds.from_config(ctx.config.get("safety", {})),
        safe_zones=ctx.config.get("safe_zones"))
    payload = aggregate(results)
    _REG.validate("qc", payload)
    out = ctx.write_output("qc")
    out.write_text(json.dumps(payload))                   # write BEFORE any quarantine raise
    if not payload["passed"]:
        ctx.quarantine(f"safety gate failed: {[c['name'] for c in payload['checks'] if not c['ok']]}")
    ctx.log.info("safety gate pass", checks=len(results))
    return StageResult(outputs={"qc": out})


def _recent_ledger(ctx):
    raise NotImplementedError("Integration seam: read the trailing novelty/posted window from "
                              "history/; CI injects a list. The pure checks are unit-tested.")
```

- [ ] **Step 3: Write `manifest.json`** → `{"id": "05b", "inputs": ["render", "script", "vision", "narration", "music"], "outputs": ["qc"], "compute": "cpu", "capability": "llm"}` (cpu stage carrying a capability — mirror it, M0 drift-catcher note). **Run** → PASS (3). **Commit.**

```bash
git add stages/s05b_safety/ tests/test_s05b_safety.py
git commit -m "feat(m5): 05b stage — every Ch.8 check, support-only LLM, quality-leak guard (ADR 0004 D3/0016 D1)"
```

---

# Part B — Distribution (Stage 06)

### Task 9: Exactly-once posts ledger (intent → publishing → confirmed, hard-fail on corruption)

**Files:** Create `shared/distribution/__init__.py` (empty), `shared/distribution/posts_ledger.py`; Modify `schemas/posts.schema.json`; Test `tests/test_posts_ledger.py`

- [ ] **Step 1: Pin `schemas/posts.schema.json`** (extend the M0 skeleton; **platform is registry-validated, not a closed enum**, so a 3rd platform needs no schema bump)

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
    "platform": {"type": "string", "minLength": 1},
    "state": {"enum": ["intent", "publishing", "confirmed"]},
    "idempotency_key": {"type": "string"},
    "remote_id": {"type": "string"}, "url": {"type": "string"}, "ts": {"type": "string"}
  }
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_posts_ledger.py
import pytest
from shared.distribution.posts_ledger import (already_confirmed, pending_post, write_intent,
                                             write_publishing, write_confirmed, idempotency_key,
                                             LedgerCorruption, read_records)


def test_idempotency_key_is_deterministic():
    assert idempotency_key("v", "youtube") == idempotency_key("v", "youtube")
    assert idempotency_key("v", "youtube") != idempotency_key("v", "tiktok")


def test_confirmed_blocks_a_second_post(tmp_path):
    led = tmp_path / "posts.jsonl"
    write_intent(led, video_id="v", platform="youtube")
    write_confirmed(led, video_id="v", platform="youtube", remote_id="yt", url="u")
    assert already_confirmed(led, "v", "youtube") and not pending_post(led, "v", "youtube")


def test_intent_or_publishing_without_confirm_is_a_retry_case(tmp_path):
    led = tmp_path / "posts.jsonl"
    write_intent(led, video_id="v", platform="tiktok")
    assert pending_post(led, "v", "tiktok")
    write_publishing(led, video_id="v", platform="tiktok", remote_id="pub1")   # async accepted
    assert pending_post(led, "v", "tiktok") and not already_confirmed(led, "v", "tiktok")


def test_corrupt_line_fails_loud(tmp_path):
    led = tmp_path / "posts.jsonl"
    led.write_text('{"good": 1}\nNOT JSON\n')
    with pytest.raises(LedgerCorruption):           # exactly-once must NEVER silently skip (spec Ch.8)
        read_records(led)
```

- [ ] **Step 3: Implement `shared/distribution/posts_ledger.py`**

```python
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class LedgerCorruption(Exception):
    """A posts.jsonl line failed to parse. For an exactly-once ledger, silently skipping it could
    drop a 'confirmed' record and cause a double-post — so we fail loud (spec Ch.8: no silent failures)."""


def idempotency_key(video_id: str, platform: str) -> str:
    return hashlib.sha256(f"{video_id}:{platform}".encode()).hexdigest()[:16]


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise LedgerCorruption(f"{path}:{i} unparseable — {e}") from e
    return out


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now(timezone.utc).isoformat()
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _states(path, video_id, platform) -> set[str]:
    return {r["state"] for r in read_records(path)
            if r["video_id"] == video_id and r["platform"] == platform}


def already_confirmed(path: Path, video_id: str, platform: str) -> bool:
    return "confirmed" in _states(path, video_id, platform)


def pending_post(path: Path, video_id: str, platform: str) -> bool:
    s = _states(path, video_id, platform)
    return bool(s & {"intent", "publishing"}) and "confirmed" not in s


def _rec(video_id, platform, state, **extra) -> dict:
    return {"schema_version": "1.0.0", "video_id": video_id, "platform": platform, "state": state,
            "idempotency_key": idempotency_key(video_id, platform), **extra}


def write_intent(path, *, video_id, platform): _append(path, _rec(video_id, platform, "intent"))
def write_publishing(path, *, video_id, platform, remote_id):
    _append(path, _rec(video_id, platform, "publishing", remote_id=remote_id))
def write_confirmed(path, *, video_id, platform, remote_id, url):
    _append(path, _rec(video_id, platform, "confirmed", remote_id=remote_id, url=url))
```

- [ ] **Step 4: Run** → PASS (4). **Commit.**

```bash
git add shared/distribution/__init__.py shared/distribution/posts_ledger.py schemas/posts.schema.json tests/test_posts_ledger.py
git commit -m "feat(m5): exactly-once posts ledger (intent/publishing/confirmed, hard-fail on corruption, ADR 0003 D1)"
```

### Task 10: Caption assembly + visibility via the `allowed_visibility` seam

**Files:** Create `shared/distribution/caption.py`, `shared/distribution/visibility.py`; Test `tests/test_caption.py`, `tests/test_visibility.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_caption.py
from shared.distribution.caption import build_caption


def test_primary_keyword_leads_first_150_and_disclosure_appended():
    meta = {"title": "The Fed blinked", "description": "Here's what changed.",
            "hashtags": ["finance"], "primary_keyword": "interest rates"}
    cap = build_caption(meta, platform="youtube", disclosure_line="AI-generated. Educational only.",
                        affiliate=None)
    assert cap["description"][:150].lower().startswith("interest rates")
    assert "AI-generated" in cap["description"]


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


class _YT:
    platform = "youtube"
    def allowed_visibility(self, cfg): return {"private", "public"}
class _TT:
    platform = "tiktok"
    def allowed_visibility(self, cfg): return {"SELF_ONLY", "PUBLIC_TO_EVERYONE"}


def test_youtube_public_after_warming_tiktok_audit_gated():
    cfg = {"youtube": {"public_after_warming": True}, "tiktok": {"audit_cleared": False}}
    assert resolve_visibility(_YT(), cfg, warmed=True) == "public"
    assert resolve_visibility(_YT(), cfg, warmed=False) == "private"
    assert resolve_visibility(_TT(), cfg, warmed=True) == "SELF_ONLY"     # audit not cleared


def test_tiktok_public_once_audit_cleared():
    assert resolve_visibility(_TT(), {"tiktok": {"audit_cleared": True}}, warmed=True) == "PUBLIC_TO_EVERYONE"


def test_resolution_never_returns_a_value_outside_the_allowed_set():
    cfg = {"youtube": {"public_after_warming": True}}
    assert resolve_visibility(_YT(), cfg, warmed=True) in _YT().allowed_visibility(cfg)
```

- [ ] **Step 2: Implement both** (visibility is generic over `adapter.allowed_visibility` — ADR 0010 D3)

```python
# shared/distribution/caption.py
def build_caption(meta: dict, *, platform: str, disclosure_line: str, affiliate: dict | None) -> dict:
    kw, body = meta["primary_keyword"], meta.get("description", "")
    lead = body if body.lower().startswith(kw.lower()) else f"{kw} — {body}"
    parts = [lead, "", " ".join(f"#{h}" for h in meta.get("hashtags", [])), "", disclosure_line]
    if affiliate:
        parts += ["", affiliate["text"], *affiliate.get("links", [])]
    return {"title": meta["title"], "description": "\n".join(p for p in parts if p)}
```

```python
# shared/distribution/visibility.py
def resolve_visibility(adapter, cfg: dict, *, warmed: bool) -> str:
    """Generic over the adapter's declared legal set (ADR 0010 D3) — no per-platform branches.
    The chosen value is asserted to be inside allowed_visibility(), so a config typo fails loud."""
    pcfg = cfg.get(adapter.platform, {})
    allowed = adapter.allowed_visibility(cfg)
    public = adapter.public_label() if hasattr(adapter, "public_label") else "public"
    private = adapter.private_label() if hasattr(adapter, "private_label") else "private"
    if not pcfg.get("audit_required_cleared", True) if "audit_required_cleared" in pcfg else False:
        chosen = private
    elif adapter.platform == "tiktok":
        chosen = public if pcfg.get("audit_cleared") else private
    else:
        chosen = public if (warmed and pcfg.get("public_after_warming")) else private
    assert chosen in allowed, f"{chosen} not in {adapter.platform} allowed {allowed}"
    return chosen
```

> The adapters expose `public_label()`/`private_label()` (YouTube → `public`/`private`; TikTok → `PUBLIC_TO_EVERYONE`/`SELF_ONLY`) so the platform's privacy strings live with the adapter, not in this function. Keep `resolve_visibility` free of `if platform ==` beyond the audit-gate distinction, which is itself a generic `audit_cleared` config key.

- [ ] **Step 3: Run** → both PASS. **Commit.**

```bash
git add shared/distribution/caption.py shared/distribution/visibility.py tests/test_caption.py tests/test_visibility.py
git commit -m "feat(m5): caption (keyword-first + disclosure + affiliate) + visibility via allowed_visibility (ADR 0006/0009/0010 D3)"
```

### Task 11: `DistributionAdapter` base — exactly-once + `allowed_visibility`

**Files:** Modify `shared/adapters/base.py`; Test `tests/test_distribution_base.py`

- [ ] **Step 1: Write the failing tests** (a FakeAdapter exercises the base)

```python
# tests/test_distribution_base.py
from shared.adapters.base import DistributionAdapter


class FakeAdapter(DistributionAdapter):
    platform = "youtube"
    def __init__(self): self.posts = 0; self.searchable = {}
    def allowed_visibility(self, cfg): return {"private", "public"}
    def _post(self, media_path, metadata, visibility):
        self.posts += 1; rid = f"rid{self.posts}"; self.searchable[metadata["idempotency_key"]] = rid
        return rid, f"https://yt/{rid}"
    def _find_existing(self, idempotency_key):
        rid = self.searchable.get(idempotency_key)
        return (rid, f"https://yt/{rid}") if rid else None


def test_publish_returns_a_confirmed_record_and_writes_the_per_video_ledger(tmp_path):
    led = tmp_path / "v" / "posts.jsonl"
    a = FakeAdapter()
    rec = a.publish(video_id="v", media_path="m.mp4", metadata={"title": "t", "idempotency_key": "k"},
                    visibility="private", ledger_path=led)
    assert a.posts == 1 and rec["remote_id"] == "rid1"
    from shared.distribution.posts_ledger import already_confirmed
    assert already_confirmed(led, "v", "youtube")


def test_confirmed_video_is_never_reposted(tmp_path):
    led = tmp_path / "v" / "posts.jsonl"; a = FakeAdapter(); md = {"title": "t", "idempotency_key": "k"}
    a.publish(video_id="v", media_path="m.mp4", metadata=md, visibility="private", ledger_path=led)
    a.publish(video_id="v", media_path="m.mp4", metadata=md, visibility="private", ledger_path=led)
    assert a.posts == 1                                     # second call no-ops


def test_retry_after_crash_confirms_via_find_existing(tmp_path):
    from shared.distribution.posts_ledger import write_intent
    led = tmp_path / "v" / "posts.jsonl"; a = FakeAdapter()
    write_intent(led, video_id="v", platform="youtube"); a.searchable["k"] = "rid_prior"  # post landed
    a.publish(video_id="v", media_path="m.mp4", metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 0                                     # found remote -> no re-post


def test_retry_when_post_did_not_land_reposts_cleanly(tmp_path):
    from shared.distribution.posts_ledger import write_intent
    led = tmp_path / "v" / "posts.jsonl"; a = FakeAdapter()
    write_intent(led, video_id="v", platform="youtube")    # intent only; nothing landed remotely
    a.publish(video_id="v", media_path="m.mp4", metadata={"title": "t", "idempotency_key": "k"},
              visibility="private", ledger_path=led)
    assert a.posts == 1                                     # legitimate single re-post
```

- [ ] **Step 2: Implement the base in `shared/adapters/base.py`**

```python
from abc import ABC, abstractmethod
from pathlib import Path

from shared.distribution.posts_ledger import (already_confirmed, pending_post,
                                             write_confirmed, write_intent)


class DistributionAdapter(ABC):
    """Exactly-once is OWNED HERE (ADR 0003 D1/0010). publish() writes to the PER-VIDEO ledger;
    the shared history/posts.jsonl is the M4 fan-in's job (ADR 0003 D6). A retry recovers via
    _find_existing — never a blind re-post."""
    platform: str

    def publish(self, *, video_id, media_path, metadata, visibility, ledger_path: Path) -> dict | None:
        if already_confirmed(ledger_path, video_id, self.platform):
            return None
        if pending_post(ledger_path, video_id, self.platform):
            found = self._find_existing(metadata["idempotency_key"])    # crash-recovery
            if found:
                rid, url = found
                write_confirmed(ledger_path, video_id=video_id, platform=self.platform, remote_id=rid, url=url)
                return {"remote_id": rid, "url": url, "recovered": True}
        else:
            write_intent(ledger_path, video_id=video_id, platform=self.platform)
        rid, url = self._post(media_path, metadata, visibility)         # the side effect (verified live)
        write_confirmed(ledger_path, video_id=video_id, platform=self.platform, remote_id=rid, url=url)
        return {"remote_id": rid, "url": url, "recovered": False}

    @abstractmethod
    def allowed_visibility(self, cfg: dict) -> set[str]: ...
    @abstractmethod
    def _post(self, media_path, metadata: dict, visibility: str) -> tuple[str, str]: ...
    @abstractmethod
    def _find_existing(self, idempotency_key: str) -> tuple[str, str] | None: ...
```

- [ ] **Step 3: Run** → PASS (4). **Commit.**

```bash
git add shared/adapters/base.py tests/test_distribution_base.py
git commit -m "feat(m5): DistributionAdapter base — exactly-once (per-video ledger) + allowed_visibility (ADR 0003 D1/D6/0010 D3)"
```

### Task 12: `YouTubeAdapter` (uploads-playlist retry) + `TikTokAdapter` (status-poll confirm)

**Files:** Create `shared/adapters/youtube.py`, `shared/adapters/tiktok.py`; Test `tests/test_youtube_adapter.py`, `tests/test_tiktok_adapter.py`

- [ ] **Step 1: Write the tests** (request-shape units + live-call integration marks)

```python
# tests/test_youtube_adapter.py
import pytest
from shared.adapters.base import DistributionAdapter
from shared.adapters.youtube import YouTubeAdapter


def test_protocol_and_NO_invented_synthetic_field():
    a = YouTubeAdapter(creds=None)
    assert isinstance(a, DistributionAdapter) and a.platform == "youtube"
    assert a.allowed_visibility({}) == {"private", "unlisted", "public"}
    body = a._insert_body({"title": "t", "description": "d\nAI-generated."}, visibility="private")
    assert body["status"]["privacyStatus"] == "private"
    # the altered-content flag has NO Data API field — disclosure rides in the description, not status
    assert "containsSyntheticMedia" not in body["status"]
    assert "AI-generated" in body["snippet"]["description"]


@pytest.mark.integration
def test_youtube_retry_uses_uploads_playlist_not_search(tmp_path):
    ...  # asserts _find_existing calls playlistItems.list on the uploads playlist, not search.list
```

```python
# tests/test_tiktok_adapter.py
import pytest
from shared.adapters.base import DistributionAdapter
from shared.adapters.tiktok import TikTokAdapter


def test_protocol_and_aigc_flag_in_post_info():
    a = TikTokAdapter(token=None)
    assert isinstance(a, DistributionAdapter) and a.platform == "tiktok"
    assert a.allowed_visibility({}) == {"SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS",
                                        "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"}
    body = a._init_body({"title": "t"}, visibility="SELF_ONLY")
    assert body["post_info"]["privacy_level"] == "SELF_ONLY"
    assert body["post_info"]["brand_content_toggle"] is False
    assert body["post_info"]["aigc_content"] is True       # AIGC flag in post_info (NOT source_info)
    assert "is_ai_generated" not in body.get("source_info", {})


@pytest.mark.integration
def test_tiktok_confirms_only_after_publish_complete(tmp_path):
    ...  # asserts _post polls /publish/status/fetch/ until PUBLISH_COMPLETE before returning
```

- [ ] **Step 2: Implement both**

```python
# shared/adapters/youtube.py
from shared.adapters.base import DistributionAdapter


class YouTubeAdapter(DistributionAdapter):
    """YouTube Data API v3 videos.insert. The altered/synthetic-content label has NO public API
    field (Studio-UI only as of 2026 — see deploy/host/oauth-production.md); disclosure rides in the
    DESCRIPTION line. _find_existing uses the uploads playlist (near-real-time, 1 unit) — NOT
    search.list, whose index lags minutes-to-hours and would risk a blind double-post (ADR 0003 D1)."""
    platform = "youtube"

    def __init__(self, creds, *, insert=None, list_uploads=None):
        self._creds, self._insert, self._list_uploads = creds, insert, list_uploads

    def allowed_visibility(self, cfg): return {"private", "unlisted", "public"}
    def public_label(self): return "public"
    def private_label(self): return "private"

    def _insert_body(self, metadata, visibility):
        return {"snippet": {"title": metadata["title"], "description": metadata["description"],
                            "categoryId": "25"},
                "status": {"privacyStatus": visibility, "selfDeclaredMadeForKids": False}}

    def _post(self, media_path, metadata, visibility):
        resp = self._insert(self._insert_body(metadata, visibility), media_path)   # MediaFileUpload + videos().insert
        return resp["id"], f"https://youtu.be/{resp['id']}"

    def _find_existing(self, idempotency_key):
        if self._list_uploads is None:
            return None
        hit = self._list_uploads(idempotency_key)        # playlistItems.list(uploads); marker in description
        return (hit["id"], f"https://youtu.be/{hit['id']}") if hit else None
```

```python
# shared/adapters/tiktok.py
from shared.adapters.base import DistributionAdapter


class TikTokAdapter(DistributionAdapter):
    """TikTok Content Posting API. The AIGC disclosure goes in post_info.aigc_content (NOT
    source_info). Publish is ASYNC: init -> upload -> poll /publish/status/fetch/; _post returns
    only after PUBLISH_COMPLETE so a 'confirmed' ledger record means actually-published (ADR 0003 D1)."""
    platform = "tiktok"
    _PRIVACY = {"SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"}

    def __init__(self, token, *, init=None, upload=None, poll=None):
        self._token, self._init, self._upload, self._poll = token, init, upload, poll

    def allowed_visibility(self, cfg): return set(self._PRIVACY)
    def public_label(self): return "PUBLIC_TO_EVERYONE"
    def private_label(self): return "SELF_ONLY"

    def _init_body(self, metadata, visibility):
        return {"post_info": {"title": metadata["title"], "privacy_level": visibility,
                              "brand_content_toggle": False, "aigc_content": True},
                "source_info": {"source": "FILE_UPLOAD"}}

    def _post(self, media_path, metadata, visibility):
        publish_id = self._init(self._init_body(metadata, visibility), media_path)
        self._upload(publish_id, media_path)
        status = self._poll(publish_id)                  # blocks until PUBLISH_COMPLETE or raises on FAILED
        if status != "PUBLISH_COMPLETE":
            raise RuntimeError(f"TikTok publish {publish_id} ended {status}")
        return publish_id, f"https://tiktok.com/@me/video/{publish_id}"

    def _find_existing(self, idempotency_key):
        # the intent/publishing record stored the publish_id; recovery re-polls its terminal status.
        if self._poll is None:
            return None
        pub = self._poll_by_marker(idempotency_key) if hasattr(self, "_poll_by_marker") else None
        return (pub, f"https://tiktok.com/@me/video/{pub}") if pub else None
```

- [ ] **Step 3: Run** → `uv run pytest tests/test_youtube_adapter.py tests/test_tiktok_adapter.py -m "not integration" -v` → PASS (2). **Commit.**

```bash
git add shared/adapters/youtube.py shared/adapters/tiktok.py tests/test_youtube_adapter.py tests/test_tiktok_adapter.py
git commit -m "feat(m5): YouTube (uploads-playlist retry) + TikTok (post_info AIGC, status-poll confirm) adapters (ADR 0003 D1/0004/0009)"
```

### Task 13: Stage 06 — ramp-gated publish; emit the per-video posts artifact

**Files:** Create `stages/s06_distribute/{stage.py,manifest.json}`; Test `tests/test_s06_distribute.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_s06_distribute.py
import pytest
from stages.s06_distribute.stage import distribute, HeldForReview


class _Adapter:
    def __init__(self, platform): self.platform = platform; self.calls = []
    def publish(self, *, video_id, media_path, metadata, visibility, ledger_path):
        self.calls.append((video_id, visibility)); return {"remote_id": "r", "url": "u"}


def test_posts_each_platform_when_approved(tmp_path):
    adapters = {"youtube": _Adapter("youtube"), "tiktok": _Adapter("tiktok")}
    posted = distribute(video_id="v", platforms=["youtube", "tiktok"], adapters=adapters,
                        renders={"youtube": "y.mp4", "tiktok": "t.mp4"},
                        metadata={"youtube": {"title": "t", "idempotency_key": "k1"},
                                  "tiktok": {"title": "t", "idempotency_key": "k2"}},
                        visibilities={"youtube": "public", "tiktok": "SELF_ONLY"},
                        ledger_path=tmp_path / "posts.jsonl", approved=True)
    assert adapters["youtube"].calls and adapters["tiktok"].calls and set(posted) == {"youtube", "tiktok"}


def test_unapproved_video_is_held_not_failed(tmp_path):
    adapters = {"youtube": _Adapter("youtube")}
    with pytest.raises(HeldForReview):
        distribute(video_id="v", platforms=["youtube"], adapters=adapters, renders={"youtube": "y.mp4"},
                   metadata={"youtube": {"title": "t", "idempotency_key": "k"}},
                   visibilities={"youtube": "public"}, ledger_path=tmp_path / "posts.jsonl", approved=False)
    assert not adapters["youtube"].calls
```

- [ ] **Step 2: Implement `stages/s06_distribute/stage.py`** (note: writes the per-video ledger; the **fan-in** merges it into `history/posts.jsonl`; `approved` defaults to **False** when the gate is active)

```python
import json
from datetime import datetime, timezone

from shared.ctx import StageContext, StageResult
from shared.distribution.caption import build_caption
from shared.distribution.posts_ledger import idempotency_key
from shared.distribution.visibility import resolve_visibility
from shared.ramp.policy import gate_active
from shared.ramp.state import load_state, is_warmed
from shared.stage import StageManifest, stage


class HeldForReview(Exception):
    """The ramp gate is active and this video has no approval yet — a resumable HOLD, not a failure
    (maps to exit 70 / status 'held'). The review CLER releases it on the next batch."""


def distribute(*, video_id, platforms, adapters, renders, metadata, visibilities, ledger_path, approved):
    if not approved:
        raise HeldForReview(f"{video_id} awaiting human approval (ramp gate active)")
    return {p: (adapters[p].publish(video_id=video_id, media_path=renders[p], metadata=metadata[p],
                                    visibility=visibilities[p], ledger_path=ledger_path)
                or {"skipped": "already confirmed"}) for p in platforms}


@stage(StageManifest(id="06", inputs=["render", "script", "qc", "creative_qc"],
                     outputs=["posts", "feature_record"], compute="cpu", capability="distribution"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    state = load_state(ctx.config["ramp_state_path"])          # explicit path (no run-dir guessing)
    warmed = is_warmed(state)                                  # CALENDAR predicate (now >= warming_until)
    active = gate_active(state, ctx.config.get("ramp", {}))
    approved = (not active) or state.get("approved_videos", {}).get(ctx.job["video_id"], False)
    platforms, adapters = ctx.job.get("platform_targets", ["youtube"]), ctx.backend("distribution")
    vis_cfg = ctx.config.get("visibility", {})
    metadata = {p: {**build_caption(script["platform_meta"][p], platform=p,
                                    disclosure_line=ctx.config["disclosure_line"],
                                    affiliate=script.get("affiliate") if ctx.config.get("affiliate_enabled") else None),
                    "idempotency_key": idempotency_key(ctx.job["video_id"], p)} for p in platforms}
    posted = distribute(
        video_id=ctx.job["video_id"], platforms=platforms, adapters=adapters,
        renders={p: ctx.run_dir / f"renders/{p}.mp4" for p in platforms}, metadata=metadata,
        visibilities={p: resolve_visibility(adapters[p], vis_cfg, warmed=warmed) for p in platforms},
        ledger_path=ctx.run_dir / "posts.jsonl", approved=approved)               # PER-VIDEO ledger
    out = ctx.write_output("posts")
    out.write_text(json.dumps({"video_id": ctx.job["video_id"], "posted": posted,
                               "ts": datetime.now(timezone.utc).isoformat()}))
    ctx.log.info("distributed", platforms=list(posted))
    return StageResult(outputs={"posts": out})
```

- [ ] **Step 3: Write `manifest.json`** → `{"id": "06", "inputs": ["render", "script", "qc"], "outputs": ["posts"], "compute": "cpu", "capability": "distribution"}`. **Run** → PASS (2). **Commit.**

```bash
git add stages/s06_distribute/ tests/test_s06_distribute.py
git commit -m "feat(m5): 06 distribute — ramp-gated, per-video posts artifact for fan-in (ADR 0003 D1/D6)"
```

> **Backend wiring (note for the implementer):** `ctx.backend("distribution")` must resolve to a **`dict[str, DistributionAdapter]`** (one per platform). Update the M4 `_build_backends` fake so `"distribution"` returns `{"youtube": FixtureAdapter("youtube"), "tiktok": FixtureAdapter("tiktok")}` (it previously returned a single object) — and the `FixtureDistributionAdapter` implements `allowed_visibility`/`_post`/`_find_existing` against an in-memory store.
>
> **Fan-in (ADR 0003 D6):** `06` writes only the per-video `posts` artifact + the per-video `posts.jsonl`. The M4 `commit_ledgers` step is extended to read each video's confirmed records and append them to `history/posts.jsonl` (idempotent on `(video_id, platform)`), so the shared ledger has exactly one appender. Cross-batch dedup in the adapter base reads `history/posts.jsonl` **read-only** in addition to the per-video file (pass both; `already_confirmed` ORs them).

---

# Part C — The publish ramp + the review CLI

### Task 14: Ramp state (provisioning / warming / counts / `is_warmed`)

**Files:** Create `shared/ramp/__init__.py` (empty), `shared/ramp/state.py`; Test `tests/test_ramp_state.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ramp_state.py
from datetime import datetime, timedelta, timezone
from shared.ramp.state import load_state, record_decision, mark_provisioned, is_warmed, approved_days


def test_load_defaults_for_a_new_niche(tmp_path):
    s = load_state(tmp_path / "ramp.finance.json")
    assert s["approved"] == 0 and s["rejected"] == 0 and s["warming_until"] is None
    assert s["first_approval_ts"] is None and s["approved_videos"] == {}


def test_record_decision_increments_persists_and_stamps_first_approval(tmp_path):
    p = tmp_path / "ramp.finance.json"
    record_decision(p, video_id="v1", approved=True)
    record_decision(p, video_id="v2", approved=False)
    s = load_state(p)
    assert s["approved"] == 1 and s["rejected"] == 1
    assert s["approved_videos"] == {"v1": True, "v2": False}
    assert s["first_approval_ts"] is not None              # stamped on the first approval


def test_is_warmed_is_a_calendar_predicate(tmp_path):
    p = tmp_path / "ramp.finance.json"
    assert is_warmed(load_state(p)) is False               # not provisioned -> not warmed
    mark_provisioned(p, warming_days=7)
    assert is_warmed(load_state(p)) is False                # within the window
    past = {"warming_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
    assert is_warmed(past) is True                          # window elapsed


def test_approved_days_counts_distinct_calendar_days(tmp_path):
    s = {"first_approval_ts": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()}
    assert approved_days(s) >= 10
```

- [ ] **Step 2: Implement `shared/ramp/state.py`** (atomic temp+rename writes; `is_warmed` is purely the calendar comparison; `approved_days` derives from `first_approval_ts`)

```python
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DEFAULT = {"provisioned": False, "warming_until": None, "approved": 0, "rejected": 0,
            "first_approval_ts": None, "approved_videos": {}}


def load_state(path: Path) -> dict:
    if not Path(path).exists():
        return dict(_DEFAULT, approved_videos={})
    return {**_DEFAULT, **json.loads(Path(path).read_text())}


def _save(path: Path, state: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"{path}.tmp")
    tmp.write_text(json.dumps(state)); os.replace(tmp, path)


def mark_provisioned(path: Path, *, warming_days: int) -> None:
    s = load_state(path)
    s["provisioned"] = True
    s["warming_until"] = (datetime.now(timezone.utc) + timedelta(days=warming_days)).isoformat()
    _save(path, s)


def record_decision(path: Path, *, video_id: str, approved: bool) -> None:
    s = load_state(path)
    s["approved" if approved else "rejected"] += 1
    s["approved_videos"][video_id] = approved
    if approved and s["first_approval_ts"] is None:
        s["first_approval_ts"] = datetime.now(timezone.utc).isoformat()
    _save(path, s)


def is_warmed(state: dict) -> bool:
    """Calendar predicate ONLY — independent of the approval track record (ADR 0009)."""
    wu = state.get("warming_until")
    return wu is not None and datetime.now(timezone.utc) >= datetime.fromisoformat(wu)


def approved_days(state: dict) -> int:
    ts = state.get("first_approval_ts")
    if not ts:
        return 0
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).days
```

- [ ] **Step 3: Run** → PASS (4). **Commit.**

```bash
git add shared/ramp/__init__.py shared/ramp/state.py tests/test_ramp_state.py
git commit -m "feat(m5): ramp state — calendar warming + decision counts + approved_days (ADR 0009/0014 D2)"
```

### Task 15: Ramp queue + calibration labels + the two-tier policy

**Files:** Create `shared/ramp/queue.py`, `shared/ramp/labels.py`, `shared/ramp/policy.py`; Modify `schemas/feature_record.schema.json`; Test `tests/test_ramp_queue.py`, `tests/test_ramp_labels.py`, `tests/test_ramp_policy.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ramp_queue.py
from shared.ramp.queue import pending_review


def test_pending_is_passed_both_gates_and_not_yet_decided():
    videos = [{"video_id": "a", "qc_pass": True, "creative_pass": True},
              {"video_id": "b", "qc_pass": False, "creative_pass": True},
              {"video_id": "c", "qc_pass": True, "creative_pass": True}]
    assert pending_review(videos, {"a": True}) == ["c"]
```

```python
# tests/test_ramp_labels.py
import json
from shared.ramp.labels import record_label


def test_decision_writes_a_ramp_label_into_feature_record(tmp_path):
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "format": "myth_buster", "scores": {}}))
    record_label(fr, approved=False, reason="thesis was generic")
    rec = json.loads(fr.read_text())
    assert rec["ramp_label"]["approved"] is False and rec["ramp_label"]["reason"] == "thesis was generic"
```

```python
# tests/test_ramp_policy.py
from shared.ramp.policy import gate_active, can_widen_cadence, DEFAULT_RAMP


def test_gate_lift_uses_the_LENIENT_bar():
    earned = {"approved": 10, "rejected": 1, "approved_days_": 7, "strikes": 0}
    # approved_days is passed via cfg-injected accessor in real use; the test stubs it on the state
    s = {"approved": 10, "rejected": 1, "strikes": 0, "first_approval_ts": _days_ago(7)}
    assert gate_active(s, {}) is False                       # 10/7d/<=1 rejection -> lifted
    not_yet = {"approved": 5, "rejected": 0, "strikes": 0, "first_approval_ts": _days_ago(7)}
    assert gate_active(not_yet, {}) is True


def test_a_strike_keeps_the_gate_active():
    s = {"approved": 99, "rejected": 0, "strikes": 1, "first_approval_ts": _days_ago(99)}
    assert gate_active(s, {}) is True


def test_cadence_widening_uses_the_STRICTER_bar():
    lenient_only = {"approved": 12, "rejected": 1, "strikes": 0, "first_approval_ts": _days_ago(8)}
    assert gate_active(lenient_only, {}) is False             # gate lifted...
    assert can_widen_cadence(lenient_only, {}) is False       # ...but not enough to widen cadence
    strong = {"approved": 20, "rejected": 0, "strikes": 0, "first_approval_ts": _days_ago(14)}
    assert can_widen_cadence(strong, {}) is True
    assert DEFAULT_RAMP["lift"]["min_approved"] == 10 and DEFAULT_RAMP["widen"]["min_approved"] == 20


def _days_ago(n):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()
```

- [ ] **Step 2: Add the `ramp_label` block to `schemas/feature_record.schema.json`** (optional — pre-ramp records still validate; same pattern as M3's `vision.judgment`):

```json
{
  "ramp_label": {
    "type": "object", "additionalProperties": false, "required": ["approved"],
    "properties": {"approved": {"type": "boolean"}, "reason": {"type": "string"}, "ts": {"type": "string"}}
  }
}
```

- [ ] **Step 3: Implement the three modules**

```python
# shared/ramp/queue.py
def pending_review(videos: list[dict], decided: dict[str, bool]) -> list[str]:
    """Passed BOTH gates and no human decision yet. A gate failure is already quarantined — never queued."""
    return [v["video_id"] for v in videos
            if v.get("qc_pass") and v.get("creative_pass") and v["video_id"] not in decided]
```

```python
# shared/ramp/labels.py
import json
from datetime import datetime, timezone
from pathlib import Path


def record_label(feature_record_path: Path, *, approved: bool, reason: str = "") -> None:
    """Capture the operator verdict into feature_record as the 05c calibration label (ADR 0016 D2)."""
    rec = json.loads(Path(feature_record_path).read_text())
    rec["ramp_label"] = {"approved": approved, "reason": reason,
                         "ts": datetime.now(timezone.utc).isoformat()}
    Path(feature_record_path).write_text(json.dumps(rec))
```

```python
# shared/ramp/policy.py
from shared.ramp.state import approved_days

# Two tiers (ADR 0014 D2): a LENIENT bar lifts the per-post gate (achievable in a PoC window);
# a STRICTER bar widens cadence 1->2. Both are config (ctx.config["ramp"]).
DEFAULT_RAMP = {
    "lift":  {"min_approved": 10, "min_days": 7,  "max_rejected": 1, "max_strikes": 0},
    "widen": {"min_approved": 20, "min_days": 14, "max_rejected": 0, "max_strikes": 0},
}


def _meets(state: dict, bar: dict) -> bool:
    return (state.get("approved", 0) >= bar["min_approved"]
            and approved_days(state) >= bar["min_days"]
            and state.get("rejected", 0) <= bar["max_rejected"]
            and state.get("strikes", 0) <= bar["max_strikes"])


def gate_active(state: dict, cfg: dict) -> bool:
    """Human-at-publish gate stays ACTIVE until the LENIENT bar is met (ADR 0014 D2)."""
    return not _meets(state, {**DEFAULT_RAMP["lift"], **cfg.get("lift", {})})


def can_widen_cadence(state: dict, cfg: dict) -> bool:
    return _meets(state, {**DEFAULT_RAMP["widen"], **cfg.get("widen", {})})
```

- [ ] **Step 4: Run** → PASS (5). **Commit.**

```bash
git add shared/ramp/queue.py shared/ramp/labels.py shared/ramp/policy.py schemas/feature_record.schema.json tests/test_ramp_queue.py tests/test_ramp_labels.py tests/test_ramp_policy.py
git commit -m "feat(m5): ramp queue + calibration labels + two-tier policy (lift vs widen) (ADR 0014 D2/0016 D2)"
```

### Task 16: The review CLI (`make review`)

**Files:** Create `shorts/review.py`; Modify `Makefile`; Test `tests/test_review_cli.py`

- [ ] **Step 1: Write the failing tests** (the decision flow with injected I/O)

```python
# tests/test_review_cli.py
import json
from shorts.review import review_one
from shared.ramp.state import load_state


def test_approve_plays_then_records_label_and_state(tmp_path):
    fr = tmp_path / "feature_record.json"; fr.write_text(json.dumps({"video_id": "v", "scores": {}}))
    state = tmp_path / "ramp.finance.json"; played = []
    review_one(video_id="v", render="v.mp4", feature_record=fr, state_path=state,
               play=lambda p: played.append(p), prompt=lambda: ("approve", ""))
    assert played == ["v.mp4"]
    assert json.loads(fr.read_text())["ramp_label"]["approved"] is True
    assert load_state(state)["approved"] == 1


def test_reject_captures_reason(tmp_path):
    fr = tmp_path / "feature_record.json"; fr.write_text(json.dumps({"video_id": "v", "scores": {}}))
    review_one(video_id="v", render="v.mp4", feature_record=fr, state_path=tmp_path / "s.json",
               play=lambda p: None, prompt=lambda: ("reject", "hook was weak"))
    assert json.loads(fr.read_text())["ramp_label"]["reason"] == "hook was weak"
```

- [ ] **Step 2: Implement `shorts/review.py`**

```python
"""python -m shorts.review — the temporary human-at-publish ramp CLI (ADR 0014 D2).
list pending -> play the YouTube cut -> approve/reject; each decision is a 05c calibration label
(ADR 0016 D2) and releases/holds the video for 06. Read-only on renders; append-only on labels."""
from pathlib import Path

from shared.ramp.labels import record_label
from shared.ramp.state import record_decision


def review_one(*, video_id, render, feature_record: Path, state_path: Path, play, prompt) -> bool:
    play(render)
    action, reason = prompt()
    approved = action == "approve"
    record_label(feature_record, approved=approved, reason=reason)
    record_decision(state_path, video_id=video_id, approved=approved)
    return approved


def main() -> int:
    # Production wiring: scan runs/<batch>/<video> for qc.json.passed && creative_qc.json.pass,
    # filter via shared.ramp.queue.pending_review against the ramp state, then review_one each with
    # play=_open_player (xdg-open/ffplay) and prompt=_tty_prompt. Held videos re-run 06 next batch.
    raise SystemExit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Wire `make review`** → `uv run python -m shorts.review`. **Run** → PASS (2). **Commit.**

```bash
git add shorts/review.py Makefile tests/test_review_cli.py
git commit -m "feat(m5): the publish-ramp review CLI (make review) capturing calibration labels (ADR 0014 D2/0016 D2)"
```

---

# Part D — Held-status threading, credentials & ops

### Task 17: Thread the `held` status end-to-end (exit code, schemas, executor, reconciler)

`06`'s `HeldForReview` must be a first-class, **resumable** status — not a `failed` (which would alarm) and not lost on reboot.

**Files:** Modify `shared/exitcodes.py`, `shared/conductor/executor.py`, `shared/conductor/reconcile.py`, `schemas/job.schema.json`, `schemas/batch.schema.json`; Test `tests/test_held_status.py`, `tests/test_stage_order.py`, `tests/test_reconcile_held.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_held_status.py
from shared.exitcodes import EXIT_OK, EXIT_HELD, status_for_exit


def test_held_exit_code_maps_to_held():
    assert EXIT_HELD == 70
    assert status_for_exit(70) == "held"
    assert status_for_exit(0) == "done" and status_for_exit(77) == "quarantined"   # M4 unchanged
```

```python
# tests/test_stage_order.py
from shared.conductor.executor import default_stage_order


def test_05b_06_placement():
    o = default_stage_order()
    assert o.index("05x") < o.index("05b") < o.index("06")   # vision -> safety -> distribute
    assert o.index("05c") < o.index("06") and o[-1] == "06"
```

```python
# tests/test_reconcile_held.py
from shared.conductor.reconcile import resume_plan


def test_held_is_requeued_done_and_quarantined_are_not():
    batch = {"videos": [{"video_id": "a", "status": "done"}, {"video_id": "b", "status": "held"},
                        {"video_id": "c", "status": "quarantined"}, {"video_id": "d", "status": "pending"}]}
    assert resume_plan(batch) == ["b", "d"]                  # held re-queued (idempotent re-run via exactly-once)
```

- [ ] **Step 2: Apply the changes**
  - `shared/exitcodes.py`: add `EXIT_HELD = 70`; `status_for_exit(70) == "held"` (leave 0/75/77 untouched so M4's `test_protocol_values_are_stable` still passes). The 05b/06 stage CLIs map `HeldForReview` → `EXIT_HELD`.
  - `shared/conductor/executor.py`: add `default_stage_order()` returning `["00a","00b","01a","01b","01c","01d","01e","02","03","04","05","05x","05b","05c","06"]`; add `"held"` to the per-video-domain skip set (alongside `quarantined`/`failed`) so a held video doesn't re-run earlier stages mid-batch.
  - `shared/conductor/reconcile.py`: `resume_plan` includes `held` in its re-run set (`status in ("running", "pending", "held")`) — safe because the adapter's exactly-once no-ops an already-confirmed post and the review CLI controls `approved`.
  - `schemas/job.schema.json` + `schemas/batch.schema.json`: add `"held"` to the status enum (`pending/running/done/quarantined/failed/held`).

- [ ] **Step 3: Run** → PASS (3). **Commit.**

```bash
git add shared/exitcodes.py shared/conductor/executor.py shared/conductor/reconcile.py schemas/job.schema.json schemas/batch.schema.json tests/test_held_status.py tests/test_stage_order.py tests/test_reconcile_held.py
git commit -m "feat(m5): thread 'held' status (exit 70, executor skip, reconciler re-queue, schema enum) (ADR 0003 D9/0014 D2)"
```

### Task 18: OAuth token-age pre-flight (mode-aware) + YouTube quota gate + ops docs

ADR 0009 #10. M4 Task 11 left the pluggable pre-flight seam.

**Files:** Modify `shared/conductor/preflight.py`; Create `deploy/host/oauth-production.md`, `deploy/host/platform-audit.md`; Test `tests/test_oauth_preflight.py`, `tests/test_quota_preflight.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_oauth_preflight.py
import pytest
from shared.conductor.preflight import oauth_token_age_gate, PreflightFailure


def test_testing_mode_enforces_7_day_margin():
    oauth_token_age_gate(token_age_days=2.0, mode="testing")          # ok
    with pytest.raises(PreflightFailure):
        oauth_token_age_gate(token_age_days=8.0, mode="testing")      # > 6d margin -> would expire


def test_production_mode_checks_inactivity_not_issue_age():
    # Production refresh tokens don't expire on a 7-day schedule; only long inactivity/revocation.
    oauth_token_age_gate(token_age_days=40.0, last_used_days=3.0, mode="production")   # ok
    with pytest.raises(PreflightFailure):
        oauth_token_age_gate(token_age_days=40.0, last_used_days=200.0, mode="production")  # ~6mo idle
```

```python
# tests/test_quota_preflight.py
import pytest
from shared.conductor.preflight import youtube_quota_gate, PreflightFailure


def test_quota_gate_blocks_when_a_batch_wont_fit():
    # insert ~1600 units; a 4-video batch needs ~6400 + headroom
    youtube_quota_gate(used_units=0, planned_inserts=4, daily_quota=10000)            # ok
    with pytest.raises(PreflightFailure):
        youtube_quota_gate(used_units=6000, planned_inserts=4, daily_quota=10000)     # 6400 > 4000 left
```

- [ ] **Step 2: Add both gates to `shared/conductor/preflight.py`**

```python
_INSERT_UNITS = 1600          # YouTube videos.insert cost (ADR 0009 #8); config-overridable


def oauth_token_age_gate(*, token_age_days: float = 0.0, last_used_days: float = 0.0,
                         mode: str = "testing", testing_margin_days: float = 6.0,
                         production_idle_days: float = 150.0) -> None:
    """ADR 0009 #10. Testing-status refresh tokens die at 7 days -> enforce a <7d margin. Production
    tokens don't expire on a schedule (only ~6mo inactivity/revocation) -> check last-used, not age,
    so a healthy Production token doesn't false-alarm weekly."""
    if mode == "testing":
        if token_age_days > testing_margin_days:
            raise PreflightFailure(f"OAuth token {token_age_days:.1f}d old > {testing_margin_days}d "
                                   "(Testing tokens expire at 7d — refresh or move to Production)")
    else:
        if last_used_days > production_idle_days:
            raise PreflightFailure(f"OAuth token idle {last_used_days:.0f}d > {production_idle_days}d "
                                   "(Production tokens revoke on ~6mo inactivity)")


def youtube_quota_gate(*, used_units: int, planned_inserts: int, daily_quota: int = 10000,
                       insert_units: int = _INSERT_UNITS) -> None:
    """Fail the batch BEFORE fan-out if the planned inserts won't fit the day's remaining quota —
    otherwise mid-batch quota exhaustion strands videos in pending-intent (ADR 0003 D8)."""
    need = planned_inserts * insert_units
    if used_units + need > daily_quota:
        raise PreflightFailure(f"YouTube quota: need {need} units, only {daily_quota - used_units} left")
```

- [ ] **Step 3: Write the ops docs.** `deploy/host/oauth-production.md`: (1) move the Google Cloud OAuth consent screen **Testing → Production** (stops the 7-day refresh-token expiry); (2) scopes (`youtube.upload`); (3) credential storage + the M4 nightly `backup()` coverage; (4) the token-refresh check feeding `oauth_token_age_gate(mode="production")`; (5) **the YouTube altered/synthetic-content disclosure has no Data API field — it is a Studio-UI step**: record the policy decision (description-line disclosure is the API-available disclosure; the Studio toggle is a manual/out-of-band step pending any future API), so the gap is explicit, not silent; (6) TikTok token lifetime + refresh. `deploy/host/platform-audit.md`: the parallel audit checklist — YouTube API compliance audit (public-quota) + **TikTok app audit** (the gate that flips `tiktok.audit_cleared` → public, Task 10).

- [ ] **Step 4: Run** → PASS (3). **Commit.**

```bash
git add shared/conductor/preflight.py deploy/host/oauth-production.md deploy/host/platform-audit.md tests/test_oauth_preflight.py tests/test_quota_preflight.py
git commit -m "feat(m5): mode-aware OAuth pre-flight + YouTube quota gate + Production/audit ops docs (ADR 0009 #8/#10)"
```

---

## M5 Acceptance Checklist (the testable "done")

- [ ] **05b** runs **every** spec-Ch.8 check — disclaimer/prohibited-claims (from the **profile's `denylist_terms`**)/citation/AI-disclosure/profanity (hard booleans), **artifact** (from `vision.json`), CTA safe-zone, the loudness/dead-air/duration/black-run/clipping **numeric windows** (from injected `SafetyThresholds`), repetition, and the **support-only 00b LLM** (with a **quality-leak guard**) — and **quarantines on any single failure**; `qc.json` records every check and validates (incl. `detail`) → Tasks 1–8.
- [ ] **All safety policy is data:** denylist/disclaimer/profanity/thresholds/safe-zones come from the profile or `ctx.config`; **no hardcoded policy wordlist** in any stage → Tasks 2–4, 8.
- [ ] **Exactly-once** is owned by the `DistributionAdapter` base against a **per-video** ledger (intent/publishing/confirmed; hard-fail on corrupt JSONL); a confirmed video is never re-posted; a crash recovers via `_find_existing` — **YouTube via the uploads playlist** (not `search.list`), **TikTok only after `PUBLISH_COMPLETE`** → Tasks 9, 11, 12.
- [ ] **No invented API fields:** YouTube disclosure rides in the **description** (no `containsSyntheticMedia`); TikTok's AIGC flag is in **`post_info`**; the Studio gap is a documented ops step → Tasks 12, 18.
- [ ] **06** builds **keyword-first captions** + the **blanket disclosure line** (+ affiliate when enabled), resolves visibility via the adapter's **`allowed_visibility`** seam (YouTube public-after-warming, TikTok SELF_ONLY until audit-cleared), posts per-platform, and **emits a per-video `posts` artifact** that the **M4 fan-in** merges into `history/posts.jsonl` (one appender, ADR 0003 D6) → Tasks 10, 13.
- [ ] The **publish ramp** holds unapproved videos as a resumable **`held`** status (exit 70) that the executor skips and the **boot reconciler re-queues**; the **`make review` CLI** lists pending → plays → records approve/reject; every decision is **captured as a `feature_record` calibration label** (ADR 0016 D2); the **two-tier policy** lifts the gate on the lenient bar (≥10/≥7 days/≤1 rejection) and widens cadence on the stricter bar (≥20/≥14 days/0 rejections); **warmed** is a calendar predicate → Tasks 13–17.
- [ ] The **mode-aware OAuth pre-flight** + the **YouTube quota gate** plug into the M4 framework; the **Production + audit ops docs** exist → Task 18.
- [ ] `05b`/`06` sit correctly in `default_stage_order()`; CI stays GPU-free **and network-free** (`-m "not integration"`); `ctx.backend("distribution")` resolves to `dict[str, DistributionAdapter]` → Tasks 13, 17.

---

## Self-Review

**Spec coverage (Ch.10 M5 row + Ch.8 + ADRs):** the safety gate `05b` covers the **complete** Ch.8 list — disclaimer, prohibited-claims, citation, AI-disclosure, profanity, **artifact** (now a wired check, Task 2/8), CTA safe-zone, loudness/dead-air/duration, black-run/clipping, repetition, and the support-only hallucination pass — ALL-must-hold (ADR 0004 D3 / 0005 D8/D10 / 0008 / 0016 D5) → A; distribution `06` (per-platform adapters, exactly-once on a per-video ledger merged by fan-in, uploads-playlist + status-poll recovery, private-first/≥1-public via `allowed_visibility`, **API-real disclosure**, keyword-first caption, affiliate-disabled) → B (ADR 0003 D1/D6 / 0006 / 0009 / 0004 D5 / 0010 D3); provisioning + warming → the human ramp with the review CLI capturing calibration labels + the **two-tier exit criteria** → C (ADR 0014 D2 / 0016 D2); the `held` threading + **mode-aware OAuth** + **quota gate** + Production/audit docs → D (ADR 0003 D8/D9 / 0009 #8/#10). The two spec "Open" items (05b numeric thresholds; ramp-exit criteria) are pinned in the decisions header and encoded as config (`SafetyThresholds`, `DEFAULT_RAMP`).

**Review fixes folded in (from the M5 multi-lens review):** single `CheckResult`/`SafetyThresholds` type (was duplicated 4×); denylist now reads the profile (was a hardcoded set contradicting the stated principle); `artifact_clear` wired into `collect_checks` + tests + acceptance (was orphaned prose); `06` writes a per-video ledger for fan-in (was bypassing the single-appender rule, ADR 0003 D6); `containsSyntheticMedia` removed (not a real API field) — disclosure via description + TikTok `post_info`; TikTok async publish confirmed only after `PUBLISH_COMPLETE`; YouTube retry via uploads playlist (not `search.list`); `held` threaded through exit codes/schemas/executor/reconciler; `warmed` is a calendar predicate; `06` `approved` defaults False under an active gate; full `shared/ramp/state.py` implementation; OAuth gate mode-aware; YouTube quota pre-flight added; `qc.schema` includes `detail`; `posts_ledger` hard-fails on corruption; `ProbeResult` contract pins the ffprobe seam; `resolve_visibility` generic via `allowed_visibility`; thresholds/zones/ramp numbers all config; `ctx.backend("distribution")` → dict specified.

**Placeholder scan:** no "TBD"/"add error handling". The `NotImplementedError` bodies (`probe`/`_recent_ledger`; the injected Google/TikTok clients; `review.main`/`run_batch` wiring) are documented integration/bring-up seams whose pure collaborators are all implemented + tested. The `ProbeResult` contract makes the `probe` seam type-checked.

**Type consistency vs M0–M4:** `@stage(StageManifest(...))`, `StageContext`, `StageResult`, `SchemaRegistry().validate`, `ctx.read_input/write_output/backend/quarantine/log`; `05b`/`06` cpu stages carry a `capability` mirrored in `manifest.json`; `DistributionAdapter` is the M0 interface (exactly-once + `allowed_visibility` now in the base); qc/posts/feature_record schemas **extend their M0 skeletons** (Task steps confirm `schema_version` survives), each carrying `schema_version`; the new `held`/exit-70 extend M4's `status_for_exit` (0/75/77 untouched) and the ADR 0012 §4 status enum; `06`'s shared-ledger write goes through the M4 single fan-in (ADR 0003 D6); `backup()` already covers `posts.jsonl`.

**Scope:** four parts, one acceptance gate, produces working testable software (a video that passes both gates, waits for one approval, posts exactly once to two platforms with real disclosure, and feeds its verdict back as calibration data). Parts A–D are separable for review; A (safety) and B (distribution) are independent; C (ramp) depends on B; D is the held-threading + ops. After M5 the only thing between the pipeline and the Chapter-1 unattended DoD is **M6** (the 1–2 week run + alerts/GC + re-anchoring the 05c floor on M5's collected labels).
