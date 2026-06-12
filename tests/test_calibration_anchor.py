from shared.calibration.anchor import PROVISIONAL, recommend_floor


def test_holds_provisional_until_enough_labels():
    rec = recommend_floor([{"overall": 0.8, "approved": True}] * 5, min_labels=30)
    assert rec["floor"] == PROVISIONAL and rec["reason"] == "insufficient_labels"


def test_low_confidence_flag_below_50():
    labels = ([{"overall": o, "approved": True} for o in (0.74, 0.82, 0.95)] +
              [{"overall": o, "approved": False} for o in (0.40, 0.55, 0.69)]) * 6   # 36 labels
    rec = recommend_floor(labels, min_labels=30)
    assert rec["reason"] == "data_anchored" and rec["low_confidence"] is True        # 36 < 50


def test_picks_a_separating_floor_with_keep_precision_constraint():
    labels = ([{"overall": o, "approved": True} for o in (0.74, 0.78, 0.82, 0.9, 0.95)] +
              [{"overall": o, "approved": False} for o in (0.40, 0.52, 0.60, 0.66, 0.69)]) * 6  # 60
    rec = recommend_floor(labels, min_labels=30, min_keep_precision=0.85)
    assert 0.69 < rec["floor"] <= 0.74 and rec["keep_precision"] >= 0.85
    assert rec["low_confidence"] is False and rec["n_labels"] == 60


def test_never_below_a_safety_minimum():
    rec = recommend_floor([{"overall": 0.1, "approved": True}] * 35, min_labels=30, floor_min=0.50)
    assert rec["floor"] >= 0.50
