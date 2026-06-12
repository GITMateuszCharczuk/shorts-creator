from shared.ops.gc import PROTECTED, quarantine_to_delete, runs_to_delete


def test_keeps_recent_runs_by_count_and_age_and_deletes_the_rest():
    runs = [{"id": f"b{i}", "age_days": i} for i in range(20)]
    deleted = {r["id"] for r in runs_to_delete(runs, keep_days=7, keep_count=14)}
    assert deleted == {f"b{i}" for i in range(14, 20)}        # b14..b19 (old AND beyond newest 14)
    assert "b0" not in deleted and "b13" not in deleted


def test_active_or_resumed_batch_is_never_deleted_regardless_of_age():
    runs = [{"id": "old-resumed", "age_days": 99}, {"id": "b1", "age_days": 99}]
    deleted = {r["id"] for r in runs_to_delete(runs, keep_days=7, keep_count=1,
                                               protected_ids={"old-resumed"})}
    assert "old-resumed" not in deleted                      # the reconciler just re-ran it


def test_quarantine_kept_longer():
    q = [{"id": "q1", "age_days": 10}, {"id": "q2", "age_days": 40}]
    assert [r["id"] for r in quarantine_to_delete(q, keep_days=30)] == ["q2"]


def test_history_and_models_protected():
    assert "history" in PROTECTED and "models" in PROTECTED
