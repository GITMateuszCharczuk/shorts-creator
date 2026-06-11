import json

from shared.ramp.labels import record_label


def test_decision_writes_a_ramp_label_into_feature_record(tmp_path):
    fr = tmp_path / "feature_record.json"
    fr.write_text(json.dumps({"video_id": "v", "format": "myth_buster", "scores": {}}))
    record_label(fr, approved=False, reason="thesis was generic")
    rec = json.loads(fr.read_text())
    assert rec["ramp_label"]["approved"] is False
    assert rec["ramp_label"]["reason"] == "thesis was generic"
