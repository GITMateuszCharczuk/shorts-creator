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


def test_below_floor_writes_artifact_then_quarantines(tmp_path):
    import json

    from shared.ctx import Quarantined, StageContext
    from stages.s05c_qc.stage import run

    class _WeakJudge:
        def llm_json(self, prompt, seed=None):
            return {"hook": 0.1, "original_insight": 0.1, "payoff": 0.1}

    (tmp_path / "vision.json").write_text(json.dumps(
        {"judgment": {"visual_scores": {"coherence": 0.2, "pacing": 0.2}, "observations": []}}))
    (tmp_path / "script.json").write_text(json.dumps({"format": "x"}))
    (tmp_path / "render.mp4").write_bytes(b"x")
    ctx = StageContext(stage="05c", run_dir=tmp_path, seed=1, job={}, config={},
                       input_paths={"render": "render.mp4", "vision": "vision.json",
                                    "script": "script.json"},
                       output_paths={"creative_qc": "creative_qc.json"},
                       backends={"llm": _WeakJudge()})
    with pytest.raises(Quarantined):
        run(ctx)
    payload = json.loads((tmp_path / "creative_qc.json").read_text())   # artifact written FIRST
    assert payload["pass"] is False
