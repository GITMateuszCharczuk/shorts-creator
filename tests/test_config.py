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
