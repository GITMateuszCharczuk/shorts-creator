import json
from pathlib import Path

import pytest

from shared.ctx import Degraded, Quarantined, StageContext, StageResult


def _ctx(run_dir: Path) -> StageContext:
    (run_dir / "data.json").write_text(json.dumps({"hello": "world"}))
    return StageContext(
        stage="00b", run_dir=run_dir, seed=7,
        job={"seed": 7, "video_id": "v1"},
        config={"k": 1},
        input_paths={"data": "data.json"},
        output_paths={"script": "script.json"},
        backends={},
    )


def test_read_input_by_name(run_dir):
    ctx = _ctx(run_dir)
    assert json.loads(ctx.read_input("data").read_text()) == {"hello": "world"}


def test_read_undeclared_input_raises(run_dir):
    ctx = _ctx(run_dir)
    with pytest.raises(KeyError):
        ctx.read_input("not_declared")


def test_write_output_returns_path_under_run_dir(run_dir):
    ctx = _ctx(run_dir)
    p = ctx.write_output("script")
    p.write_text("{}")
    assert p == run_dir / "script.json" and p.exists()


def test_seed_and_job_exposed(run_dir):
    ctx = _ctx(run_dir)
    assert ctx.seed == 7 and ctx.job["video_id"] == "v1"


def test_quarantine_signal(run_dir):
    ctx = _ctx(run_dir)
    with pytest.raises(Quarantined):
        ctx.quarantine("safety failed")


def test_degrade_signal(run_dir):
    ctx = _ctx(run_dir)
    with pytest.raises(Degraded):
        ctx.degrade("budget tripped")


def test_stage_result_defaults(run_dir):
    r = StageResult()
    assert r.outputs == {} and r.cache_hit is False


def test_set_status_atomic_section_scoped(run_dir):
    (run_dir / "job.json").write_text(json.dumps({"seed": 7, "video_id": "v1", "stages": {}}))
    _ctx(run_dir).set_status("running")
    job = json.loads((run_dir / "job.json").read_text())
    assert job["stages"]["00b"]["status"] == "running"   # only this stage's section touched
    assert not (run_dir / "job.json.tmp").exists()        # temp renamed away
