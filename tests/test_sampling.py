# tests/test_sampling.py
import pytest

from shared.qc.sampling import sample_frames
from shared.schema import SchemaError, SchemaRegistry


def test_includes_hook_endcard_markers_and_caps_at_8():
    manifest = {"fps": 30, "markers": {"cta_bump": 90},
                "scenes": [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0},
                           {"start": 4.0, "end": 6.0}]}
    total_frames = 180
    idx = sample_frames(manifest, total_frames)
    assert 0 in idx and (total_frames - 1) in idx and 90 in idx
    assert len(idx) <= 8 and idx == sorted(set(idx))


def _vision(judgment: dict) -> dict:
    return {"schema_version": "1.0.0",
            "keyframes": [{"frame_id": "0", "kind": "hook", "observations": []}],
            "judgment": judgment}


def test_vision_judgment_schema():
    reg = SchemaRegistry()
    reg.validate("vision", _vision(
        {"visual_scores": {"coherence": 0.85, "pacing": 0.8},
         "observations": ["clean frames"]}))
    with pytest.raises(SchemaError):   # missing pacing — the pinned visual keys can't drift
        reg.validate("vision", _vision(
            {"visual_scores": {"coherence": 0.85}, "observations": []}))


def test_cap_always_retains_hook_and_endcard():
    # >8 candidates force truncation; the endpoints must survive (the 05b kind contract)
    manifest = {"fps": 30, "markers": {},
                "scenes": [{"start": float(i), "end": i + 1.0} for i in range(12)]}
    idx = sample_frames(manifest, 400)
    assert len(idx) <= 8
    assert 0 in idx and 399 in idx
