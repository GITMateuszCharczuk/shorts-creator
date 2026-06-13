import json

import pytest

from shared.exitcodes import EXIT_OK
from shared.stage import REGISTRY, RegisteredStage, StageManifest, default_path
from shorts.stage import main, resolve_argo_args
from stages.registry import load_all


def test_resolves_run_dir_seed_config_from_batch_json(tmp_path):
    load_all()  # populate REGISTRY so the manifest IO-path derivation can run
    batch = {"batch_id": "b1", "videos": [
        {"video_id": "fin-b1-0", "niche": "finance", "seed": 4242, "format": "myth_buster"}]}
    (tmp_path / "runs" / "b1").mkdir(parents=True)
    (tmp_path / "runs" / "b1" / "batch.json").write_text(json.dumps(batch))
    args = resolve_argo_args(data_root=tmp_path, batch_id="b1", video_id="fin-b1-0",
                             stage_id="00a")
    assert args["run_dir"].endswith("runs/b1/fin-b1-0")
    assert args["seed"] == 4242                          # the per-video seed from the plan
    assert args["config"]["niche"] == "finance"


def test_argo_mode_derives_input_output_paths_from_manifest(tmp_path):
    # C3: an Argo pod for a real stage must carry input_paths/output_paths in its config so
    # shorts.stage.main() runs the stage body instead of p.error()-ing at the IO gate. The
    # paths are derived from the manifest's declared inputs/outputs via the SAME default_path
    # mapping the runner uses (single PVC run-dir -> an input's path == its producer's output).
    load_all()
    batch = {"batch_id": "b1", "videos": [
        {"video_id": "fin-b1-0", "niche": "finance", "seed": 4242, "format": "myth_buster"}]}
    (tmp_path / "runs" / "b1").mkdir(parents=True)
    (tmp_path / "runs" / "b1" / "batch.json").write_text(json.dumps(batch))

    cfg = resolve_argo_args(data_root=tmp_path, batch_id="b1", video_id="fin-b1-0",
                            stage_id="05")["config"]

    # main()'s IO gate requires BOTH keys present (else p.error / exit 2).
    assert "input_paths" in cfg and "output_paths" in cfg

    m = REGISTRY["05"].manifest
    assert cfg["input_paths"] == {n: default_path(n) for n in m.inputs}
    assert cfg["output_paths"] == {n: default_path(n) for n in m.outputs}
    # stage 05: inputs include script/render-feeders, outputs map to the render binary path.
    assert cfg["input_paths"]["script"] == "script.json"
    assert cfg["output_paths"]["render"] == "renders/youtube.mp4"


def test_argo_mode_main_passes_io_gate_and_runs_stage_body(tmp_path, monkeypatch):
    # C3 end-to-end: main() in Argo mode (--batch/--video, no --config) must derive
    # input_paths/output_paths from the manifest and feed them into the StageContext, so the
    # stage body RUNS instead of aborting at the IO gate (p.error -> exit 2). We register a
    # sentinel stage that records the IO paths it received and returns OK; backends are not
    # exercised here (real-backend wiring is a host-bring-up concern), so we use a fake.
    seen: dict[str, dict] = {}

    def _sentinel(ctx):
        seen["input_paths"] = ctx.input_paths
        seen["output_paths"] = ctx.output_paths
        return None

    REGISTRY["zz_argo_io_gate"] = RegisteredStage(
        manifest=StageManifest(id="zz_argo_io_gate", inputs=["script"],
                               outputs=["render"], compute="cpu"),
        fn=_sentinel,
    )
    try:
        batch = {"batch_id": "b1", "videos": [
            {"video_id": "fin-b1-0", "niche": "finance", "seed": 7,
             "format": "myth_buster"}]}
        run_dir = tmp_path / "runs" / "b1" / "fin-b1-0"
        run_dir.mkdir(parents=True)
        (tmp_path / "runs" / "b1" / "batch.json").write_text(json.dumps(batch))
        (run_dir / "job.json").write_text(json.dumps(
            {"video_id": "fin-b1-0", "batch_id": "b1", "platform_targets": ["youtube"]}))

        monkeypatch.setenv("DATA_ROOT", str(tmp_path))
        monkeypatch.setattr("sys.argv", ["shorts.stage", "zz_argo_io_gate",
                                         "--batch", "b1", "--video", "fin-b1-0"])
        # main() builds backends for the StageContext; the sentinel never touches one, but the
        # build still needs a known mode. Force the fixture backend (CI/offline) for this stage.
        monkeypatch.setattr("shorts.stage._build_backends", lambda cfg, job: {})

        rc = main()

        assert rc == EXIT_OK            # NOT exit 2 (the old C3 abort at the IO gate)
        assert seen["input_paths"]["script"] == "script.json"
        assert seen["output_paths"]["render"] == "renders/youtube.mp4"
    finally:
        REGISTRY.pop("zz_argo_io_gate", None)


def test_unknown_video_is_a_hard_error(tmp_path):
    (tmp_path / "runs" / "b1").mkdir(parents=True)
    (tmp_path / "runs" / "b1" / "batch.json").write_text('{"batch_id":"b1","videos":[]}')
    with pytest.raises(KeyError):
        resolve_argo_args(data_root=tmp_path, batch_id="b1", video_id="ghost",
                          stage_id="00a")
