from shared.ramp.queue import pending_review


def test_pending_is_passed_both_gates_and_not_yet_decided():
    videos = [{"video_id": "a", "qc_pass": True, "creative_pass": True},
              {"video_id": "b", "qc_pass": False, "creative_pass": True},
              {"video_id": "c", "qc_pass": True, "creative_pass": True}]
    assert pending_review(videos, {"a": True}) == ["c"]
