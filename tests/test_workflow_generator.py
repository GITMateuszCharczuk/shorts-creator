import yaml

from deploy.argo.generator.generate import (  # noqa: F401
    build_workflow,
    capability_env,
    retry_strategy,
)


def _manifests():
    return [{"id": "00a", "inputs": [], "outputs": ["job"], "compute": "cpu"},
            {"id": "00b", "inputs": ["job"], "outputs": ["script"], "compute": "cpu",
             "capability": "llm"},
            {"id": "05", "inputs": ["script"], "outputs": ["render"], "compute": "gpu",
             "capability": "generate_image"},
            {"id": "05x", "inputs": ["render"], "outputs": ["vision"], "compute": "gpu",
             "capability": "vlm_judge"}]


def test_dag_dependencies_come_from_inputs_outputs():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    dag = next(t for t in wf["spec"]["templates"] if "dag" in t)
    tasks = {t["name"]: t for t in dag["dag"]["tasks"]}
    assert tasks["00b"]["dependencies"] == ["00a"] and tasks["05"]["dependencies"] == ["00b"]
    assert tasks["00a"].get("dependencies", []) == []


def test_capability_drives_the_host_endpoint_env():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})

    def envof(sid):
        t = next(t for t in wf["spec"]["templates"] if t["name"] == sid)
        return {e["name"]: e["value"] for e in t["container"]["env"]}
    assert "HOST_GPU_ENDPOINT" in envof("05")
    assert "HOST_OLLAMA_ENDPOINT" in envof("00b")
    assert "HOST_VLM_ENDPOINT" in envof("05x")
    s05 = next(t for t in wf["spec"]["templates"] if t["name"] == "05")
    assert "nvidia.com/gpu" not in str(s05["container"].get("resources", {}))


def test_step_body_is_the_batch_video_one_liner():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    s05 = next(t for t in wf["spec"]["templates"] if t["name"] == "05")
    cmd = s05["container"]["command"] + s05["container"]["args"]
    assert cmd[:3] == ["python", "-m", "shorts.stage"]
    assert "--batch" in cmd and "--video" in cmd


def test_workflow_declares_its_parameters_and_retry():
    wf = build_workflow(_manifests(), retry={"retries": 3, "backoff_s": 20})
    params = {p["name"] for p in wf["spec"]["arguments"]["parameters"]}
    assert params == {"batch_id", "video_id"}
    assert retry_strategy({"retries": 3, "backoff_s": 20}) == \
        {"limit": 3, "backoff": {"duration": "20s", "factor": 2}}


def test_image_and_mount_are_parameters_and_output_is_deterministic():
    a = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30},
                       image="shorts-creator:ci", mount="/data")
    assert all(t["container"]["image"] == "shorts-creator:ci"
               for t in a["spec"]["templates"] if t.get("container"))
    b = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30},
                       image="shorts-creator:ci", mount="/data")
    assert yaml.safe_dump(a, sort_keys=True) == yaml.safe_dump(b, sort_keys=True)


def test_duplicate_output_name_is_a_hard_error():
    import pytest
    dupe = [{"id": "a", "inputs": [], "outputs": ["x"]},
            {"id": "b", "inputs": [], "outputs": ["x"]}]
    with pytest.raises(ValueError):
        build_workflow(dupe, retry={"retries": 2, "backoff_s": 30})
