import pytest

from shared.conductor.executor import SystemicFailure, execute_batch
from shared.conductor.subproc import StageOutcome


def _runner(script):
    def run(video_id, stage_id):                  # (video, stage) -> StageOutcome
        return script.get((video_id, stage_id), StageOutcome("done", 0, 0.1))
    return run


def test_per_video_failure_domain_isolates(tmp_path):
    batch = {"videos": [{"video_id": "a", "status": "pending"},
                        {"video_id": "b", "status": "pending"}]}
    script = {("a", "00b"): StageOutcome("quarantined", 77, 0.1)}
    result = execute_batch(batch, stage_order=["00a", "00b", "02"],
                           run_stage=_runner(script))
    assert result["a"] == "quarantined"           # a parked at 00b — 02 never ran for a
    assert result["b"] == "done"                  # b unaffected (per-video domain, ADR 0003)


def test_failed_stage_fails_only_that_video():
    batch = {"videos": [{"video_id": "a", "status": "pending"},
                        {"video_id": "b", "status": "pending"}]}
    script = {("b", "02"): StageOutcome("failed", 1, 0.1)}
    result = execute_batch(batch, stage_order=["00a", "00b", "02"], run_stage=_runner(script))
    assert result == {"a": "done", "b": "failed"}


def test_statuses_are_written_through_and_persisted():
    # the boot reconciler reads batch.json — statuses MUST be flushed, not just returned
    batch = {"videos": [{"video_id": "a", "status": "pending"}]}
    flushes = []
    execute_batch(batch, stage_order=["00a"], run_stage=_runner({}),
                  persist=lambda b: flushes.append(True))
    assert batch["videos"][0]["status"] == "done"     # mutated in place
    assert flushes                                     # and persisted


def test_circuit_breaker_halts_on_consecutive_failures():
    batch = {"videos": [{"video_id": v, "status": "pending"} for v in ("a", "b", "c")]}
    script = {(v, "00a"): StageOutcome("failed", 1, 0.1) for v in ("a", "b", "c")}
    with pytest.raises(SystemicFailure):              # host-down pattern, not 3x bad luck
        execute_batch(batch, stage_order=["00a", "00b"], run_stage=_runner(script),
                      max_consecutive_failures=3)


def test_done_videos_not_rerun():
    """A video already 'done' must never be re-run — boot-reconciler resume semantics.

    This test exposes the plan bug (spec skip tuple omitted "done") and verifies the fix:
    the executor skips ("quarantined", "failed", "done") so a resumed batch leaves
    already-completed videos untouched.
    """
    def raising_runner(video_id, stage_id):
        raise AssertionError(f"run_stage called for already-done video {video_id!r}")

    batch = {"videos": [{"video_id": "already", "status": "done"}]}
    result = execute_batch(batch, stage_order=["00a", "00b"], run_stage=raising_runner)
    assert result["already"] == "done"
