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


def test_result_does_not_alias_inputs():
    # mutating the resolved config must NEVER corrupt a shared input layer (batch-safety)
    g = {"render": {"fps": 30}}
    p = {"extra": {"flag": True}}                     # nested dict present only in per_platform
    cfg = resolve_config(global_defaults=g, niche={}, batch={}, per_platform=p)
    cfg["render"]["fps"] = 999
    cfg["extra"]["flag"] = False
    assert g["render"]["fps"] == 30 and p["extra"]["flag"] is True


def test_empty_layers_resolve_to_empty():
    assert resolve_config(global_defaults={}, niche={}, batch={}, per_platform={}) == {}
