from pathlib import Path

import pytest

from shared.stage import REGISTRY, StageManifest, load_manifest, stage
from stages.registry import load_all

STAGES_DIR = Path(__file__).resolve().parents[1] / "stages"


def test_stage_decorator_registers():
    saved = dict(REGISTRY)   # save/restore so clearing the global REGISTRY can't leak across tests
    REGISTRY.clear()
    try:
        @stage(StageManifest(id="demo", inputs=["a"], outputs=["b"], compute="cpu"))
        def run(ctx):
            return None

        assert "demo" in REGISTRY
        assert REGISTRY["demo"].manifest.outputs == ["b"]
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_load_manifest_bad_field_raises_clear_error(tmp_path):
    import json as _json
    p = tmp_path / "manifest.json"
    p.write_text(_json.dumps({"id": "x", "inputs": [], "outputs": [], "compute": "cpu",
                              "bogus": 1}))
    from shared.stage import load_manifest
    with pytest.raises(ValueError):
        load_manifest(p)


def test_manifest_requires_capability_for_gpu():
    with pytest.raises(ValueError):
        StageManifest(id="g", inputs=[], outputs=[], compute="gpu")  # no capability


def test_manifests_match_registered_stages():
    load_all()
    manifest_files = sorted(STAGES_DIR.glob("s*/manifest.json"))
    assert len(manifest_files) == 15
    for mf in manifest_files:
        m = load_manifest(mf)
        assert m.id in REGISTRY, f"{m.id} declared in {mf} but not registered"
        assert REGISTRY[m.id].manifest == m, f"manifest drift for {m.id}"
