"""M7 Task 9 — the `make k8s-smoke` harness: thin, REAL kubectl/argo subprocess wrappers
that drive the golden offline DAG on a kind cluster through Variant A (the conductor as a
k8s Job — deploy/k8s/conductor/{cronjob,job}.yaml) and Variant B (the Argo CronWorkflow —
deploy/argo/cronworkflow.yaml). ADR 0015a (OPTIONAL post-PoC k8s/Argo profile, D6).

These functions touch a LIVE cluster: they shell out to `kind`, `kubectl` and `argo`, none
of which exist in the GPU-free CI/dev sandbox. They therefore run ONLY under
`make k8s-smoke` on a real box (or the nightly k8s-smoke CI job). The two tests that call
them are `@pytest.mark.integration` and so are DESELECTED by the default sweep
(`-m "not integration and not soak"`) — they collect here but never execute. Nothing in
this module imports a cluster client at import time, so collection stays clean offline.
"""
import json
import subprocess
import time
from pathlib import Path

NAMESPACE = "shorts"
IMAGE_TAG = "shorts-creator:ci"
# Argo's pinned quick-start manifest (minimal: just the workflow-controller + CRDs, no UI/auth).
ARGO_QUICK_START = (
    "https://github.com/argoproj/argo-workflows/releases/download/"
    "v3.5.8/quick-start-minimal.yaml"
)


def kind_cluster() -> None:
    """Bring up the kind cluster (the kind-local overlay) and load the CI image into its node.

    `make cluster-up` is idempotent (creates the cluster only if absent, then applies the
    overlay). `kind load docker-image` makes shorts-creator:ci resolvable in-cluster without a
    registry — the manifests reference that exact tag with imagePullPolicy defaulting to
    IfNotPresent, so the loaded image is used directly.
    """
    subprocess.run(["make", "cluster-up"], check=True)
    subprocess.run(["kind", "load", "docker-image", IMAGE_TAG], check=True)


def argo_installed(namespace: str = NAMESPACE) -> None:
    """Install the Argo Workflows controller into <namespace> and wait for it to be ready.

    Variant B needs the argoproj CRDs (CronWorkflow/Workflow) + the workflow-controller running
    before `argo submit` will do anything. We apply the pinned quick-start-minimal release and
    block on the controller Deployment rolling out so the subsequent submit isn't racing the CRD
    registration.
    """
    subprocess.run(
        ["kubectl", "apply", "-n", namespace, "-f", ARGO_QUICK_START], check=True
    )
    subprocess.run(
        ["kubectl", "rollout", "status", "-n", namespace,
         "deploy/workflow-controller", "--timeout=180s"],
        check=True,
    )


def data_root_pvc() -> Path:
    """The host-side DATA_ROOT the cluster bind-mounts into the PVC (kind extraMounts).

    `make -s print-data-root` echoes the resolved DATA_ROOT; the kind-local overlay bind-mounts
    that same tree into the node and surfaces it through the `shorts-data` PVC, so artifacts the
    in-cluster conductor writes under /data/runs land here on the host where the test can glob
    them.
    """
    out = subprocess.check_output(["make", "-s", "print-data-root"])
    return Path(out.decode().strip())


def run_one_off_job(*, image, args, timeout_s: int = 600) -> None:
    """Variant A — run the golden DAG as a one-off k8s Job and block until it completes.

    Approach: clone the committed CronJob's jobTemplate into a fresh Job with
    `kubectl create job <name> --from=cronjob/shorts-batch` (the cluster analogue of
    `make trigger` / deploy/k8s/conductor/job.yaml), then patch the conductor container's `args`
    so the smoke run is the GPU-free golden path (`--profiles finance --backends fake`). We wait
    on `condition=complete`; if the Job instead reaches `condition=failed` (or the wait times
    out) we raise so the test fails loudly. `image` mirrors the CronJob's container image and is
    asserted to match so a stale --from clone can't silently run the wrong build.

    NOTE: exercised only on a real cluster (integration); never runs in the GPU-free sweep.
    """
    name = "shorts-smoke"
    # Start from the committed CronJob so the podSpec (mounts, env, host-gpu endpoints) is
    # identical to a scheduled run — only the args differ for the offline golden path.
    subprocess.run(
        ["kubectl", "create", "job", name, "--from=cronjob/shorts-batch", "-n", NAMESPACE],
        check=True,
    )
    # Override the conductor's args to the GPU-free golden DAG (fake backends, single profile).
    # /containers/0 is the `conductor` container defined in the CronJob jobTemplate.
    patch = {"spec": {"template": {"spec": {"containers": [
        {"name": "conductor", "image": image, "args": list(args)}]}}}}
    subprocess.run(
        ["kubectl", "patch", "job", name, "-n", NAMESPACE,
         "--type=strategic", "-p", json.dumps(patch)],
        check=True,
    )
    # Block until the Job completes; a failed Job trips the second wait and we raise.
    try:
        subprocess.run(
            ["kubectl", "wait", "--for=condition=complete", f"job/{name}",
             "-n", NAMESPACE, f"--timeout={timeout_s}s"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        # Surface whether it actually FAILED (vs merely slow) for a clearer test signal.
        failed = subprocess.run(
            ["kubectl", "get", f"job/{name}", "-n", NAMESPACE,
             "-o", "jsonpath={.status.conditions[?(@.type=='Failed')].status}"],
            capture_output=True, text=True,
        ).stdout.strip()
        raise AssertionError(
            f"one-off Job {name!r} did not complete within {timeout_s}s "
            f"(Failed={failed or 'unknown'})"
        ) from e


def submit_cronworkflow_now(path, *, timeout_s: int = 900) -> None:
    """Variant B — register the CronWorkflow then trigger one run NOW (don't wait for 02:00).

    `argo cron create <path>` registers deploy/argo/cronworkflow.yaml (the `shorts-nightly`
    CronWorkflow whose workflowSpec plans then fans out the committed shorts-batch
    WorkflowTemplate). `argo submit --from cronwf/shorts-nightly` launches an immediate Workflow
    from that schedule without altering the cron cadence. We name the launched Workflow
    `shorts-batch` deterministically so `wait_succeeded(workflow="shorts-batch", ...)` can find
    it. timeout_s bounds the submit/registration calls; the run itself is awaited by
    wait_succeeded.

    NOTE: exercised only on a real cluster (integration).
    """
    subprocess.run(
        ["argo", "cron", "create", str(path), "-n", NAMESPACE], check=True,
        timeout=timeout_s,
    )
    subprocess.run(
        ["argo", "submit", "--from", "cronwf/shorts-nightly", "-n", NAMESPACE,
         "--name", "shorts-batch"],
        check=True, timeout=timeout_s,
    )


def wait_succeeded(*, workflow, timeout_s) -> bool:
    """Poll an Argo Workflow's phase until terminal. True on Succeeded; raise on Failed/Error;
    False if it's still running when timeout_s elapses.

    Reads `argo get <workflow> -o json` and inspects `.status.phase` (Argo's terminal phases are
    Succeeded / Failed / Error; transient are Pending / Running). We sleep between polls rather
    than relying on `argo wait` so a Failed/Error run raises immediately with the phase rather
    than blocking to the deadline.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        out = subprocess.check_output(
            ["argo", "get", workflow, "-n", NAMESPACE, "-o", "json"]
        )
        phase = json.loads(out).get("status", {}).get("phase", "")
        if phase == "Succeeded":
            return True
        if phase in ("Failed", "Error"):
            raise AssertionError(f"workflow {workflow!r} terminated in phase {phase!r}")
        time.sleep(5)
    return False


def no_pod_errors(*, namespace) -> bool:
    """True iff no pod in <namespace> is in an error state.

    Flags a pod-level phase of `Failed`, or any container stuck waiting in `CrashLoopBackOff` /
    `ImagePullBackOff` / `ErrImagePull` / `Error`, or terminated with reason `Error`. Used as a
    belt-and-braces assert after the DAG run so a green Job/Workflow that nonetheless left a
    crashlooping sidecar still fails the smoke.
    """
    bad_waiting = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "Error"}
    out = subprocess.check_output(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
    )
    for pod in json.loads(out).get("items", []):
        status = pod.get("status", {})
        if status.get("phase") == "Failed":
            return False
        for cs in status.get("containerStatuses", []):
            state = cs.get("state", {})
            waiting = state.get("waiting") or {}
            if waiting.get("reason") in bad_waiting:
                return False
            terminated = state.get("terminated") or {}
            if terminated.get("reason") == "Error":
                return False
    return True
