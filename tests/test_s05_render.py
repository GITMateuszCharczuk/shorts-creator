from stages.s05_render.stage import scene_durations_from_words


def test_scene_durations_split_by_beat_count():
    words = [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.0}, {"start": 2.0, "end": 4.0}]
    durs = scene_durations_from_words(words, n_scenes=2)
    assert len(durs) == 2
    assert abs(sum(durs) - 4.0) < 1e-6


def test_zero_scenes_returns_empty_not_zerodivision():
    assert scene_durations_from_words([{"start": 0.0, "end": 1.0}], n_scenes=0) == []
