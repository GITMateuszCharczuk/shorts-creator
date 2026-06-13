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


def _all_manifests():
    return [load_manifest(mf) for mf in sorted(STAGES_DIR.glob("s*/manifest.json"))]


def test_scenes_viz_reaches_the_renderer():
    # H8: 01e produces scenes_viz; before the fix NO stage consumed it, so the data-viz lane
    # never reached the renderer. The renderer (05) must declare it as an input so the dataviz
    # charts fold into the render (the parallel of the MediaZone `assets` lane).
    manifests = {m.id: m for m in _all_manifests()}
    assert "scenes_viz" in manifests["01e"].outputs
    assert "scenes_viz" in manifests["05"].inputs, "scenes_viz orphaned — 05 must consume it"


def test_no_orphan_visual_lane_scene_artifacts():
    # the drift-catcher for H8: every `scenes_*` visual-lane artifact is consumed by some
    # downstream stage's inputs — no lane silently dropped before the renderer. (scenes_viz was
    # the orphan: 01e produced it, no stage consumed it.)
    manifests = _all_manifests()
    all_inputs = {i for m in manifests for i in m.inputs}
    scene_outputs = {o for m in manifests for o in m.outputs if o.startswith("scenes_")}
    assert scene_outputs, "expected scenes_* visual-lane artifacts to exist"
    for out in sorted(scene_outputs):
        assert out in all_inputs, f"visual-lane artifact {out!r} is consumed by no stage"
