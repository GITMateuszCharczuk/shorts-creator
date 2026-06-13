import pytest

from shared.safety.probe import ProbeResult
from shared.safety.types import SafetyThresholds
from stages.s05b_safety.stage import QualityLeakError, collect_checks


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


def test_profanity_wordlist_unions_with_defaults_not_replaces():
    """A profile that adds a niche term ('shill') must NOT silently drop the global
    defaults ('damn'/'crap'). The gate must only ever get wider, never narrower."""
    script = {"disclaimer": "Educational only — not financial advice.",
              "narration_beats": [{"text": "oh damn that is wild"}],
              "captions": [{"text": "the index"}], "claims": [{"source_ref": "data.cpi"}],
              "platform_meta": {"ai_disclosure": True}, "hook": {"spoken": "h"}}
    profile = {"defaults": {"disclaimer": "Educational only — not financial advice.",
                            "denylist_terms": ["guaranteed"],
                            "profanity_wordlist": ["shill"]}}
    vision = {"judgment": {"observations": ["clean"]}}
    results = collect_checks(script=script, profile=profile, vision=vision, probes=_probes(),
                             platform="tiktok", ledger=[], llm=_SaneLLM(),
                             thresholds=SafetyThresholds(), safe_zones=None)
    profanity = next(r for r in results if r.name == "profanity")
    assert not profanity.ok, "default profanity 'damn' must still be caught when profile adds terms"
    assert "damn" in profanity.detail


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


@pytest.mark.parametrize("leaked_key", [
    "grade", "rank", "assessment", "verdict", "evaluation",
])
def test_new_quality_synonym_keys_are_rejected(leaked_key):
    """_QUALITY_KEYS must include newly added synonyms so the 05b fact LLM can't smuggle
    quality signal in via alternate labels (e.g. 'grade' or 'verdict')."""
    class _LeakyLLM:
        def __init__(self, key):
            self._key = key

        def llm_json(self, prompt, seed=None):
            return {"hallucination": False, self._key: 0.9}

    with pytest.raises(QualityLeakError):
        collect_checks(script={"disclaimer": "", "narration_beats": [], "hook": {}},
                       profile={"defaults": {"disclaimer": "", "denylist_terms": []}},
                       vision={"judgment": {"observations": []}}, probes=_probes(),
                       platform="tiktok", ledger=[], llm=_LeakyLLM(leaked_key),
                       thresholds=SafetyThresholds(), safe_zones=None)
