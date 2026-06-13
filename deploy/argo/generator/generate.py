"""manifest -> Argo WorkflowTemplate (ADR 0015a D3). The ONLY author of the Variant-B template;
CI regenerates + diffs the committed output. Retry is read from the SAME source the M4 conductor
uses (shared/conductor/retry.RetryPolicy) — one policy source. Run:
  python -m deploy.argo.generator.generate > deploy/argo/generated/shorts-workflowtemplate.yaml"""
import json
import sys
from pathlib import Path

_DEFAULT_IMAGE = "shorts-creator:ci"  # the M4 ci image (prod overlay patches via kustomize images:)
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
    return {
        "limit": retry["retries"],
        "backoff": {"duration": f"{retry['backoff_s']}s", "factor": 2},
    }


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
                raise ValueError(
                    f"output {out!r} produced by both {producer[out]!r} and {m['id']!r}"
                )
            producer[out] = m["id"]
    return producer


def build_workflow(
    manifests: list[dict],
    *,
    retry: dict,
    image: str = _DEFAULT_IMAGE,
    mount: str = _DEFAULT_MOUNT,
) -> dict:
    producer = _producer_of(manifests)
    dag_tasks, templates = [], []
    for m in manifests:
        deps = sorted({producer[i] for i in m.get("inputs", []) if i in producer})
        dag_tasks.append(
            {
                "name": m["id"],
                "template": m["id"],
                **({"dependencies": deps} if deps else {}),
            }
        )
        env = [{"name": "DATA_ROOT", "value": mount}, *capability_env(m.get("capability"))]
        templates.append(
            {
                "name": m["id"],
                "retryStrategy": retry_strategy(retry),
                "container": {
                    "image": image,
                    "command": ["python", "-m", "shorts.stage"],
                    "args": [
                        m["id"],
                        "--batch",
                        "{{workflow.parameters.batch_id}}",
                        "--video",
                        "{{workflow.parameters.video_id}}",
                    ],
                    "env": env,
                    "volumeMounts": [{"name": "data", "mountPath": mount}],
                },
            }
        )
    dag = {"name": "shorts-dag", "dag": {"tasks": dag_tasks}}
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "WorkflowTemplate",
        "metadata": {"name": "shorts-batch", "namespace": "shorts"},
        "spec": {
            "entrypoint": "shorts-dag",
            "arguments": {
                "parameters": [{"name": "batch_id"}, {"name": "video_id"}]
            },
            "templates": [dag, *templates],
            "volumes": [
                {"name": "data", "persistentVolumeClaim": {"claimName": "shorts-data"}}
            ],
        },
    }


def main() -> int:
    import yaml

    from shared.conductor.retry import RetryPolicy

    root = Path(__file__).resolve().parents[3]  # deploy/argo/generator -> repo root
    manifests = [
        json.loads(p.read_text()) for p in sorted(root.glob("stages/*/manifest.json"))
    ]
    rp = RetryPolicy()  # the SINGLE retry source (the conductor's defaults)
    sys.stdout.write(
        yaml.safe_dump(
            build_workflow(manifests, retry={"retries": rp.retries, "backoff_s": rp.backoff_s}),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
