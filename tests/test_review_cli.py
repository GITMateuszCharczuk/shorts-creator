import json

from shared.ramp.state import load_state
from shorts.review import review_one


def test_approve_plays_then_records_label_and_state(tmp_path):
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "scores": {}}))
    state = tmp_path / "ramp.finance.json"
    played = []
    review_one(video_id="v", render="v.mp4", feature_record=fr, state_path=state,
               play=lambda p: played.append(p), prompt=lambda: ("approve", ""))
    assert played == ["v.mp4"]
    assert json.loads(fr.read_text())["ramp_label"]["approved"] is True
    assert load_state(state)["approved"] == 1


def test_reject_captures_reason(tmp_path):
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "scores": {}}))
    review_one(video_id="v", render="v.mp4", feature_record=fr, state_path=tmp_path / "s.json",
               play=lambda p: None, prompt=lambda: ("reject", "hook was weak"))
    assert json.loads(fr.read_text())["ramp_label"]["reason"] == "hook was weak"
