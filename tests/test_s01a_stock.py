from shared.visual.fallback import AssetChoice
from stages.s01a_stock.stage import select_for_beat


def test_select_for_beat_ranks_dedups_then_chooses():
    cands = [("a.jpg", "ffff0000ffff0000"), ("b.jpg", "0000ffff0000ffff")]
    choice = select_for_beat(
        beat="gold bars", candidates=cands,
        scorer=lambda p: {"a.jpg": 0.1, "b.jpg": 0.5}[p],
        used_hashes={"ffff0000ffff0001"},   # a.jpg is a near-dup of a used clip
        stock_threshold=0.30, ai_available=True, is_hook=False)
    # a dropped by dedup, b clears threshold
    assert choice == AssetChoice(kind="stock", ref="b.jpg")
