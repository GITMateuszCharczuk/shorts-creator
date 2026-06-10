# M7 — The Kubernetes / Argo Deployment Profile (Variants A + B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** OPTIONAL, post-PoC. The PoC's Definition of Done is satisfied at **M6** (runner-first on the Windows/WSL2 box, ADR 0015). M7 builds the **deferred deployment profile** designed in [ADR 0015a](../../decisions/0015a-kubernetes-argo-deployment-profile.md) so "Kubernetes when I want it" is a real, tested property — not a rewrite, not marketing.

**Goal:** Make the system **genuinely Kubernetes-deployable on demand** while changing *nothing* about what runs. Build **Variant A** (the unchanged conductor as one `CronJob`, `concurrencyPolicy: Forbid` replacing the lockfile 1:1) + the **`deploy/k8s` base** (PVC = `DATA_ROOT`, the host-owned-GPU `Service`/`Endpoints`, `Secret`s), the **manifest→`WorkflowTemplate` generator** with its **regenerate-and-diff CI check** (ADR 0015a D3), **Variant B** (Argo per-stage fan-out), and **`make k8s-smoke`** — the golden offline DAG on **kind**, green through **A *and* B**. **Variant C (GPU-in-cluster) stays design-only** (ADR 0015a adopted scope: the host is Windows-only).

**Architecture:** The thinnest possible k8s layer — every cluster artifact **derives from artifacts the PoC already maintains** (the stage manifests, the M4 shared image, `DATA_ROOT`, the conductor's config), so the profile can never drift into a second orchestrator. **Variant A** runs the **unchanged M4 conductor** (`python -m shorts.run_batch`) as a Job — all orchestration stays in the tested Python. **Variant B** runs the **unchanged M4 per-stage CLI** (`python -m shorts.stage <id>`) one pod per stage, with Argo owning **only placement + retry**; the stage semantics (IO/validation/cache/exit-codes) live in the M0 Stage SDK exactly as under the conductor. The **GPU plane stays host-owned** (ADR 0001) — pods reach ComfyUI/Ollama/VLM through a `Service` with **manual `Endpoints`** pinning the host, surfaced as the same `HOST_GPU_ENDPOINT` env the stages already use. The only **new code** is small and pure: the **WorkflowTemplate generator** (~100 lines + a template, D3) and the **`host_client` path-relativization** (D4). Everything else is **k8s manifests (data)** + the kind smoke test.

**Tech Stack:** kind (local cluster on WSL2, ADR 0013) + `kubectl` + `kustomize`; **Argo Workflows** (Variant B); the M4 **shared image** (the one deployable artifact, unchanged); Python 3.12 for the generator + its unit tests; GitHub Actions for the **per-commit regenerate-and-diff** (fast) and the **nightly/manual kind smoke** (slow). No GPU in CI — the smoke runs the **fake-backend** offline DAG (ADR 0015 D2).

**Decisions made here (ADR 0015a "Open, for M7"; pinned):**
- **One policy source for retries (ADR 0015a D3 open item):** the generator does **not** invent Argo retry numbers — it reads the **same `retry` config block the M4 `RetryPolicy` reads** (retries, backoff_s) and emits the Argo `retryStrategy` from it (`limit = retries`, `backoff.duration = backoff_s`, `factor = 2`). Choreography has exactly one home; a config change moves both the conductor and the cluster.
- **The generator is the only template author (D3):** the Variant-B `WorkflowTemplate` is **never hand-edited** — `deploy/argo/generated/shorts-workflowtemplate.yaml` is committed, and **CI regenerates + diffs** it against the manifests on every commit (the new drift-catcher, replacing the old YAML↔manifest eyeball). A hand-edit fails CI.
- **kind smoke cadence (D6 open item):** **manual + nightly**, never per-commit (kind-in-CI is slow). The **per-commit** guarantee stays the M4 shared-image offline DAG + this generator diff (both fast). `make k8s-smoke` is the same target locally and in the nightly job.
- **Secrets (D5):** created from the **same host vault material** via a templated `make k8s-secrets` (`kubectl create secret` from the env/file vault → the same env names pods and the host both use); `secrets.template.yaml` carries **no real values**. Rotation beyond the ADR 0009 #10 pre-flight is **out of scope** (single-operator, D5/Open).
- **The path contract is the load-bearing rule (D4):** **every** artifact path in `job.json`/`batch.json`/stage outputs is **`DATA_ROOT`-relative**; each process resolves against its **own** `DATA_ROOT` env (`/data` in pods, the WSL2 dir on host). The host GPU client converts ComfyUI's returned **host-absolute** paths to relative **at the API boundary** — **one unit-tested function** in `shared/host_client.py`. This single rule makes runner-mode and cluster-mode **byte-compatible on disk**; M7 hardens + tests it (the M0 SDK already maps declared names to run-dir paths).
- **Variant C is design-only (ADR 0015a adopted scope):** not built. The base is **C-ready by construction** — the only diffs would be the `host-gpu` Service target + GPU `resources.limits` on the model-server Deployments (D7) — but C activates only if a **dedicated Linux GPU node** ever materializes. M7 ships A + B.
- **`concurrencyPolicy: Forbid` replaces the lockfile 1:1** (D1) in both variants' Cron objects — the M4 run-lock semantics, now Kubernetes-native; the conductor's lockfile still guards the in-pod path harmlessly.

---

## File Structure (ADR 0015a D9)

```
deploy/k8s/
  base/
    namespace.yaml                 # the `shorts` namespace
    pvc.yaml                       # PVC `shorts-data` (hostPath/local-PV = host DATA_ROOT), mounted /data
    host-gpu.yaml                  # Service `host-gpu` + manual Endpoints -> host ComfyUI/Ollama/VLM (ADR 0001)
    secrets.template.yaml          # OAuth/API-key Secret templates (NO real values committed)
    kustomization.yaml
  conductor/                       # Variant A
    cronjob.yaml                   # the daily batch (concurrencyPolicy: Forbid)
    job.yaml                       # the one-off manual-trigger Job (mirrors scripts/trigger.sh)
    kustomization.yaml
  overlays/
    kind-local/                    # kind extraMounts path + host-gateway Endpoint + the local PV
    prod/                          # real node selectors, storage class, endpoint IPs
deploy/argo/                       # Variant B
  generator/
    __init__.py
    generate.py                    # stage manifests + config -> WorkflowTemplate (retry from the conductor config)
    templates/workflowtemplate.yaml.j2
  generated/
    shorts-workflowtemplate.yaml   # COMMITTED output; CI regenerates + diffs (D3)
  cronworkflow.yaml                # the Variant-B daily trigger (concurrencyPolicy: Forbid)
shared/host_client.py              # MODIFY: to_relative() at the API boundary (D4); DATA_ROOT-env resolution
Makefile                           # cluster-up / k8s-secrets / argo-generate / k8s-smoke get real bodies
.github/workflows/k8s-generator-diff.yml   # per-commit: regenerate + diff (fast, no cluster)
.github/workflows/k8s-smoke.yml            # nightly/manual: kind + the golden offline DAG (slow)
tests/
  test_host_client_paths.py        # the D4 path contract (pure)
  test_workflow_generator.py       # the generator: DAG deps, retry mapping, step bodies (pure)
  test_k8s_smoke.py                # integration (kind), runs under `make k8s-smoke`
```

**Responsibility split:** `deploy/k8s/` = Variant A as data (the conductor wrapped in a Job); `deploy/argo/generator/` = the *only* author of the Variant-B template; `deploy/argo/generated/` = the committed, CI-diffed output; `shared/host_client.py` = the one rule (D4) that keeps disk byte-compatible across modes. **No stage, conductor, planner, or schema code changes** — M7 wraps the tested M0–M6 system; it does not modify it.

---

# Part A — The path contract (ADR 0015a D4)

The single rule that makes runner-mode and cluster-mode byte-compatible: every stored path is `DATA_ROOT`-relative, resolved against each process's own `DATA_ROOT`. The only place an absolute path appears is ComfyUI's API response — converted at the boundary.

### Task 1: `host_client.to_relative()` + DATA_ROOT-env resolution

**Files:** Modify `shared/host_client.py`; Test `tests/test_host_client_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_host_client_paths.py
import pytest
from shared.host_client import to_relative, resolve


def test_comfyui_host_absolute_path_becomes_data_root_relative():
    # ComfyUI returns a host-absolute output path; we store it relative to DATA_ROOT
    rel = to_relative("/srv/shorts-data/runs/b1/v1/scenes/01.png", data_root="/srv/shorts-data")
    assert rel == "runs/b1/v1/scenes/01.png"
    assert not rel.startswith("/")


def test_already_relative_is_unchanged():
    assert to_relative("runs/b1/v1/scenes/01.png", data_root="/srv/shorts-data") == \
        "runs/b1/v1/scenes/01.png"


def test_path_outside_data_root_is_a_hard_error():
    # a path the cluster could never resolve must fail loud, not silently leak an absolute path
    with pytest.raises(ValueError):
        to_relative("/tmp/elsewhere/x.png", data_root="/srv/shorts-data")


def test_resolve_uses_THIS_process_data_root(monkeypatch):
    # the same relative path resolves to /data in a pod and the WSL2 dir on the host
    monkeypatch.setenv("DATA_ROOT", "/data")
    assert str(resolve("runs/b1/v1/x.png")) == "/data/runs/b1/v1/x.png"
    monkeypatch.setenv("DATA_ROOT", "/srv/shorts-data")
    assert str(resolve("runs/b1/v1/x.png")) == "/srv/shorts-data/runs/b1/v1/x.png"
```

- [ ] **Step 2: Implement in `shared/host_client.py`**

```python
import os
from pathlib import Path


def to_relative(path: str, *, data_root: str) -> str:
    """ADR 0015a D4: convert ComfyUI's host-ABSOLUTE output path to a DATA_ROOT-relative one AT
    THE API BOUNDARY — the only place an absolute path is ever allowed. A path outside DATA_ROOT
    is unreconstructable in a pod, so we fail loud rather than store a path the cluster can't resolve."""
    p = Path(path)
    if not p.is_absolute():
        return path
    try:
        return str(p.relative_to(data_root))
    except ValueError:
        raise ValueError(f"{path!r} is outside DATA_ROOT {data_root!r} — cannot store cross-mode")


def resolve(rel_path: str, *, data_root: str | None = None) -> Path:
    """Resolve a DATA_ROOT-relative path against THIS process's DATA_ROOT (/data in a pod, the WSL2
    dir on the host). Every process maps the same relative path to its own mount (D4)."""
    root = data_root or os.environ["DATA_ROOT"]
    return Path(root) / rel_path
```

- [ ] **Step 3: Wire** — the host GPU client (the function that calls ComfyUI's `/history`/`/view` and records output paths) routes every returned path through `to_relative(..., data_root=os.environ["DATA_ROOT"])` before it lands in any stage output; stages read inputs via `resolve(...)`. Add a one-line note that the M0 `ctx` already maps declared names to run-dir-relative paths — this task only closes the **ComfyUI boundary** leak.
- [ ] **Step 4: Run** → `uv run pytest tests/test_host_client_paths.py -v` → PASS (4). **Commit.**

```bash
git add shared/host_client.py tests/test_host_client_paths.py
git commit -m "feat(m7): the DATA_ROOT-relative path contract — byte-compatible runner/cluster disk (ADR 0015a D4)"
```

---

# Part B — Variant A: conductor-in-cluster (the minimal lift)

### Task 2: The `deploy/k8s/base` — namespace, PVC, host-GPU Service, Secrets

**Files:** Create `deploy/k8s/base/{namespace,pvc,host-gpu,secrets.template,kustomization}.yaml`

- [ ] **Step 1: `namespace.yaml`** → the `shorts` namespace.
- [ ] **Step 2: `pvc.yaml`** → PVC `shorts-data` bound to a **hostPath/local PV** whose backing dir **is the host `DATA_ROOT`** (ADR 0015a D2), `accessModes: [ReadWriteOnce]`, mounted at the canonical **`/data`** in every pod. (The base declares the PVC + a local-PV stub; the *path* is set per-overlay — Task 4.)
- [ ] **Step 3: `host-gpu.yaml`** → a headless `Service` `host-gpu` **with manual `Endpoints`** pointing at the host's ComfyUI/Ollama/VLM (ADR 0001 — the GPU plane never enters the cluster in this profile). Pods get `HOST_GPU_ENDPOINT=http://host-gpu.shorts.svc:8188` (and the Ollama/VLM ports) — the same env the stages already use; the host-health gate (ADR 0003) is the same HTTP check.
- [ ] **Step 4: `secrets.template.yaml`** → `Secret` templates for the YouTube/TikTok OAuth material + API keys, projected to the **same env names** the host vault uses (D5). **No real values committed.** `make k8s-secrets` creates the real Secret from the host vault.
- [ ] **Step 5: `kustomization.yaml`** → bundles the base. **Validate** (integration): `kubectl --dry-run=client -k deploy/k8s/base`. **Commit.**

```bash
git add deploy/k8s/base/
git commit -m "feat(m7): deploy/k8s base — namespace, PVC=DATA_ROOT, host-gpu Service/Endpoints, Secrets (ADR 0015a D2/D5)"
```

### Task 3: Variant A — the conductor `CronJob` + one-off `Job`

**Files:** Create `deploy/k8s/conductor/{cronjob,job,kustomization}.yaml`

- [ ] **Step 1: `cronjob.yaml`** → the daily batch: the M4 **shared image**, `command: ["python","-m","shorts.run_batch"]`, `DATA_ROOT=/data`, the PVC mounted at `/data`, the `host-gpu` env + Secrets, `schedule` = the nightly window, **`concurrencyPolicy: Forbid`** (replaces the M4 lockfile 1:1, D1), `restartPolicy: Never` + `backoffLimit` aligned to the conductor's own retry posture. `TimeoutSeconds`/`activeDeadlineSeconds` = the M4 batch watchdog (10h).
- [ ] **Step 2: `job.yaml`** → the **one-off manual trigger** (mirrors `scripts/trigger.sh`): the same pod spec, no schedule, `kubectl create -f` (or `kubectl create job --from=cronjob/shorts-batch`). Supports `--dry-run` by overriding `args`.
- [ ] **Step 3: `kustomization.yaml`** → base + conductor. **Validate** (integration): `kubectl --dry-run=client -k deploy/k8s/conductor`. **Commit.**

```bash
git add deploy/k8s/conductor/
git commit -m "feat(m7): Variant A — conductor CronJob + one-off Job (Forbid replaces the lockfile, ADR 0015a D1)"
```

### Task 4: The `kind-local` + `prod` overlays + `make cluster-up`/`k8s-secrets`

**Files:** Create `deploy/k8s/overlays/kind-local/`, `deploy/k8s/overlays/prod/`; Modify `Makefile`

- [ ] **Step 1: `overlays/kind-local/`** → the kind cluster config with **`extraMounts`** mapping the host `DATA_ROOT` (the WSL2 ext4 dir, ADR 0013) into the node at the PV's hostPath; the `host-gpu` Endpoints set to **kind's host-gateway** address; the local-PV path patch. This is what makes the local cluster read/write the *same* `DATA_ROOT` as runner-mode.
- [ ] **Step 2: `overlays/prod/`** → real node selectors, a storage class, and the endpoint IPs for a non-kind cluster (the C-ready seam: only the `host-gpu` target changes if the GPU ever moves in-cluster, D7).
- [ ] **Step 3: `make cluster-up`** → `kind create cluster --config overlays/kind-local/kind.yaml` (idempotent: skip if it exists), then `kubectl apply -k deploy/k8s/overlays/kind-local`. **`make k8s-secrets`** → `kubectl create secret generic shorts-creds --from-env-file=$VAULT ...` from the host vault (D5). **`make cluster-down`** → `kind delete cluster`.
- [ ] **Step 4: Validate** (integration): `kustomize build deploy/k8s/overlays/kind-local | kubectl --dry-run=client apply -f -`. **Commit.**

```bash
git add deploy/k8s/overlays/ Makefile
git commit -m "feat(m7): kind-local + prod overlays + cluster-up/k8s-secrets targets (ADR 0015a D2)"
```

---

# Part C — The template generator (ADR 0015a D3)

The generator finally earns its keep: it emits the Variant-B `WorkflowTemplate` **from the stage manifests**, so the DAG is never hand-authored and can't drift.

### Task 5: `generate.py` — manifests → `WorkflowTemplate` (retry from the conductor config)

**Files:** Create `deploy/argo/generator/{__init__.py,generate.py,templates/workflowtemplate.yaml.j2}`; Test `tests/test_workflow_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workflow_generator.py
import yaml
from deploy.argo.generator.generate import build_workflow, retry_strategy


def _manifests():
    return [{"id": "00a", "inputs": [], "outputs": ["job"], "compute": "cpu"},
            {"id": "00b", "inputs": ["job"], "outputs": ["script"], "compute": "cpu", "capability": "llm"},
            {"id": "05", "inputs": ["script"], "outputs": ["render"], "compute": "gpu", "capability": "generate_image"}]


def test_dag_dependencies_come_from_inputs_outputs():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    tasks = {t["name"]: t for t in wf["spec"]["templates"][0]["dag"]["tasks"]}
    assert tasks["00b"]["dependencies"] == ["00a"]          # 00b consumes 00a's `job`
    assert tasks["05"]["dependencies"] == ["00b"]           # 05 consumes 00b's `script`
    assert tasks["00a"].get("dependencies", []) == []       # root


def test_every_step_body_is_the_same_one_liner_bar_the_id():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    cmds = [t["container"]["command"] + t["container"]["args"]
            for t in wf["spec"]["templates"] if t.get("container")]
    for c in cmds:
        assert c[:3] == ["python", "-m", "shorts.stage"]    # the dumb per-stage entrypoint (D1/B)


def test_retry_strategy_is_derived_from_THE_CONDUCTOR_config():
    rs = retry_strategy({"retries": 3, "backoff_s": 20})
    assert rs["limit"] == 3 and rs["backoff"]["duration"] == "20s" and rs["backoff"]["factor"] == 2


def test_gpu_stage_gets_the_host_gpu_env_not_an_in_cluster_gpu_request():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    s05 = next(t for t in wf["spec"]["templates"] if t["name"] == "05")
    env = {e["name"]: e for e in s05["container"]["env"]}
    assert "HOST_GPU_ENDPOINT" in env                       # GPU stays host-owned (ADR 0001)
    assert "nvidia.com/gpu" not in str(s05["container"].get("resources", {}))   # NOT Variant C


def test_output_is_deterministic_yaml():
    a = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    b = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    assert yaml.safe_dump(a, sort_keys=True) == yaml.safe_dump(b, sort_keys=True)   # CI-diff stable
```

- [ ] **Step 2: Implement `deploy/argo/generator/generate.py`**

```python
"""manifest -> Argo WorkflowTemplate (ADR 0015a D3). The ONLY author of the Variant-B template;
CI regenerates + diffs the committed output. Choreography (retry) is read from the SAME config the
M4 conductor uses — one policy source. Run: python -m deploy.argo.generator.generate > generated/...yaml"""
import json
import sys
from pathlib import Path

_IMAGE = "shorts-creator:latest"        # the M4 shared image (the one deployable artifact)


def retry_strategy(retry: dict) -> dict:
    """Map the conductor's RetryPolicy config to Argo retryStrategy — same numbers, one source."""
    return {"limit": retry["retries"],
            "backoff": {"duration": f"{retry['backoff_s']}s", "factor": 2}}


def _producer_of(manifests: list[dict]) -> dict[str, str]:
    return {out: m["id"] for m in manifests for out in m.get("outputs", [])}


def build_workflow(manifests: list[dict], *, retry: dict) -> dict:
    producer = _producer_of(manifests)
    dag_tasks, templates = [], []
    for m in manifests:
        deps = sorted({producer[i] for i in m.get("inputs", []) if i in producer})
        dag_tasks.append({"name": m["id"], "template": m["id"],
                          **({"dependencies": deps} if deps else {})})
        env = [{"name": "DATA_ROOT", "value": "/data"},
               {"name": "HOST_GPU_ENDPOINT", "value": "http://host-gpu.shorts.svc:8188"}]
        templates.append({
            "name": m["id"], "retryStrategy": retry_strategy(retry),
            "container": {"image": _IMAGE, "command": ["python", "-m", "shorts.stage"],
                          "args": [m["id"], "--video", "{{workflow.parameters.video_id}}"],
                          "env": env,
                          "volumeMounts": [{"name": "data", "mountPath": "/data"}]}})
        # NOTE: compute=='gpu' stages still reach the HOST GPU over HTTP (ADR 0001) — NO
        # nvidia.com/gpu request here; that would be Variant C (design-only).
    dag = {"name": "shorts-dag", "dag": {"tasks": dag_tasks}}
    return {"apiVersion": "argoproj.io/v1alpha1", "kind": "WorkflowTemplate",
            "metadata": {"name": "shorts-batch", "namespace": "shorts"},
            "spec": {"entrypoint": "shorts-dag", "templates": [dag, *templates],
                     "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "shorts-data"}}]}}


def main() -> int:
    import yaml
    root = Path(__file__).resolve().parents[3]
    manifests = [json.loads(p.read_text()) for p in sorted(root.glob("stages/*/manifest.json"))]
    retry = json.loads((root / "config/defaults.json").read_text()).get("retry", {"retries": 2, "backoff_s": 30})
    sys.stdout.write(yaml.safe_dump(build_workflow(manifests, retry=retry), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Write `templates/workflowtemplate.yaml.j2`** as the documented shape (the implementation above builds the dict directly + `yaml.safe_dump` for determinism; the `.j2` is kept as the human-readable reference of the target shape). **Run** → PASS (5). **Commit.**

```bash
git add deploy/argo/generator/ tests/test_workflow_generator.py
git commit -m "feat(m7): WorkflowTemplate generator — DAG from manifests, retry from conductor config (ADR 0015a D3)"
```

### Task 6: Generate the committed template + the regenerate-and-diff CI check

**Files:** Create `deploy/argo/generated/shorts-workflowtemplate.yaml`, `.github/workflows/k8s-generator-diff.yml`

- [ ] **Step 1: Generate + commit the output** → `python -m deploy.argo.generator.generate > deploy/argo/generated/shorts-workflowtemplate.yaml`. This is the **committed** artifact.
- [ ] **Step 2: Write `.github/workflows/k8s-generator-diff.yml`** (per-commit, fast, no cluster):

```yaml
name: k8s-generator-diff
on: [push, pull_request]
jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pyyaml
      - name: Regenerate and diff (the D3 drift-catcher)
        run: |
          python -m deploy.argo.generator.generate > /tmp/regenerated.yaml
          diff -u deploy/argo/generated/shorts-workflowtemplate.yaml /tmp/regenerated.yaml \
            || { echo "::error::generated WorkflowTemplate is stale — run 'make argo-generate'"; exit 1; }
```

- [ ] **Step 3: Wire `make argo-generate`** → the generate command above (the only sanctioned way to update the committed YAML). **Commit.**

```bash
git add deploy/argo/generated/ .github/workflows/k8s-generator-diff.yml Makefile
git commit -m "feat(m7): committed WorkflowTemplate + regenerate-and-diff CI (the D3 drift-catcher)"
```

---

# Part D — Variant B: Argo fan-out

### Task 7: The Argo `CronWorkflow` (mirrors Variant A's schedule + Forbid)

**Files:** Create `deploy/argo/cronworkflow.yaml`

- [ ] **Step 1: `cronworkflow.yaml`** → references the generated `WorkflowTemplate` (`workflowTemplateRef: shorts-batch`), the nightly `schedule`, **`concurrencyPolicy: Forbid`** (mirrors A, D1), and the per-batch parameters (the planned `video_id`s — Argo fans out one pod per stage per video). The artifact volume is the same `shorts-data` PVC. Note the **single-node caveat (D8)**: multi-node fan-out would require the PVC to go RWX (NFS/object store) — recorded, deferred.
- [ ] **Step 2: Validate** (integration): `argo lint deploy/argo/cronworkflow.yaml` + `kubectl --dry-run=client`. **Commit.**

```bash
git add deploy/argo/cronworkflow.yaml
git commit -m "feat(m7): Variant B — Argo CronWorkflow over the generated template (Forbid mirrors A, ADR 0015a D1/D8)"
```

---

# Part E — The smoke test (ADR 0015a D6) — the M7 gate

### Task 8: `make k8s-smoke` — the golden offline DAG on kind, through A *and* B

The profile is tested the same way the runner is: spin kind, apply the profile, run the **golden offline DAG with fakes** (no GPU), assert the golden `posts` record lands on the PVC.

**Files:** Create `tests/test_k8s_smoke.py`, `.github/workflows/k8s-smoke.yml`; Modify `Makefile`

- [ ] **Step 1: Write the smoke test** `tests/test_k8s_smoke.py` (integration — runs under `make k8s-smoke`, not per-commit)

```python
import pytest


@pytest.mark.integration
def test_variant_a_runs_the_golden_dag_as_a_job(kind_cluster, data_root_pvc):
    """Variant A: the conductor Job runs the golden offline DAG with fake backends; the golden
    posts record lands on the PVC (ADR 0015a D6)."""
    run_one_off_job(image="shorts-creator:ci", args=["--profiles", "finance", "--dry-run-backends", "fake"])
    assert (data_root_pvc / "runs").glob("*/“*”/posts.json")     # a posts artifact was produced
    assert no_pod_errors(namespace="shorts")


@pytest.mark.integration
def test_variant_b_runs_the_golden_dag_through_argo(kind_cluster, argo_installed, data_root_pvc):
    """Variant B: the same golden DAG via the generated WorkflowTemplate, one pod per stage."""
    submit_cronworkflow_now("deploy/argo/cronworkflow.yaml")
    assert wait_succeeded(workflow="shorts-batch", timeout_s=900)
    assert (data_root_pvc / "runs").glob("*/“*”/posts.json")
```

- [ ] **Step 2: Implement the harness helpers** — `kind_cluster` (create/reuse via `make cluster-up`), `argo_installed` (apply the Argo quick-start into the namespace), `data_root_pvc` (the kind `extraMounts` host dir), `run_one_off_job`/`submit_cronworkflow_now`/`wait_succeeded`/`no_pod_errors` (thin `kubectl`/`argo` wrappers). The image is the **M4 `ci` image** with `backends=fake` (ADR 0015 D2) — **no GPU, no network**; the `host-gpu` Service is unused on the fake path.
- [ ] **Step 3: Write `.github/workflows/k8s-smoke.yml`** (nightly + `workflow_dispatch`): set up kind, `docker build --target ci`, `kind load`, `make k8s-smoke`. Not in the per-commit path (D6).
- [ ] **Step 4: Wire `make k8s-smoke`** → `cluster-up` → load the image → `pytest tests/test_k8s_smoke.py -m integration`. **Run locally** → PASS (2). **Commit.**

```bash
git add tests/test_k8s_smoke.py .github/workflows/k8s-smoke.yml Makefile
git commit -m "feat(m7): make k8s-smoke — golden offline DAG on kind through Variant A and B (the M7 gate, ADR 0015a D6)"
```

---

## M7 Acceptance Checklist (the testable "done")

- [ ] **The path contract holds (D4):** `to_relative` converts ComfyUI host-absolute paths to `DATA_ROOT`-relative at the boundary (and hard-fails outside `DATA_ROOT`); `resolve` maps a relative path to `/data` in a pod and the WSL2 dir on the host → Task 1.
- [ ] **Variant A is data, not code:** the unchanged conductor runs as a `CronJob` (+ one-off `Job`), `concurrencyPolicy: Forbid` replacing the lockfile, against PVC=`DATA_ROOT` and the host-owned-GPU `Service`/`Endpoints`; Secrets come from the host vault → Tasks 2–4.
- [ ] **The generator is the only template author (D3):** `build_workflow` derives the DAG from the stage manifests (deps from inputs/outputs), every step is the same `python -m shorts.stage <id>` one-liner, the retry strategy is read from the **conductor's config**, GPU stages reach the **host** GPU (no `nvidia.com/gpu` request), and output is deterministic; **CI regenerates + diffs** the committed YAML → Tasks 5–6.
- [ ] **Variant B fans out:** the Argo `CronWorkflow` runs the generated template one pod per stage, `Forbid` mirroring A → Task 7.
- [ ] **The M7 gate:** `make k8s-smoke` runs the **golden offline DAG with fakes on kind**, green through **Variant A *and* Variant B**, with the golden `posts` record on the PVC; the per-commit guarantee remains the M4 shared image + the generator diff → Task 8.
- [ ] **Variant C stays design-only:** no GPU-in-cluster artifacts are built; the base is C-ready (only the `host-gpu` target + GPU resource requests would change) → the decisions header + ADR 0015a D7.
- [ ] CI: the generator diff is **per-commit** (fast); the kind smoke is **nightly/manual** (slow) → Tasks 6, 8.

---

## Self-Review

**ADR 0015a coverage:** Variant A (conductor CronJob + Job, Forbid-for-lockfile) → B (Tasks 2–4, D1/D2); the base (PVC=`DATA_ROOT`, host-gpu Service/Endpoints, Secrets) → Task 2 (D2/D5); the path contract → A (Task 1, D4 — the single byte-compatibility rule); the template generator + regenerate-diff CI → C (Tasks 5–6, D3); Variant B Argo fan-out → D (Task 7, D1/D8); `make k8s-smoke` golden-DAG-on-kind through A *and* B → E (Task 8, D6 — the gate). Variant C → **design-only**, not built (the decisions header + D7 adopted scope); the base is C-ready by construction. The three ADR 0015a "Open, for M7" items are pinned: retry mapping = one config source (Task 5), kind-smoke cadence = nightly/manual (Task 8), secrets = host-vault-templated (Task 2/4, rotation out of scope).

**Placeholder scan:** no "TBD"/"add error handling". The integration seams (the kind/Argo/kubectl harness helpers in Task 8, the `kubectl --dry-run` validations) are documented and run under `make k8s-smoke`; the pure logic — `to_relative`/`resolve` (Task 1) and the full `build_workflow`/`retry_strategy` generator (Task 5) — is implemented + unit-tested with no GPU/cluster. The `.j2` template is explicitly the human-readable reference; the dict-build + `yaml.safe_dump` is the deterministic source (so the CI diff is stable).

**Type/contract consistency vs M0–M6:** reuses the M0 stage **manifests** (`id`/`inputs`/`outputs`/`compute`/`capability`) as the generator's sole input (no new metadata); the M4 **shared image** + the **`python -m shorts.stage`/`shorts.run_batch`** entrypoints unchanged (Variant B's step body is exactly the M4 per-stage CLI, A's is the M4 conductor); the conductor's **`retry` config** is the single choreography source (Task 5); `HOST_GPU_ENDPOINT` is the same env the stages already resolve (ADR 0001/0015); the `DATA_ROOT`-relative contract matches the M0 `ctx` path mapping (Task 1 only closes the ComfyUI boundary). **No stage, conductor, planner, schema, or gate code changes** — M7 wraps the M0–M6 system; the smoke test proves the wrapper, the M4/M6 suites prove the system.

**Scope:** five parts, one gate (the golden DAG green through A and B on kind). Optional and post-PoC — the Chapter 1 DoD is M6's. A (path contract) and C (generator) are pure + independent; B (Variant A) and D (Variant B) are the manifests; E depends on all. This is the last planned milestone: with it, "runner-first PoC → A → B" is a built, tested ladder, and C is a documented one-node-away design — the operator's "Kubernetes when I want it," delivered without ever forking what runs.
