import json

from shorts.stage import resolve_argo_args


def test_resolves_run_dir_seed_config_from_batch_json(tmp_path):
    batch = {"batch_id": "b1", "videos": [
        {"video_id": "fin-b1-0", "niche": "finance", "seed": 4242, "format": "myth_buster"}]}
    (tmp_path / "runs" / "b1").mkdir(parents=True)
    (tmp_path / "runs" / "b1" / "batch.json").write_text(json.dumps(batch))
    args = resolve_argo_args(data_root=tmp_path, batch_id="b1", video_id="fin-b1-0")
    assert args["run_dir"].endswith("runs/b1/fin-b1-0")
    assert args["seed"] == 4242                          # the per-video seed from the plan
    assert args["config"]["niche"] == "finance"


def test_unknown_video_is_a_hard_error(tmp_path):
    (tmp_path / "runs" / "b1").mkdir(parents=True)
    (tmp_path / "runs" / "b1" / "batch.json").write_text('{"batch_id":"b1","videos":[]}')
    import pytest
    with pytest.raises(KeyError):
        resolve_argo_args(data_root=tmp_path, batch_id="b1", video_id="ghost")
