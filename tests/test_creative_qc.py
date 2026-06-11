# tests/test_creative_qc.py
import pytest

from shared.qc.creative import CRITERIA, RUBRIC, passes_floor, weighted_overall


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
