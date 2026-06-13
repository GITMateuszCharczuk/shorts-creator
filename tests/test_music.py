import json
from pathlib import Path

import pytest

from shared.audio.music import ENERGIES, MOODS, NoTrackError, select_track

LIB = json.loads((Path(__file__).parent / "fixtures" / "m3" / "music_index.json").read_text())

REPO = Path(__file__).resolve().parents[1]
ALLOWED_LICENSES = {"YouTubeAudioLibrary", "TikTokCommercialMusicLibrary", "PixabayMusic"}


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


@pytest.mark.parametrize("niche", ["finance", "business"])
def test_music_indexes_present_and_licensed(niche):
    # ADR 0009 strike-safe rule: the curated per-niche library covers EVERY mood x energy cell
    # with license-verified tracks (terms verified, not assumed), so Stage 04 runs unattended.
    library = json.loads((REPO / "profiles" / niche / "music" / "index.json").read_text())
    for mood in MOODS:
        for energy in ENERGIES:
            cell = [t for t in library if t["mood"] == mood and t["energy"] == energy]
            assert cell, f"{niche}: no track for {mood}/{energy}"
    for t in library:
        assert t.get("license", "").strip(), f"{niche}: track {t['id']} has no license"
        assert t["license"] in ALLOWED_LICENSES, f"{niche}: {t['id']} license not strike-safe"
        assert t.get("path"), f"{niche}: track {t['id']} has no path"
    ids = [t["id"] for t in library]
    assert len(ids) == len(set(ids)), f"{niche}: duplicate track ids"
