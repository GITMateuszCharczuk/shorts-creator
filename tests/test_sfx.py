from shared.audio.sfx import cues_for_scenes


def test_tick_per_list_item_and_riser_on_reveal():
    scenes = [{"kind": "hook"}, {"kind": "item"}, {"kind": "item"}, {"kind": "cta"}]
    cues = cues_for_scenes(scenes)
    kinds = [c["sfx"] for c in cues]
    assert kinds.count("tick") == 2          # one per item
    assert "whoosh" in kinds                  # transitions
