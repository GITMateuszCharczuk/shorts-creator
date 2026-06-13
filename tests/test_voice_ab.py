import pytest

from shared.adapters import ModelBackend
from shared.adapters.real import ChatterboxBackend, KokoroBackend, OrpheusBackend
from shared.audio.prosody import speech_segments
from shared.audio.voice_ab import reference_script


def test_reference_script_yields_varied_rate_segments():
    # the A/B gate's pure unit: the fixed reference (hook + 3 beats, emphatic/rising) must
    # produce per-segment rates that actually VARY — a flat read cannot exercise rate control.
    segs = speech_segments(reference_script())
    assert len(segs) >= 4
    assert len({s["rate"] for s in segs}) > 1
    assert all(s["pause_after"] > 0 for s in segs)


@pytest.mark.parametrize("cls", [KokoroBackend, OrpheusBackend, ChatterboxBackend])
def test_candidate_backend_satisfies_model_backend(cls, tmp_path):
    assert isinstance(cls(out_dir=tmp_path), ModelBackend)
