import json
from pathlib import Path

import pytest

from shared.audio.music import NoTrackError, select_track

LIB = json.loads((Path(__file__).parent / "fixtures" / "m3" / "music_index.json").read_text())


def test_select_matches_mood_energy_and_is_seed_deterministic():
    a = select_track(LIB, mood="confident", energy="mid", seed=7, recent_ids=set())
    b = select_track(LIB, mood="confident", energy="mid", seed=7, recent_ids=set())
    assert a["id"] == b["id"] and a["mood"] == "confident" and a["energy"] == "mid"


def test_anti_repeat_excludes_recent():
    chosen = select_track(LIB, mood="confident", energy="mid", seed=7, recent_ids={"t1"})
    assert chosen["id"] == "t2"


def test_taxonomy_is_closed():
    with pytest.raises(ValueError):
        select_track(LIB, mood="spicy", energy="mid", seed=7, recent_ids=set())


def test_no_track_when_all_recent():
    with pytest.raises(NoTrackError):
        select_track(LIB, mood="tense", energy="high", seed=1, recent_ids={"t3"})
