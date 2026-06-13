# M7 — The Kubernetes / Argo Deployment Profile (Variants A + B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** OPTIONAL, post-PoC. The PoC's Definition of Done is satisfied at **M6** (runner-first on the Windows/WSL2 box, ADR 0015). M7 builds the **deferred deployment profile** designed in [ADR 0015a](../../decisions/0015a-kubernetes-argo-deployment-profile.md) so "Kubernetes when I want it" is a real, tested property — not a rewrite, not marketing.

**Goal:** Make the system **genuinely Kubernetes-deployable on demand** while changing *nothing* about what runs. Build **Variant A** (the unchanged conductor as one `CronJob`, `concurrencyPolicy: Forbid` + the lockfile/reconciler together replacing the run-lock) + the **`deploy/k8s` base** (PVC = `DATA_ROOT`, the host-owned-GPU `Service`/`Endpoints`, `Secret`s), the **manifest→`WorkflowTemplate` generator** with its **regenerate-and-diff CI check** (ADR 0015a D3), **Variant B** (Argo per-stage fan-out, video list from the planner — never hand-authored), and **`make k8s-smoke`** — the golden offline DAG on **kind**, green through **A *and* B**. **Variant C (GPU-in-cluster) stays design-only** (ADR 0015a adopted scope: the host is Windows-only).

**Architecture:** The thinnest possible k8s layer — every cluster artifact **derives from artifacts the PoC already maintains** (the stage manifests, the M4 shared image, `DATA_ROOT`, the conductor's retry config), so the profile can never drift into a second orchestrator. **Variant A** runs the **unchanged M4/M6 conductor** (`python -m shorts.run_batch`) as a Job. **Variant B** runs the **per-stage CLI** one pod per (stage, video); the stage semantics (IO/validation/cache/exit-codes) live in the M0 Stage SDK exactly as under the conductor. A **single per-stage CLI serves both modes** — it accepts either the explicit `--run-dir/--seed/--config` (conductor) **or** `--batch/--video` (Argo, resolving run-dir/seed/config from `batch.json` on the PVC). The **GPU plane stays host-owned** (ADR 0001) — pods reach ComfyUI/Ollama/VLM through a `Service` with **manual `Endpoints`** pinning the host, with **per-capability** endpoint envs. The only **new code** is small and pure: the **WorkflowTemplate generator** (D3), the **`host_client` path-relativization** (D4), and the stage CLI's `--batch/--video` resolver. Everything else is **k8s manifests (data)** + the kind smoke test.

**Tech Stack:** kind + `kubectl` + `kustomize` + the **`argo` CLI** (Variant B + linting); **Argo Workflows**; the M4 **shared image** (the one deployable artifact, unchanged); Python 3.12 for the generator + the resolver + their unit tests; GitHub Actions for the **per-commit regenerate-and-diff** (fast) and the **nightly/manual kind smoke** (slow). No GPU in CI — the smoke runs the **fake-backend** offline DAG (ADR 0015 D2). **kind requires `dockerd` running inside the WSL2 distro (native), not the Docker-Desktop WSL2 backend** (ADR 0013) — a `make cluster-up` prerequisite check.

**Decisions made here (ADR 0015a "Open, for M7" + the review's gaps; pinned):**
- **One per-stage CLI, two arg modes (resolves the entrypoint mismatch):** `shorts/stage.py` keeps the M4 explicit mode (`--run-dir/--seed/--config`) **and** gains an Argo mode (`--batch <id> --video <id>`) that reads `runs/<batch>/batch.json` on the PVC and resolves that video's run-dir, seed, and per-stage config. Both modes call the identical stage body — Variant A (conductor) and Variant B (Argo) are byte-identical in what runs.
- **Retry is single-sourced from the conductor, not a phantom file:** the generator imports the **M4 `RetryPolicy` defaults from `shared/conductor/retry.py`** (and the same optional config override the conductor reads) — there is no invented `config/defaults.json`. `limit = retries`, `backoff.duration = f"{backoff_s}s"`, `factor = 2`. A retry change moves both the conductor and the cluster from one source.
- **The generator honors `capability` (the dead seam, now live):** a `CAPABILITY_ENV` data map emits the **right host endpoint per stage** — `HOST_GPU_ENDPOINT` (:8188 ComfyUI) for `generate_image`/`img2vid`/`restore`, `HOST_OLLAMA_ENDPOINT` (:11434) for `llm`, `HOST_VLM_ENDPOINT` for `vlm_judge` — plus `DATA_ROOT`. Adding a capability is a one-line map entry, not code surgery. GPU stages still reach the **host** (no `nvidia.com/gpu` request — that's Variant C).
- **The image tag + mount path are generator parameters:** `--image` (default **`shorts-creator:ci`** — what the smoke builds/loads; the **prod overlay patches the tag via kustomize `images:`**) and `--mount` (default **`/data`** — the same value the PVC `volumeMount` uses). No hardcoded `:latest`; the committed YAML and the smoke image agree.
- **Variant B's video list comes from the planner, never hand-authored (the drift fix):** the CronWorkflow's entry DAG is two steps — (1) **`plan`** runs `shorts.run_batch --plan-only` (writes `batch.json` to the PVC, emits the planned `video_id`s as an Argo output parameter); (2) a **`withParam` fan-out** instantiates the per-video stage-DAG `WorkflowTemplate` once per planned `video_id`. `cronworkflow.yaml` carries **no** video IDs. The `WorkflowTemplate` declares `spec.arguments.parameters: [batch_id, video_id]`.
- **The PVC makes the RWX swap a one-line overlay patch (D8):** `base/pvc.yaml` sets `storageClassName: ""` (manual bind) and **`accessModes` is a kustomize patch target** — the `kind-local`/`prod` overlays set `ReadWriteOnce` (single node) vs `ReadWriteMany` (multi-node NFS/object, the deferred cost). `hostPath`/local-PV is the kind-local backing; prod patches the storage class.
- **The host-GPU reachability mechanism is explicit (D2; the load-bearing networking):** `make host-gateway-ip` discovers the Docker bridge gateway (`ip route | awk '/default/{print $3}'`), the `kind-local` overlay **patches the `host-gpu` `Endpoints`** with it, and ComfyUI/Ollama bind **`0.0.0.0`** on the host. The smoke runs the **fake** path (GPU unused), but the harness still asserts the `host-gpu` Service **resolves** from a pod (hygiene; the real DAG would silently fail otherwise). Documented: this requires native `dockerd` in WSL2.
- **kind-smoke cadence (D6 open item):** **manual + nightly**, never per-commit. The **per-commit** guarantee stays the M4 shared-image offline DAG + the generator diff (both fast, no cluster).
- **Secrets (D5):** created from the **host vault** via a templated `make k8s-secrets`; `secrets.template.yaml` carries no real values; rotation beyond the ADR 0009 #10 pre-flight is **out of scope** (single-operator).
- **Crash-restart (not just concurrency):** `concurrencyPolicy: Forbid` prevents concurrent *starts*; **crash-restart recovery is the M6-wired `run_batch.main` lockfile (stale-PID takeover) + boot reconciler** (`resume_plan`), which run unchanged in-pod. Variant A's Job sets **`backoffLimit: 0`** — the Job never retries the whole conductor (per-stage retries are conductor-internal; the next CronJob tick + the lock/reconciler handle a crashed pod, and the exactly-once ledger guards against any double-post).
- **Variant C is design-only (ADR 0015a adopted scope):** not built; the base is **C-ready by construction** — only the `host-gpu` target + GPU `resources.limits` would change (D7).
- **The `.j2` reference is removed:** the committed generated YAML *is* the human-readable reference. No `jinja2` dependency, no decorative file that could silently drift.

---

## File Structure (ADR 0015a D9)

```
deploy/
  __init__.py                      # (namespace package so `python -m deploy.argo.generator.generate` imports)
  argo/
    __init__.py
    generator/
      __init__.py
      generate.py                  # stage manifests + retry config -> WorkflowTemplate (capability-aware, parameterized)
    generated/
      shorts-workflowtemplate.yaml # COMMITTED output; CI regenerates + diffs (D3)
    cronworkflow.yaml              # Variant B: plan -> withParam fan-out (NO hand-authored video IDs)
  k8s/
    base/
      namespace.yaml
      pvc.yaml                     # PVC `shorts-data`: storageClassName "", accessModes as a patch target
      host-gpu.yaml                # Service `host-gpu` + Endpoints (patched per-overlay) -> host ComfyUI/Ollama/VLM
      secrets.template.yaml        # OAuth/API-key Secret templates (NO real values)
      kustomization.yaml
    conductor/                     # Variant A
      cronjob.yaml                 # daily batch; concurrencyPolicy: Forbid; backoffLimit: 0
      job.yaml                     # one-off manual trigger (mirrors scripts/trigger.sh)
      kustomization.yaml
    overlays/
      kind-local/                  # extraMounts=DATA_ROOT, host-gateway Endpoints patch, accessModes: RWO
      prod/                        # node selectors, real storageClassName, endpoint IPs, image tag, accessModes
shorts/stage.py                    # MODIFY: --batch/--video Argo mode (resolve run-dir/seed/config from batch.json)
shared/host_client.py              # MODIFY: to_relative() at the API boundary (D4)
Makefile                           # cluster-up (+dockerd check) / host-gateway-ip / k8s-secrets / argo-generate / k8s-smoke
.github/workflows/k8s-generator-diff.yml   # per-commit: install + regenerate + diff (fast, no cluster)
.github/workflows/k8s-smoke.yml            # nightly/manual: kind + the golden offline DAG (slow)
tests/
  test_host_client_paths.py        # the D4 path contract (pure)
  test_stage_argo_mode.py          # the --batch/--video resolver (pure)
  test_workflow_generator.py       # the generator: DAG deps, capability env, retry, params, determinism (pure)
  helpers/k8s_smoke.py             # the kind/argo harness helpers (specified, not bare names)
  test_k8s_smoke.py                # integration (kind), runs under `make k8s-smoke`
```

**Responsibility split:** `deploy/k8s/` = Variant A as data; `deploy/argo/generator/` = the *only* author of the Variant-B template; `deploy/argo/generated/` = the committed, CI-diffed output; `shorts/stage.py` (Argo mode) + `shared/host_client.py` = the two small code seams that keep both modes byte-identical on disk. **No stage-logic, conductor, planner, schema, or gate changes** — M7 wraps the tested M0–M6 system.

---

# Part A — The two code seams (path contract + the dual-mode stage CLI)

### Task 1: `host_client.to_relative()` + DATA_ROOT-env resolution (D4)

**Files:** Modify `shared/host_client.py`; Test `tests/test_host_client_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_host_client_paths.py
import pytest
from shared.host_client import to_relative, resolve


def test_comfyui_host_absolute_path_becomes_data_root_relative():
    rel = to_relative("/srv/shorts-data/runs/b1/v1/scenes/01.png", data_root="/srv/shorts-data")
    assert rel == "runs/b1/v1/scenes/01.png" and not rel.startswith("/")


def test_already_relative_is_unchanged():
    assert to_relative("runs/b1/v1/x.png", data_root="/srv/shorts-data") == "runs/b1/v1/x.png"


def test_path_outside_data_root_is_a_hard_error():
    with pytest.raises(ValueError):
        to_relative("/tmp/elsewhere/x.png", data_root="/srv/shorts-data")


def test_resolve_uses_THIS_process_data_root(monkeypatch):
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
    """ADR 0015a D4: convert ComfyUI's host-ABSOLUTE output path to DATA_ROOT-relative AT THE API
    BOUNDARY — the only place an absolute path is allowed. Outside DATA_ROOT -> fail loud (a pod
    could never resolve it)."""
    p = Path(path)
    if not p.is_absolute():
        return path
    try:
        return str(p.relative_to(data_root))
    except ValueError:
        raise ValueError(f"{path!r} is outside DATA_ROOT {data_root!r} — cannot store cross-mode")


def resolve(rel_path: str, *, data_root: str | None = None) -> Path:
    """Resolve a DATA_ROOT-relative path against THIS process's DATA_ROOT (/data in a pod, the WSL2
    dir on the host) — every process maps the same relative path to its own mount (D4)."""
    return Path(data_root or os.environ["DATA_ROOT"]) / rel_path
```

- [ ] **Step 3: Wire** — the host GPU client routes every ComfyUI-returned path through `to_relative(..., data_root=os.environ["DATA_ROOT"])` before it lands in any stage output; stages read inputs via `resolve(...)`. (The M0 `ctx` already maps declared names to run-dir-relative paths; this closes the ComfyUI boundary leak.)
- [ ] **Step 4: Run** → PASS (4). **Commit.**

```bash
git add shared/host_client.py tests/test_host_client_paths.py
git commit -m "feat(m7): the DATA_ROOT-relative path contract — byte-compatible runner/cluster disk (ADR 0015a D4)"
```

### Task 2: The dual-mode per-stage CLI (`--batch/--video` resolves from `batch.json`)

The M4 stage CLI takes `--run-dir/--seed/--config`. Argo wants to address a stage by `(batch, video)`. One CLI must serve both so Variant A and B run identical code.

**Files:** Modify `shorts/stage.py`; Test `tests/test_stage_argo_mode.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_stage_argo_mode.py
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
```

- [ ] **Step 2: Implement `resolve_argo_args` in `shorts/stage.py`** and branch `main()` on the mode

```python
def resolve_argo_args(*, data_root, batch_id: str, video_id: str) -> dict:
    """Argo mode (ADR 0015a B): address a stage by (batch, video); resolve the explicit run-dir,
    per-video seed, and config from the planner's batch.json on the PVC — so `--batch/--video`
    and the M4 `--run-dir/--seed/--config` mode run the IDENTICAL stage body."""
    import json
    from pathlib import Path
    batch = json.loads((Path(data_root) / "runs" / batch_id / "batch.json").read_text())
    video = next((v for v in batch["videos"] if v["video_id"] == video_id), None)
    if video is None:
        raise KeyError(f"video {video_id!r} not in batch {batch_id!r}")
    run_dir = str(Path(data_root) / "runs" / batch_id / video_id)
    return {"run_dir": run_dir, "seed": video["seed"],
            "config": {"niche": video["niche"], "format": video.get("format")}}
```

`main()` gains `--batch`/`--video`; when present, it calls `resolve_argo_args(data_root=os.environ["DATA_ROOT"], ...)` and proceeds exactly as the explicit mode (same `StageContext`, same `reg.fn(ctx)`, same exit codes). The two modes are a thin arg-parsing fork over one body.
- [ ] **Step 3: Run** → PASS (2). **Commit.**

```bash
git add shorts/stage.py tests/test_stage_argo_mode.py
git commit -m "feat(m7): dual-mode stage CLI — --batch/--video resolves from batch.json (one body, ADR 0015a B)"
```

---

# Part B — Variant A: conductor-in-cluster

### Task 3: The `deploy/k8s/base` — namespace, PVC (patchable), host-GPU Service, Secrets

**Files:** Create `deploy/k8s/base/{namespace,pvc,host-gpu,secrets.template,kustomization}.yaml`

- [ ] **Step 1: `namespace.yaml`** → the `shorts` namespace.
- [ ] **Step 2: `pvc.yaml`** → PVC `shorts-data`, **`storageClassName: ""`** (manual bind to the local PV), mounted at **`/data`** in every pod. **`accessModes` is left as a kustomize patch target** (a documented marker) — the overlays set it (RWO kind-local / RWX prod). A comment records: single-node ⇒ RWO; multi-node ⇒ the RWX swap (D8), now a one-line overlay patch.
- [ ] **Step 3: `host-gpu.yaml`** → a headless `Service` `host-gpu` + an `Endpoints` object **with placeholder addresses patched per-overlay** (Task 6). Pods get **per-capability** envs (`HOST_GPU_ENDPOINT=http://host-gpu.shorts.svc:8188`, `HOST_OLLAMA_ENDPOINT=...:11434`, `HOST_VLM_ENDPOINT=...`) — the same envs the stages resolve (ADR 0001). The GPU plane never enters the cluster in this profile.
- [ ] **Step 4: `secrets.template.yaml`** → `Secret` templates (YouTube/TikTok OAuth + API keys) projected to the **same env names** the host vault uses (D5). **No real values.**
- [ ] **Step 5: `kustomization.yaml`** + add `deploy/__init__.py`, `deploy/argo/__init__.py`, `deploy/argo/generator/__init__.py` (so the generator is importable as a module). **Validate** (integration): `kubectl --dry-run=client -k deploy/k8s/base`. **Commit.**

```bash
git add deploy/k8s/base/ deploy/__init__.py deploy/argo/__init__.py
git commit -m "feat(m7): deploy/k8s base — PVC (patchable accessModes), per-capability host-gpu, Secrets (ADR 0015a D2/D5)"
```

### Task 4: Variant A — the conductor `CronJob` + one-off `Job`

**Files:** Create `deploy/k8s/conductor/{cronjob,job,kustomization}.yaml`

- [ ] **Step 1: `cronjob.yaml`** → the M4 **shared image** (`shorts-creator:ci`, the prod overlay patches the tag), `command: ["python","-m","shorts.run_batch"]`, `DATA_ROOT=/data`, the PVC at `/data`, the per-capability `host-gpu` envs + Secrets, the nightly `schedule`, **`concurrencyPolicy: Forbid`**, **`restartPolicy: Never`**, **`backoffLimit: 0`** (the Job never retries the whole conductor — per-stage retries are conductor-internal; crash-restart is the M6-wired lockfile + reconciler on the next tick; the exactly-once ledger guards re-posts), `activeDeadlineSeconds` = the M4 10h batch watchdog.
- [ ] **Step 2: `job.yaml`** → the one-off manual trigger (`kubectl create job --from=cronjob/shorts-batch`), supporting `--dry-run` via an `args` override.
- [ ] **Step 3: `kustomization.yaml`** → base + conductor. **Validate** (integration): `kubectl --dry-run=client -k deploy/k8s/conductor`. **Commit.**

```bash
git add deploy/k8s/conductor/
git commit -m "feat(m7): Variant A — conductor CronJob + Job (Forbid + lockfile/reconciler, backoffLimit 0, ADR 0015a D1)"
```

### Task 5: The `kind-local` + `prod` overlays + `make cluster-up`/`host-gateway-ip`/`k8s-secrets`

**Files:** Create `deploy/k8s/overlays/kind-local/`, `deploy/k8s/overlays/prod/`; Modify `Makefile`

- [ ] **Step 1: `overlays/kind-local/`** — the kind config with **`extraMounts`** mapping the host `DATA_ROOT` (the WSL2 ext4 dir) into the node at the local-PV hostPath; an **`Endpoints` patch** setting the `host-gpu` addresses to the **Docker bridge gateway IP** (from `make host-gateway-ip`); an **`accessModes: [ReadWriteOnce]`** patch on the PVC. This makes the local cluster read/write the *same* `DATA_ROOT` as runner-mode and reach the host's ComfyUI.
- [ ] **Step 2: `overlays/prod/`** — real node selectors, a real **`storageClassName`** patch (replacing `""`), an **`accessModes: [ReadWriteMany]`** patch (the multi-node RWX swap, D8), the endpoint IPs, and a kustomize **`images:`** patch pinning the image tag/digest. (C-ready: only the `host-gpu` target + GPU resource requests would change for Variant C, D7.)
- [ ] **Step 3: `make host-gateway-ip`** → `ip route | awk '/default/{print $3}'` (the Docker bridge gateway the kind node uses to reach the WSL2 host); used to render the kind-local Endpoints patch. **`make cluster-up`** → first a **prerequisite check** (`docker context show` ⇒ native `dockerd`, not the Docker-Desktop backend; fail loud with the fix if wrong), then `kind create cluster` (idempotent) + `kubectl apply -k overlays/kind-local`, with ComfyUI/Ollama bound `0.0.0.0` on the host. **`make k8s-secrets`** → `kubectl create secret ... --from-env-file=$VAULT` (D5). **`make cluster-down`** → `kind delete cluster`.
- [ ] **Step 4: Validate** (integration): `kustomize build deploy/k8s/overlays/kind-local | kubectl --dry-run=client apply -f -`. **Commit.**

```bash
git add deploy/k8s/overlays/ Makefile
git commit -m "feat(m7): kind-local + prod overlays (host-gateway Endpoints, RWO/RWX, storageClass, image) + cluster-up (ADR 0015a D2/D8)"
```

---

# Part C — The template generator (ADR 0015a D3)

### Task 6: `generate.py` — manifests → `WorkflowTemplate` (capability-aware, parameterized)

**Files:** Create `deploy/argo/generator/generate.py`; Test `tests/test_workflow_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workflow_generator.py
import yaml
from deploy.argo.generator.generate import build_workflow, retry_strategy, capability_env


def _manifests():
    return [{"id": "00a", "inputs": [], "outputs": ["job"], "compute": "cpu"},
            {"id": "00b", "inputs": ["job"], "outputs": ["script"], "compute": "cpu", "capability": "llm"},
            {"id": "05", "inputs": ["script"], "outputs": ["render"], "compute": "gpu", "capability": "generate_image"},
            {"id": "05x", "inputs": ["render"], "outputs": ["vision"], "compute": "gpu", "capability": "vlm_judge"}]


def test_dag_dependencies_come_from_inputs_outputs():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    dag = next(t for t in wf["spec"]["templates"] if "dag" in t)        # not index-fragile
    tasks = {t["name"]: t for t in dag["dag"]["tasks"]}
    assert tasks["00b"]["dependencies"] == ["00a"] and tasks["05"]["dependencies"] == ["00b"]
    assert tasks["00a"].get("dependencies", []) == []


def test_capability_drives_the_host_endpoint_env():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    envof = lambda sid: {e["name"]: e["value"] for e in
                         next(t for t in wf["spec"]["templates"] if t["name"] == sid)["container"]["env"]}
    assert "HOST_GPU_ENDPOINT" in envof("05")           # generate_image -> ComfyUI :8188
    assert "HOST_OLLAMA_ENDPOINT" in envof("00b")        # llm -> Ollama :11434, NOT the GPU port
    assert "HOST_VLM_ENDPOINT" in envof("05x")           # vlm_judge -> the VLM endpoint
    assert "nvidia.com/gpu" not in str(next(t for t in wf["spec"]["templates"]
                                            if t["name"] == "05")["container"].get("resources", {}))


def test_step_body_is_the_batch_video_one_liner():
    wf = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30})
    s05 = next(t for t in wf["spec"]["templates"] if t["name"] == "05")
    cmd = s05["container"]["command"] + s05["container"]["args"]
    assert cmd[:3] == ["python", "-m", "shorts.stage"]
    assert "--batch" in cmd and "--video" in cmd          # the dual-mode CLI (Task 2), NOT --run-dir


def test_workflow_declares_its_parameters_and_retry():
    wf = build_workflow(_manifests(), retry={"retries": 3, "backoff_s": 20})
    params = {p["name"] for p in wf["spec"]["arguments"]["parameters"]}
    assert params == {"batch_id", "video_id"}             # else Argo rejects {{workflow.parameters...}}
    assert retry_strategy({"retries": 3, "backoff_s": 20}) == \
        {"limit": 3, "backoff": {"duration": "20s", "factor": 2}}


def test_image_and_mount_are_parameters_and_output_is_deterministic():
    a = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30}, image="shorts-creator:ci", mount="/data")
    assert all(t["container"]["image"] == "shorts-creator:ci"
               for t in a["spec"]["templates"] if t.get("container"))
    b = build_workflow(_manifests(), retry={"retries": 2, "backoff_s": 30}, image="shorts-creator:ci", mount="/data")
    assert yaml.safe_dump(a, sort_keys=True) == yaml.safe_dump(b, sort_keys=True)


def test_duplicate_output_name_is_a_hard_error():
    import pytest
    dupe = [{"id": "a", "inputs": [], "outputs": ["x"]}, {"id": "b", "inputs": [], "outputs": ["x"]}]
    with pytest.raises(ValueError):
        build_workflow(dupe, retry={"retries": 2, "backoff_s": 30})
```

- [ ] **Step 2: Implement `deploy/argo/generator/generate.py`**

```python
"""manifest -> Argo WorkflowTemplate (ADR 0015a D3). The ONLY author of the Variant-B template;
CI regenerates + diffs the committed output. Retry is read from the SAME source the M4 conductor
uses (shared/conductor/retry.RetryPolicy) — one policy source. Run:
  python -m deploy.argo.generator.generate > deploy/argo/generated/shorts-workflowtemplate.yaml"""
import json
import sys
from pathlib import Path

_DEFAULT_IMAGE = "shorts-creator:ci"        # the M4 ci image (prod overlay patches via kustomize images:)
_DEFAULT_MOUNT = "/data"

# capability -> the host endpoint env it needs (ADR 0001 host-owned GPU; the live D3 seam)
CAPABILITY_ENV = {
    "generate_image": ("HOST_GPU_ENDPOINT", "http://host-gpu.shorts.svc:8188"),
    "img2vid":        ("HOST_GPU_ENDPOINT", "http://host-gpu.shorts.svc:8188"),
    "restore":        ("HOST_GPU_ENDPOINT", "http://host-gpu.shorts.svc:8188"),
    "llm":            ("HOST_OLLAMA_ENDPOINT", "http://host-gpu.shorts.svc:11434"),
    "tts":            ("HOST_OLLAMA_ENDPOINT", "http://host-gpu.shorts.svc:11434"),
    "vlm_judge":      ("HOST_VLM_ENDPOINT", "http://host-gpu.shorts.svc:11434"),
}


def retry_strategy(retry: dict) -> dict:
    return {"limit": retry["retries"], "backoff": {"duration": f"{retry['backoff_s']}s", "factor": 2}}


def capability_env(capability: str | None) -> list[dict]:
    if capability and capability in CAPABILITY_ENV:
        name, val = CAPABILITY_ENV[capability]
        return [{"name": name, "value": val}]
    return []


def _producer_of(manifests: list[dict]) -> dict[str, str]:
    producer: dict[str, str] = {}
    for m in manifests:
        for out in m.get("outputs", []):
            if out in producer:
                raise ValueError(f"output {out!r} produced by both {producer[out]!r} and {m['id']!r}")
            producer[out] = m["id"]
    return producer


def build_workflow(manifests: list[dict], *, retry: dict, image: str = _DEFAULT_IMAGE,
                   mount: str = _DEFAULT_MOUNT) -> dict:
    producer = _producer_of(manifests)
    dag_tasks, templates = [], []
    for m in manifests:
        deps = sorted({producer[i] for i in m.get("inputs", []) if i in producer})
        dag_tasks.append({"name": m["id"], "template": m["id"],
                          **({"dependencies": deps} if deps else {})})
        env = [{"name": "DATA_ROOT", "value": mount}, *capability_env(m.get("capability"))]
        templates.append({
            "name": m["id"], "retryStrategy": retry_strategy(retry),
            "container": {"image": image, "command": ["python", "-m", "shorts.stage"],
                          "args": [m["id"], "--batch", "{{workflow.parameters.batch_id}}",
                                   "--video", "{{workflow.parameters.video_id}}"],
                          "env": env, "volumeMounts": [{"name": "data", "mountPath": mount}]}})
        # compute=='gpu' reaches the HOST GPU over HTTP (ADR 0001) — NO nvidia.com/gpu (that is Variant C).
    dag = {"name": "shorts-dag", "dag": {"tasks": dag_tasks}}
    return {"apiVersion": "argoproj.io/v1alpha1", "kind": "WorkflowTemplate",
            "metadata": {"name": "shorts-batch", "namespace": "shorts"},
            "spec": {"entrypoint": "shorts-dag",
                     "arguments": {"parameters": [{"name": "batch_id"}, {"name": "video_id"}]},
                     "templates": [dag, *templates],
                     "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "shorts-data"}}]}}


def main() -> int:
    import yaml
    from shared.conductor.retry import RetryPolicy
    root = Path(__file__).resolve().parents[3]        # deploy/argo/generator -> repo root
    manifests = [json.loads(p.read_text()) for p in sorted(root.glob("stages/*/manifest.json"))]
    rp = RetryPolicy()                                # the SINGLE retry source (the conductor's defaults)
    sys.stdout.write(yaml.safe_dump(
        build_workflow(manifests, retry={"retries": rp.retries, "backoff_s": rp.backoff_s}),
        sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run** → PASS (6). **Commit.**

```bash
git add deploy/argo/generator/generate.py tests/test_workflow_generator.py
git commit -m "feat(m7): WorkflowTemplate generator — capability-aware env, params, retry from RetryPolicy (ADR 0015a D3)"
```

### Task 7: The committed template + the regenerate-and-diff CI

**Files:** Create `deploy/argo/generated/shorts-workflowtemplate.yaml`, `.github/workflows/k8s-generator-diff.yml`; Modify `Makefile`

- [ ] **Step 1: Generate + commit** → `python -m deploy.argo.generator.generate > deploy/argo/generated/shorts-workflowtemplate.yaml`. **(Note: until M0 lands `stages/*/manifest.json`, the glob is empty and this is a vacuously-valid empty-DAG template — the diff check is green-but-empty until stages exist; that is expected and harmless.)**
- [ ] **Step 2: `.github/workflows/k8s-generator-diff.yml`** (per-commit, fast, no cluster):

```yaml
name: k8s-generator-diff
on: [push, pull_request]
jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e . && pip install pyyaml      # the project must be importable
      - name: Regenerate and diff (the D3 drift-catcher)
        run: |
          python -m deploy.argo.generator.generate > /tmp/regenerated.yaml
          diff -u deploy/argo/generated/shorts-workflowtemplate.yaml /tmp/regenerated.yaml \
            || { echo "::error::generated WorkflowTemplate is stale — run 'make argo-generate'"; exit 1; }
```

- [ ] **Step 3: Wire `make argo-generate`** → the generate command (the only sanctioned way to update the committed YAML). **Commit.**

```bash
git add deploy/argo/generated/ .github/workflows/k8s-generator-diff.yml Makefile
git commit -m "feat(m7): committed WorkflowTemplate + regenerate-and-diff CI (install + diff, the D3 drift-catcher)"
```

---

# Part D — Variant B: Argo fan-out (planner-sourced video list)

### Task 8: The Argo `CronWorkflow` (plan → `withParam` fan-out)

**Files:** Create `deploy/argo/cronworkflow.yaml`

- [ ] **Step 1: `cronworkflow.yaml`** — `concurrencyPolicy: Forbid` (mirrors A, D1), the nightly `schedule`, and a **two-step entry DAG**: (1) **`plan`** — a step running `python -m shorts.run_batch --plan-only` (writes `runs/<batch>/batch.json` to the PVC, emits the planned `video_id`s as an Argo **output parameter**, e.g. a JSON list via `outputs.parameters`); (2) **`fanout`** — `withParam: "{{tasks.plan.outputs.parameters.video_ids}}"` instantiating the generated **`shorts-batch` `WorkflowTemplate`** (`templateRef`) once per `video_id`, passing `batch_id` + `video_id`. **No video IDs are hand-authored** — they come from the planner (single source). Note the **single-node caveat (D8)**: multi-node fan-out needs the PVC RWX (the prod-overlay one-liner).
- [ ] **Step 2: Validate** (integration — requires the `argo` CLI; runs under `make cluster-up`, not per-commit): `argo lint deploy/argo/cronworkflow.yaml` + `argo lint deploy/argo/generated/shorts-workflowtemplate.yaml`. **Commit.**

```bash
git add deploy/argo/cronworkflow.yaml
git commit -m "feat(m7): Variant B — Argo CronWorkflow plan->withParam fan-out (planner-sourced IDs, ADR 0015a D1/D8)"
```

---

# Part E — The smoke test (ADR 0015a D6) — the M7 gate

### Task 9: `make k8s-smoke` — the golden offline DAG on kind, through A *and* B

**Files:** Create `tests/helpers/k8s_smoke.py`, `tests/test_k8s_smoke.py`, `.github/workflows/k8s-smoke.yml`; Modify `Makefile`

- [ ] **Step 1: Specify the harness `tests/helpers/k8s_smoke.py`** (signatures + behavior — not bare names)

```python
# tests/helpers/k8s_smoke.py — thin kubectl/argo wrappers for the smoke gate (integration only)
from pathlib import Path
import subprocess, time


def kind_cluster() -> None:
    """Ensure the kind cluster exists (idempotent) and the ci image is loaded. Calls `make cluster-up`."""
    subprocess.run(["make", "cluster-up"], check=True)
    subprocess.run(["kind", "load", "docker-image", "shorts-creator:ci"], check=True)


def argo_installed(namespace: str = "shorts") -> None:
    """Install Argo (quick-start) into the namespace and WAIT for the controller to be Ready."""
    subprocess.run(["kubectl", "apply", "-n", namespace, "-f",
                    "https://github.com/argoproj/argo-workflows/releases/latest/download/quick-start-minimal.yaml"],
                   check=True)
    subprocess.run(["kubectl", "rollout", "status", "-n", namespace, "deploy/workflow-controller",
                    "--timeout=180s"], check=True)


def data_root_pvc() -> Path:
    """The host dir kind extraMounts into the PV (the WSL2 DATA_ROOT) — where posts land. Returns a Path."""
    return Path(subprocess.check_output(["make", "-s", "print-data-root"]).decode().strip())


def run_one_off_job(*, image: str, args: list[str], timeout_s: int = 600) -> None:
    """Variant A: create a Job from the conductor CronJob with overridden args; wait for Complete; raise on fail."""
    ...


def submit_cronworkflow_now(path: str, *, timeout_s: int = 900) -> None:
    """Variant B: `argo submit --from cronwf/... ` (or trigger the cron now); used with wait_succeeded."""
    ...


def wait_succeeded(*, workflow: str, timeout_s: int) -> bool:
    """Poll `argo get <workflow>`; return True on Succeeded, raise on Failed, False on timeout."""
    ...


def no_pod_errors(*, namespace: str) -> bool:
    """True iff no pod in the namespace is in Error/CrashLoopBackOff/ImagePullBackOff."""
    ...
```

- [ ] **Step 2: Write `tests/test_k8s_smoke.py`** (the glob is fixed; `list()`-wrapped so an empty result fails)

```python
import pytest
from tests.helpers.k8s_smoke import (kind_cluster, argo_installed, data_root_pvc,
                                     run_one_off_job, submit_cronworkflow_now, wait_succeeded, no_pod_errors)


@pytest.mark.integration
def test_variant_a_runs_the_golden_dag_as_a_job():
    kind_cluster()
    run_one_off_job(image="shorts-creator:ci", args=["--profiles", "finance", "--backends", "fake"])
    assert list((data_root_pvc() / "runs").glob("*/*/posts.json"))     # a posts artifact landed
    assert no_pod_errors(namespace="shorts")


@pytest.mark.integration
def test_variant_b_runs_the_golden_dag_through_argo():
    kind_cluster(); argo_installed()
    submit_cronworkflow_now("deploy/argo/cronworkflow.yaml")
    assert wait_succeeded(workflow="shorts-batch", timeout_s=900)
    assert list((data_root_pvc() / "runs").glob("*/*/posts.json"))
    assert no_pod_errors(namespace="shorts")
```

- [ ] **Step 3: Write `.github/workflows/k8s-smoke.yml`** (nightly + `workflow_dispatch`): set up kind + the `argo` CLI, `docker build --target ci -t shorts-creator:ci`, then `make k8s-smoke`. **Not** per-commit (D6). Add `make print-data-root` (echoes the kind-mounted host dir).
- [ ] **Step 4: Wire `make k8s-smoke`** → `cluster-up` → `kind load` → `pytest tests/test_k8s_smoke.py -m integration`. **Run locally** → PASS (2). **Commit.**

```bash
git add tests/helpers/k8s_smoke.py tests/test_k8s_smoke.py .github/workflows/k8s-smoke.yml Makefile
git commit -m "feat(m7): make k8s-smoke — golden offline DAG on kind through Variant A and B (the M7 gate, ADR 0015a D6)"
```

---

## M7 Acceptance Checklist (the testable "done")

- [ ] **Both code seams hold:** `to_relative`/`resolve` give the `DATA_ROOT`-relative path contract (D4); the **dual-mode stage CLI** resolves `--batch/--video` from `batch.json` so Variant A and B run the identical body → Tasks 1–2.
- [ ] **Variant A is data, not code:** the unchanged conductor runs as a `CronJob` (+ one-off `Job`), `Forbid` + the lockfile/reconciler handling crash-restart, `backoffLimit: 0`, PVC=`DATA_ROOT`, per-capability host-GPU envs, Secrets from the host vault → Tasks 3–5.
- [ ] **The generator is the only template author (D3) and is fully data-driven:** DAG deps from manifests, **`capability` → the correct host endpoint env** (no LLM-on-the-GPU-port bug), the step body is the `--batch/--video` one-liner, `spec.arguments.parameters` declares `batch_id`+`video_id`, retry comes from the **`RetryPolicy`** source, image/mount are parameters, duplicate outputs hard-fail, output is deterministic; **CI installs the project + regenerates + diffs** → Tasks 6–7.
- [ ] **Variant B fans out from the planner:** the CronWorkflow plans then `withParam`-instantiates the template per planned `video_id` — **no hand-authored IDs**, `Forbid` mirroring A → Task 8.
- [ ] **Host-GPU reachability is real:** `make host-gateway-ip` + the kind-local Endpoints patch + ComfyUI on `0.0.0.0`; the smoke verifies the Service resolves from a pod; native `dockerd` is a checked prerequisite → Task 5.
- [ ] **The M7 gate:** `make k8s-smoke` runs the **golden offline DAG with fakes on kind**, green through **Variant A *and* B**, with a `posts` artifact on the PVC (the glob is `*/*/posts.json`, `list()`-wrapped); per-commit stays the M4 image + the generator diff → Task 9.
- [ ] **Variant C stays design-only** (no GPU-in-cluster artifacts); the base is C-ready; the prod overlay makes storage-class/RWX/image one-line patches → the decisions header + Tasks 3/5.

---

## Self-Review

**ADR 0015a coverage:** Variant A → B (Tasks 3–5, D1/D2/D5); the path contract + the dual-mode CLI (the two seams that keep A/B byte-identical) → A (Tasks 1–2, D4 + B); the generator + regenerate-diff CI → C (Tasks 6–7, D3); Variant B planner-sourced fan-out → D (Task 8, D1/D8); `make k8s-smoke` through A *and* B → E (Task 9, D6 — the gate). Variant C → design-only (decisions header + D7). The three open items are pinned: retry = the `RetryPolicy` source (Task 6), kind-smoke = nightly/manual (Task 9), secrets = host-vault-templated (Tasks 3/5).

**Review fixes folded in (from the M7 multi-lens review):** the dual-mode stage CLI (the generator emitted `--video` against M4's `--run-dir/--seed/--config` — now one CLI, two modes, Task 2); the host-gateway/Endpoints mechanism made explicit (`make host-gateway-ip` + the patch + the dockerd prerequisite + the pod-resolves-Service check, Task 5); **`capability` → per-stage host endpoint** (the dead D3 seam, now `CAPABILITY_ENV`, Task 6); image is a parameter defaulting to **`shorts-creator:ci`** (was `:latest` → `ImagePullBackOff`) with the prod overlay patching the tag; retry from **`RetryPolicy`** (no phantom `config/defaults.json`); `spec.arguments.parameters` for `batch_id`+`video_id` (Argo would reject the workflow without it); **planner-sourced** `video_id`s (no hand-authored CronWorkflow IDs); the PVC `accessModes`/`storageClassName` as overlay patch targets (the D8 RWX swap is a one-liner); `DATA_ROOT`/mount as a generator parameter; the `_producer_of` **duplicate-output guard**; the **glob fixed** to `*/*/posts.json` + `list()`-wrapped (the smart-quote/`str*str`/truthy-generator triple bug); the **smoke harness fully specified** (signatures + behavior + the Argo readiness gate); the CI workflow **installs the project**; `deploy/__init__.py`/`deploy/argo/__init__.py` added; the **`.j2` removed** (the generated YAML is the reference); `backoffLimit: 0` + the lockfile/reconciler crash-restart note; the `argo` CLI in the tech stack; index-fragile tests use `next(...)`; the "vacuous until M0 stages exist" diff caveat recorded.

**Placeholder scan:** the smoke harness's `run_one_off_job`/`submit_cronworkflow_now`/`wait_succeeded`/`no_pod_errors` bodies are the only `...` left — they are thin, **specified** (signature + docstring contract) kubectl/argo wrappers that run under `make k8s-smoke` (integration); the pure logic — `to_relative`/`resolve`, `resolve_argo_args`, the full `build_workflow`/`retry_strategy`/`capability_env`/`_producer_of` — is implemented + unit-tested with no GPU/cluster.

**Type/contract consistency vs M0–M6:** reuses the M0 stage **manifests** (`id`/`inputs`/`outputs`/`compute`/`capability`) as the generator's sole input; the M4 **shared image** + the **`python -m shorts.stage`/`shorts.run_batch`** entrypoints (the Argo mode is an additive arg fork over the M4 body); the M4 **`RetryPolicy`** as the single retry source; the M5/M6 `batch.json` (the `--batch/--video` resolver reads the planner's per-video seed/niche); `HOST_*_ENDPOINT` envs the stages already resolve (ADR 0001/0015); the `DATA_ROOT`-relative contract matches the M0 `ctx` mapping + the M6 host_client. **No stage, conductor, planner, schema, or gate logic changes.**

**Scope:** five parts, one gate (the golden DAG green through A and B on kind). Optional and post-PoC — the Chapter 1 DoD is M6's. A (seams) and C (generator) are pure + independent; B (Variant A) and D (Variant B) are the manifests; E depends on all. With it, "runner-first PoC → A → B" is a built, tested ladder and C is one Linux-GPU-node away — the operator's "Kubernetes when I want it," delivered without ever forking what runs.
