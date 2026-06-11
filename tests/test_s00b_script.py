from shared.finance.grounding import GroundingError  # noqa: F401
from stages.s00b_script.stage import build_judge_prompt, clears_floor, pick_best


def test_pick_best_returns_highest_score():
    scored = [({"hook": "a"}, 0.4), ({"hook": "b"}, 0.9), ({"hook": "c"}, 0.7)]
    assert pick_best(scored) == {"hook": "b"}


def test_pick_best_is_deterministic_on_ties_by_index():
    scored = [({"hook": "a"}, 0.9), ({"hook": "b"}, 0.9)]
    assert pick_best(scored) == {"hook": "a"}  # first wins on tie


def test_judge_prompt_includes_original_insight_criterion():
    p = build_judge_prompt({"hook": {"spoken": "x"}})
    assert "non-obvious" in p.lower() or "original" in p.lower()  # ADR 0014 D1


def test_clears_floor_gates_all_bad_batches():
    # ADR 0016 D3: best-of-N SELECTS, but an all-mediocre N must not reach the GPU lane
    assert clears_floor([({"h": 1}, 0.8), ({"h": 2}, 0.4)], floor=0.55) is True
    assert clears_floor([({"h": 1}, 0.4), ({"h": 2}, 0.5)], floor=0.55) is False


def test_parse_score_handles_prefixed_replies():
    from stages.s00b_script.stage import parse_score
    assert parse_score("0.82") == 0.82
    assert parse_score("Score: 0.82") == 0.82          # live models often prefix words
    assert parse_score("I'd give it 0.9 overall") == 0.9
    assert parse_score("no number here") is None        # caller quarantines
