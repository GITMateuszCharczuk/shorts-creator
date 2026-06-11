import pytest

from shared.stage import REGISTRY, StageManifest, stage


def test_stage_decorator_registers():
    REGISTRY.clear()

    @stage(StageManifest(id="demo", inputs=["a"], outputs=["b"], compute="cpu"))
    def run(ctx):
        return None

    assert "demo" in REGISTRY
    assert REGISTRY["demo"].manifest.outputs == ["b"]


def test_manifest_requires_capability_for_gpu():
    with pytest.raises(ValueError):
        StageManifest(id="g", inputs=[], outputs=[], compute="gpu")  # no capability
