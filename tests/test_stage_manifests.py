import pytest

from shared.stage import REGISTRY, StageManifest, stage


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
