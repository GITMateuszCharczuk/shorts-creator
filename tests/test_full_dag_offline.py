import json
from pathlib import Path

import pytest

from shared.cache import StageCache
from shared.runner import run_dag
from stages.s01d_upscale.stage import _PLACEHOLDER_PNG

REPO = Path(__file__).resolve().parents[1]
DATA_FIX = Path(__file__).parent / "fixtures" / "m1" / "data.json"


@pytest.fixture(autouse=True)
def _fake_align(monkeypatch):
    """The documented WhisperX seam: 03 runs in CI against the aligned-words fixture."""
    import stages.s03_subs.stage as s03
    aligned = json.loads(
        (Path(__file__).parent / "fixtures" / "m1" / "aligned_words.json").read_text()
    )
    monkeypatch.setattr(s03, "_align_to_script", lambda wav, txt: aligned)


@pytest.fixture(autouse=True)
def _fake_compositor(monkeypatch):
    """The documented compositor seams: 05's Remotion render + NVENC encode are faked in CI
    (deterministic bytes, cache-stable); the REAL render proof is test_render_determinism
    (integration)."""
    import stages.s05_render.stage as s05

    def fake_render(manifest: dict, out_dir: Path) -> list[Path]:
        frames_dir = out_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(2):
            p = frames_dir / f"{i:05d}.png"
            p.write_bytes(_PLACEHOLDER_PNG)
            paths.append(p)
        return paths

    def fake_encode(*, frames_glob: str, audio: Path, fps: int, out: Path) -> None:
        Path(out).write_bytes(b"\x00\x00\x00\x18ftypmp42fake")

    monkeypatch.setattr(s05, "render_manifest_to_frames", fake_render)
    monkeypatch.setattr(s05, "_encode", fake_encode)


def _seed_fixture(run_dir: Path) -> dict:
    """Copy the data fixture into run_dir as data_fixture.json and return the config dict."""
    (run_dir / "data_fixture.json").write_text(DATA_FIX.read_text())
    # Stage 05 (compositor) reads run_dir/formats/<format>/layout.json + run_dir/brand_kit.json.
    layout_dst = run_dir / "formats" / "ranked_list" / "layout.json"
    layout_dst.parent.mkdir(parents=True, exist_ok=True)
    layout_dst.write_text((REPO / "formats" / "ranked_list" / "layout.json").read_text())
    (run_dir / "brand_kit.json").write_text(
        (Path(__file__).parent / "fixtures" / "m2" / "brand_kit.json").read_text())
    return {"data_fixture": "data_fixture.json", "best_of_n": 1}


def test_full_dag_produces_posts_record(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    cfg = _seed_fixture(run_dir)
    result = run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures(),
                     config=cfg)
    posts = json.loads((run_dir / result["posts"]).read_text())
    assert posts["state"] == "confirmed"
    assert posts["platform"] in ("youtube", "tiktok")


def test_rerun_is_cache_hit(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    cfg = _seed_fixture(run_dir)
    run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures(), config=cfg)
    second = run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures(),
                     config=cfg)
    assert second["cache_hits"] > 0


def test_seed_change_is_a_miss(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    cfg = _seed_fixture(run_dir)
    run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures(), config=cfg)
    third = run_dag(run_dir=run_dir, seed=8, cache=cache, fixtures_dir=_backend_fixtures(),
                    config=cfg)
    assert third["cache_hits"] == 0


def _backend_fixtures():
    return Path(__file__).parent / "fixtures" / "backends"


def test_order_is_a_valid_topological_order():
    # the hardcoded ORDER must respect the manifest DAG edges: every declared input is produced
    # by an EARLIER stage. Guards against ORDER drifting from the stage manifests (M4 will derive
    # the order from the edges; until then this is the invariant that keeps them consistent).
    from shared.runner import ORDER
    from shared.stage import REGISTRY
    from stages.registry import load_all
    load_all()
    produced: set[str] = set()
    for sid in ORDER:
        m = REGISTRY[sid].manifest
        for inp in m.inputs:
            assert inp in produced, f"{sid} consumes {inp!r} before it is produced (DAG drift)"
        produced.update(m.outputs)
