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
    # BRING-UP DEPENDENCY: run_batch.main() does not yet accept --profiles/--backends; wiring the
    # fake-backend offline path into the CLI is part of the M6 Task 12 on-box bring-up (the same
    # _build_backends NotImplementedError seam). This integration gate runs only under
    # `make k8s-smoke` on a real box, after that wiring lands.
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
