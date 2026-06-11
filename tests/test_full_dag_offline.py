import json
from pathlib import Path

from shared.cache import StageCache
from shared.runner import run_dag

DATA_FIX = Path(__file__).parent / "fixtures" / "m1" / "data.json"


def _seed_fixture(run_dir: Path) -> dict:
    """Copy the data fixture into run_dir as data_fixture.json and return the config dict."""
    (run_dir / "data_fixture.json").write_text(DATA_FIX.read_text())
    return {"data_fixture": "data_fixture.json"}


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
