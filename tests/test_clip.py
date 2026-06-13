import importlib
import importlib.util

import pytest

from shared.visual.clip import ClipRanker, rank_candidates


def test_rank_orders_by_descending_score():
    scores = {"a.jpg": 0.2, "b.jpg": 0.9, "c.jpg": 0.5}
    ranked = rank_candidates(["a.jpg", "b.jpg", "c.jpg"], lambda p: scores[p])
    assert ranked == ["b.jpg", "c.jpg", "a.jpg"]


def test_below_threshold_filtered():
    scores = {"a.jpg": 0.1, "b.jpg": 0.4}
    ranked = rank_candidates(["a.jpg", "b.jpg"], lambda p: scores[p], threshold=0.3)
    assert ranked == ["b.jpg"]


def test_rank_stable_for_equal_scores():
    """Python sorted() is stable — equal-score candidates keep input order (ADR 0009)."""
    scores = {"a.jpg": 0.5, "b.jpg": 0.5, "c.jpg": 0.5}
    ranked = rank_candidates(["a.jpg", "b.jpg", "c.jpg"], lambda p: scores[p])
    assert ranked == ["a.jpg", "b.jpg", "c.jpg"]


def test_clip_module_imports_without_torch():
    """CI-safety: open_clip/torch are host-only; clip.py must import cleanly without them."""
    assert importlib.util.find_spec("open_clip") is None
    importlib.import_module("shared.visual.clip")   # must not raise
    ClipRanker()                                     # construct without loading model (lazy only)


@pytest.mark.integration
def test_clip_ranker_scores_real_image(tmp_path):
    r = ClipRanker(model="ViT-B-32", pretrained="laion2b_s34b_b79k")
    # cosine similarity lives in [-1, 1] (the plan's 0..1 bound was wrong for anti-correlated pairs)
    assert -1.0 <= r.score("a green stock chart", tmp_path / "chart.png") <= 1.0


def test_rank_skips_candidates_whose_scorer_raises():
    # one corrupt image must never sink the whole beat's candidate list
    def scorer(p):
        if p == "bad.jpg":
            raise OSError("corrupt image")
        return 0.5
    assert rank_candidates(["bad.jpg", "ok.jpg"], scorer) == ["ok.jpg"]
