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


def test_cross_beat_dedup_blocks_repeating_the_same_clip(tmp_path):
    # two beats with the SAME candidates: beat 0 takes the best clip; beat 1 must not reuse it
    import json as _json

    from shared.ctx import StageContext
    from stages.s01a_stock.stage import run

    class _OneClipStock:
        def search(self, query, n):
            return [{"path": "stock/same.jpg", "phash": "ffff0000ffff0000", "score": 0.9,
                     "source": "pexels", "url": "u", "license": "Pexels",
                     "fetch_date": "2026-06-09"}]

    (tmp_path / "script.json").write_text(_json.dumps(
        {"narration_beats": [{"text": "gold bars"}, {"text": "gold bars again"}]}))
    ctx = StageContext(stage="01a", run_dir=tmp_path, seed=1, job={}, config={},
                       input_paths={"script": "script.json"},
                       output_paths={"scenes_stock": "scenes_stock.json",
                                     "provenance": "provenance.json"},
                       backends={"stock": _OneClipStock()})
    run(ctx)
    choices = _json.loads((tmp_path / "scenes_stock.json").read_text())["choices"]
    assert choices[0]["kind"] == "stock"
    assert choices[1]["kind"] != "stock" or choices[1]["ref"] != choices[0]["ref"]
