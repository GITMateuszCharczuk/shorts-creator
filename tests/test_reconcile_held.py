from shared.conductor.reconcile import resume_plan


def test_held_is_requeued_done_and_quarantined_are_not():
    batch = {"videos": [
        {"video_id": "a", "status": "done"},
        {"video_id": "b", "status": "held"},
        {"video_id": "c", "status": "quarantined"},
        {"video_id": "d", "status": "pending"},
    ]}
    assert resume_plan(batch) == ["b", "d"]   # held re-queued (idempotent re-run via exactly-once)
