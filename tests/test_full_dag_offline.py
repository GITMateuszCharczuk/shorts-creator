import json

from shared.cache import StageCache
from shared.runner import run_dag


def test_full_dag_produces_posts_record(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    result = run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    posts = json.loads((run_dir / result["posts"]).read_text())
    assert posts["state"] == "confirmed"
    assert posts["platform"] in ("youtube", "tiktok")


def test_rerun_is_cache_hit(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    second = run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    assert second["cache_hits"] > 0


def test_seed_change_is_a_miss(run_dir, tmp_path):
    cache = StageCache(root=tmp_path / "cache")
    run_dag(run_dir=run_dir, seed=7, cache=cache, fixtures_dir=_backend_fixtures())
    third = run_dag(run_dir=run_dir, seed=8, cache=cache, fixtures_dir=_backend_fixtures())
    assert third["cache_hits"] == 0


def _backend_fixtures():
    from pathlib import Path
    return Path(__file__).parent / "fixtures" / "backends"
