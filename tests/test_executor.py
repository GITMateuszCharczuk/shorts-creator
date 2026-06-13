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


def test_systemic_failure_does_not_leak_running_for_completed_video():
    """H7: a video that completed ALL stages before a systemic halt must be persisted
    terminal ('done'), never left 'running' (the reconciler would needlessly re-run it,
    and a re-claimed topic could collide). The failing videos are 'failed'; videos not
    yet reached stay 'running'/'pending' for resume.

    Scenario: stage order [s1, s2]. Video 'a' is iterated first each stage and succeeds
    everywhere, completing the whole sweep at s2. Videos 'b','c','d' fail at s2, tripping
    the breaker. 'a' has no more stages pending -> must be 'done'.
    """
    vids = ("a", "b", "c", "d")
    batch = {"videos": [{"video_id": v, "status": "pending"} for v in vids]}
    # everyone passes s1; a passes s2, the rest fail s2 (3 consecutive -> breaker at d)
    script = {(v, "s2"): StageOutcome("failed", 1, 0.1) for v in ("b", "c", "d")}

    flushed = {}

    def persist(b):
        flushed.clear()
        flushed.update({x["video_id"]: x["status"] for x in b["videos"]})

    with pytest.raises(SystemicFailure):
        execute_batch(batch, stage_order=["s1", "s2"], run_stage=_runner(script),
                      persist=persist, max_consecutive_failures=3)

    # the persisted-on-failure snapshot is the source of truth for the reconciler
    statuses = {x["video_id"]: x["status"] for x in batch["videos"]}
    assert statuses == flushed                      # mutated state == last persisted state
    assert statuses["a"] == "done"                  # completed the sweep, NOT left running
    assert statuses["b"] == "failed"                # hit the failing stage
    assert statuses["c"] == "failed"
    assert statuses["d"] == "failed"                # the video that tripped the breaker


def test_systemic_failure_leaves_unreached_video_for_resume():
    """A video not yet reached by the sweep when the breaker trips must NOT be marked
    'done' — it still has pending stages and belongs to the reconciler ('running')."""
    # breaker trips at s1 on a,b,c (3 consecutive); 'z' is iterated last and never runs s1
    vids = ("a", "b", "c", "z")
    batch = {"videos": [{"video_id": v, "status": "pending"} for v in vids]}
    script = {(v, "s1"): StageOutcome("failed", 1, 0.1) for v in ("a", "b", "c")}

    with pytest.raises(SystemicFailure):
        execute_batch(batch, stage_order=["s1", "s2"], run_stage=_runner(script),
                      max_consecutive_failures=3)

    statuses = {x["video_id"]: x["status"] for x in batch["videos"]}
    assert statuses["c"] == "failed"                # tripped the breaker
    assert statuses["z"] == "running"               # never reached -> resume, not done


def test_raising_runner_becomes_failed_not_batch_corruption():
    # an exception in run_stage must mark the video failed, count toward the breaker,
    # and never leave the batch in an indeterminate state
    batch = {"videos": [{"video_id": "a", "status": "pending"},
                        {"video_id": "b", "status": "pending"}]}

    def boom(video_id, stage_id):
        if video_id == "a":
            raise RuntimeError("runner crashed")
        return StageOutcome("done", 0, 0.1)

    result = execute_batch(batch, stage_order=["00a"], run_stage=boom)
    assert result == {"a": "failed", "b": "done"}
