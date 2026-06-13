import json

from shared.ramp.state import load_state
from shorts.review import main, review_one


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


# ---------------------------------------------------------------------------
# main() — the production loop over runs/<batch>/<video> (M6 audit carry-forward c)
# ---------------------------------------------------------------------------

def _mk_video(data_root, batch, vid, *, qc=True, creative=True, overall=0.81):
    d = data_root / "runs" / batch / vid
    (d / "renders").mkdir(parents=True)
    (d / "renders" / "youtube.mp4").write_bytes(b"")
    (d / "qc.json").write_text(json.dumps({"passed": qc}))
    (d / "creative_qc.json").write_text(json.dumps({"pass": creative, "overall": overall}))
    (d / "feature_record.json").write_text(json.dumps({"video_id": vid, "scores": {}}))
    return d


def test_main_records_an_approve_and_a_reject(tmp_path, capsys):
    _mk_video(tmp_path, "b1", "v1")
    _mk_video(tmp_path, "b1", "v2", overall=0.92)
    answers = iter(["a", "r", "weak hook"])           # approve v1; reject v2 with a reason
    assert main(["--data-root", str(tmp_path)], input_fn=lambda _: next(answers)) == 0
    s = load_state(tmp_path / "ramp.json")
    assert s["approved"] == 1 and s["rejected"] == 1
    assert s["approved_videos"] == {"v1": True, "v2": False}
    fr1 = json.loads((tmp_path / "runs/b1/v1/feature_record.json").read_text())
    fr2 = json.loads((tmp_path / "runs/b1/v2/feature_record.json").read_text())
    assert fr1["ramp_label"]["approved"] is True
    assert fr2["ramp_label"] == {**fr2["ramp_label"], "approved": False, "reason": "weak hook"}
    out = capsys.readouterr().out
    assert "1 approved, 1 rejected, 0 skipped" in out
    assert "v1" in out and "youtube.mp4" in out       # video_id + render path shown
    assert "0.81" in out                              # creative_qc overall shown when present


def test_main_quit_immediately_leaves_state_untouched(tmp_path, capsys):
    _mk_video(tmp_path, "b1", "v1")
    assert main(["--data-root", str(tmp_path)], input_fn=lambda _: "q") == 0
    assert not (tmp_path / "ramp.json").exists()
    assert "0 approved, 0 rejected, 0 skipped" in capsys.readouterr().out


def test_main_unknown_key_skips_with_a_hint(tmp_path, capsys):
    _mk_video(tmp_path, "b1", "v1")
    assert main(["--data-root", str(tmp_path)], input_fn=lambda _: "x") == 0
    out = capsys.readouterr().out
    assert "0 approved, 0 rejected, 1 skipped" in out
    assert "a/r/s/q" in out                           # the hint
    assert not (tmp_path / "ramp.json").exists()      # nothing recorded


def test_main_queues_only_pending_gate_passed_videos(tmp_path):
    _mk_video(tmp_path, "b1", "v1")                       # pending
    _mk_video(tmp_path, "b1", "v2", creative=False)       # quarantined by 05c -> never queued
    _mk_video(tmp_path, "b2", "v3", qc=False)             # quarantined by 05b -> never queued
    _mk_video(tmp_path, "b2", "v4")                       # other batch
    shown = []
    rc = main(["--data-root", str(tmp_path), "--batch", "b1"],
              input_fn=lambda _: "a", open_fn=lambda p: shown.append(p))
    assert rc == 0
    assert [p.name for p in shown] == ["youtube.mp4"] and "b1" in str(shown[0])
    assert load_state(tmp_path / "ramp.json")["approved_videos"] == {"v1": True}


def test_main_excludes_already_decided_videos(tmp_path):
    from shared.ramp.state import record_decision
    _mk_video(tmp_path, "b1", "v1")
    _mk_video(tmp_path, "b1", "v2")
    record_decision(tmp_path / "ramp.json", video_id="v1", approved=True)
    assert main(["--data-root", str(tmp_path)], input_fn=lambda _: "a") == 0
    s = load_state(tmp_path / "ramp.json")
    assert s["approved_videos"] == {"v1": True, "v2": True} and s["approved"] == 2


def test_main_open_cmd_runs_the_player_command(tmp_path):
    _mk_video(tmp_path, "b1", "v1")
    log = tmp_path / "opened.txt"
    opener = tmp_path / "opener.sh"
    opener.write_text(f'#!/bin/sh\necho "$1" >> {log}\n')
    opener.chmod(0o755)
    main(["--data-root", str(tmp_path), "--open-cmd", str(opener)], input_fn=lambda _: "s")
    assert "youtube.mp4" in log.read_text()


def test_main_record_strike_mode(tmp_path, capsys):
    assert main(["--data-root", str(tmp_path),
                 "--record-strike", "yt community-guideline strike"]) == 0
    s = load_state(tmp_path / "ramp.json")
    assert s["strikes"] == 1
    assert s["strike_log"][0]["note"] == "yt community-guideline strike"
    assert "strike recorded" in capsys.readouterr().out
