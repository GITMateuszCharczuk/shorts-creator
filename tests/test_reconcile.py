from shared.conductor.reconcile import resume_plan


def test_resumes_pending_and_running_videos_only():
    batch = {"videos": [{"video_id": "a", "status": "done"},
                        {"video_id": "b", "status": "running"},
                        {"video_id": "c", "status": "pending"},
                        {"video_id": "d", "status": "quarantined"}]}
    assert resume_plan(batch) == ["b", "c"]       # done/quarantined never re-run


def test_clean_batch_resumes_nothing():
    assert resume_plan({"videos": [{"video_id": "a", "status": "done"}]}) == []
