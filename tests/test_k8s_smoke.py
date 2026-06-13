import pytest

from tests.helpers.k8s_smoke import (
    argo_installed,
    data_root_pvc,
    kind_cluster,
    no_pod_errors,
    run_one_off_job,
    submit_cronworkflow_now,
    wait_succeeded,
)


@pytest.mark.integration
def test_variant_a_runs_the_golden_dag_as_a_job():
    kind_cluster()
    run_one_off_job(image="shorts-creator:ci", args=["--profiles", "finance", "--backends", "fake"])
    assert list((data_root_pvc() / "runs").glob("*/*/posts.json"))     # a posts artifact landed
    assert no_pod_errors(namespace="shorts")


@pytest.mark.integration
def test_variant_b_runs_the_golden_dag_through_argo():
    kind_cluster()
    argo_installed()
    submit_cronworkflow_now("deploy/argo/cronworkflow.yaml")
    assert wait_succeeded(workflow="shorts-batch", timeout_s=900)
    assert list((data_root_pvc() / "runs").glob("*/*/posts.json"))
    assert no_pod_errors(namespace="shorts")
