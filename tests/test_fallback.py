from shared.visual.fallback import AssetChoice, choose_asset


def test_stock_used_when_above_threshold():
    c = choose_asset(beat="gold bars", stock_ranked=[("g.jpg", 0.42)], stock_threshold=0.30,
                     ai_available=True, is_hook=False)
    assert c == AssetChoice(kind="stock", ref="g.jpg")


def test_falls_through_to_ai_when_stock_weak():
    c = choose_asset(beat="gold bars", stock_ranked=[("g.jpg", 0.10)], stock_threshold=0.30,
                     ai_available=True, is_hook=False)
    assert c == AssetChoice(kind="ai", ref=None)


def test_terminal_is_branded_card_not_generic():
    c = choose_asset(beat="gold bars", stock_ranked=[], stock_threshold=0.30,
                     ai_available=False, is_hook=False)
    assert c == AssetChoice(kind="card", ref=None)


def test_hook_floor_is_typographic_card():
    c = choose_asset(beat="hook", stock_ranked=[], stock_threshold=0.30,
                     ai_available=False, is_hook=True)
    assert c == AssetChoice(kind="hook_card", ref=None)
