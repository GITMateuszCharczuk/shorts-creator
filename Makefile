# shorts-creator — convenience entrypoints.
#
# One-command lifecycle:
#   make up        # turn the whole system on (host GPU + Ollama + conductor — ADR 0015) -> scripts/up.sh
#   make trigger   # run a batch now (manual)                                   -> scripts/trigger.sh
#   make down      # stop the system (host-backed data persists)               -> scripts/down.sh
#
# The granular targets below are the single source of truth the scripts call;
# M0 fills in the bodies marked `# M0:`.
#
# NOTE: until M0 wires them, the host-*/cluster-up/build/wire/test bodies are
# stubs that `exit 1`, so `make up` (and scripts/up.sh) will fail fast at the
# first unwired step. That is expected pre-implementation.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

KIND_CLUSTER ?= shorts
PROFILES     ?= finance,business
COUNT        ?= 2

.PHONY: help up down trigger dry-run \
        host-comfyui-up host-comfyui-down host-llm-up \
        host-up build wire submit-batch test soak voice-ab review calibrate audit \
        obs-up obs-lint \
        host-gateway-ip cluster-up cluster-down k8s-secrets print-data-root \
        argo-generate k8s-smoke

help: ## list targets (grouped by section)
	@awk 'BEGIN{FS=":.*?## "} \
	     /^## /{h=$$0; sub(/^## ?/,"",h); printf "\n\033[1m%s\033[0m\n",h} \
	     /^[a-zA-Z0-9_-]+:.*?## /{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

## ---- one-command lifecycle (wrappers over scripts/) ----
up: ## turn the whole system on with one command
	@scripts/up.sh
down: ## stop the host services (data persists)
	@scripts/down.sh
trigger: ## manually trigger a batch now (ARGS forwarded to trigger.sh)
	@scripts/trigger.sh $(ARGS)
dry-run: ## manually trigger a batch that posts nothing
	@scripts/trigger.sh --dry-run --profiles $(PROFILES) --count $(COUNT)

## ---- host GPU plane (M0 wires these) ----
host-comfyui-up:   ## start ComfyUI + ensure FLUX/LTX/ESRGAN/RIFE/GFPGAN graphs+models
	@echo "M0: start ComfyUI server (see host/comfyui/setup.md)"; exit 1
host-comfyui-down: ## stop ComfyUI
	@echo "M0: stop ComfyUI"; true
host-llm-up:       ## start the LLM endpoint (Ollama) if not already serving
	@echo "M0: start Ollama / llama.cpp (see host/llm/)"; exit 1
host-up: host-comfyui-up host-llm-up ## start the full host GPU+LLM plane

## ---- control plane (runner-first — ADR 0015; the k8s profile lives in its own section below) ----
build:      ## build the single shared image (the CI-proven deployable artifact, ADR 0015)
	@docker build --target ci -t shorts-creator:ci .
wire:       ## verify the conductor reaches host ComfyUI/LLM over localhost (ADR 0015)
	@curl -fsS http://127.0.0.1:8188/system_stats >/dev/null && echo "ComfyUI reachable (:8188/system_stats)"
	@curl -fsS http://127.0.0.1:11434/api/version >/dev/null && echo "Ollama reachable (:11434/api/version)"

## ---- runs ----
submit-batch: ## scheduled-equivalent batch submit (CronWorkflow uses the same template)
	@scripts/trigger.sh --profiles $(PROFILES) --count $(COUNT)

## ---- dev ----
test: ## schema validation + golden fixtures + GPU-free full-DAG run via shared/fakes (ADR 0010)
	@uv run pytest -q -m "not integration and not soak"
soak: ## offline stability soak over the REAL batch_flow (make soak N=14)
	@SOAK_BATCHES=$${N:-14} uv run pytest tests/test_soak_offline.py -m soak -q
voice-ab: ## expressive-voice A/B: reference script through each TTS backend (host-only, ADR 0017 D1)
	@uv run python -m shared.audio.voice_ab
review: ## human-at-publish ramp review CLI (ADR 0014 D2 / 0016 D2)
	@uv run python -m shorts.review
calibrate: ## per-niche 05c floor recommendation from ramp labels (ADR 0016 D2)
	@uv run python -m shorts.calibrate --data-root $${DATA_ROOT:-data}
audit: ## weekly spot-audit report vs the live floor (DoD clause 2)
	@uv run python -m shorts.audit --data-root $${DATA_ROOT:-data}

## ---- observability (M6) ----
obs-up: ## start node-exporter + nvidia-smi + queue pollers + Prometheus + Alertmanager + Grafana (host only)
	@echo "M6: start the obs stack on the host (node-exporter :9100, pollers, Prometheus :9090, Alertmanager :9093, Grafana :3000)"; \
	 echo "    see deploy/obs/nvidia-smi-exporter.md and deploy/obs/comfyui-queue-exporter.md"; exit 1
obs-lint: ## validate prometheus.yml, alerts.yml, alertmanager.yml and grafana JSON (CI gate)
	@uv run python -c "import json,sys; json.load(open('deploy/obs/grafana-dashboard.json'))" \
	    && echo "obs-lint: grafana JSON OK"
	@promtool check config deploy/obs/prometheus.yml
	@promtool check rules deploy/obs/alerts.yml
	@amtool check-config deploy/obs/alertmanager.yml

## ---- kubernetes profile (M7, ADR 0015a; OPTIONAL post-PoC) ----
# Variant A: the UNCHANGED conductor (`python -m shorts.run_batch`) as a k8s
# CronJob. The GPU plane stays host-owned — pods reach it via the host-gpu
# Service/Endpoints (D2). kind/kubectl/kustomize are NOT installed in CI/dev
# sandboxes; these targets are HOST-ONLY and will fail there at runtime. The
# `kubectl --dry-run`/`kustomize build` validations noted in the manifests are
# host/CI-deferred for the same reason.
host-gateway-ip: ## print the Docker bridge gateway IP (kind-local host-gpu Endpoints target)
	@ip route | awk '/default/{print $$3}'
cluster-up: ## [M7] kind cluster + apply the kind-local overlay (host-only; needs native dockerd, kind, kubectl)
	@# Precheck: kind on WSL2 MUST use the native dockerd, not docker-desktop.
	@# With docker-desktop the kind node runs in the Docker Desktop VM and CANNOT
	@# reach the host's ComfyUI/Ollama over the bridge gateway — host-gpu breaks.
	@ctx="$$(docker context show)"; \
	 if [ "$$ctx" = "desktop-linux" ] || [ "$$ctx" = "docker-desktop" ]; then \
	   echo "ERROR: docker context is '$$ctx' (Docker Desktop). The kind node won't reach the host GPU plane."; \
	   echo "  Fix: install native dockerd in WSL2 and switch: docker context use default"; \
	   exit 1; \
	 fi
	@# Idempotent: create the cluster only if absent. The kind config bind-mounts
	@# the host DATA_ROOT into the node (extraMounts) — substitute it in first.
	@DATA_ROOT=$${DATA_ROOT:-$$(pwd)/data}; \
	 if ! kind get clusters | grep -qx "$(KIND_CLUSTER)"; then \
	   sed "s|\$${DATA_ROOT}|$$DATA_ROOT|g" deploy/k8s/overlays/kind-local/kind-cluster.yaml \
	     | kind create cluster --name "$(KIND_CLUSTER)" --config -; \
	 else echo "kind cluster '$(KIND_CLUSTER)' already exists — reusing"; fi
	@# Point the host-gpu Endpoints patch at the LIVE bridge gateway (in place),
	@# then apply the overlay. kustomize reads the patch file as committed, so we
	@# rewrite the placeholder IP to the resolved gateway before `apply -k`.
	@gw="$$(ip route | awk '/default/{print $$3}')"; \
	 echo "cluster-up: patching host-gpu Endpoints -> $$gw"; \
	 sed -i "s|ip: \"[0-9.]*\"|ip: \"$$gw\"|" deploy/k8s/overlays/kind-local/patch-host-gpu-endpoints.yaml; \
	 kubectl apply -k deploy/k8s/overlays/kind-local
	@echo "cluster-up: applied kind-local overlay. Run 'make k8s-secrets VAULT=...' before any real publish."
cluster-down: ## [M7] delete the kind cluster (host data persists on the bind-mounted DATA_ROOT)
	@kind delete cluster --name $(KIND_CLUSTER)
k8s-secrets: ## [M7] inject the host vault env-file into the shorts-secrets Secret (D5; VAULT=path/to/vault.env)
	@kubectl create secret generic shorts-secrets -n shorts \
	   --from-env-file=$${VAULT:?set VAULT=path/to/host/vault.env} \
	   --dry-run=client -o yaml | kubectl apply -f -
print-data-root: ## [M7] print the resolved DATA_ROOT (used by the smoke harness)
	@echo $${DATA_ROOT:-/data}
argo-generate: ## regenerate the committed Argo WorkflowTemplate (the only sanctioned way to update it)
	@uv run python -m deploy.argo.generator.generate > deploy/argo/generated/shorts-workflowtemplate.yaml
k8s-smoke: cluster-up ## the M7 gate — golden offline DAG on kind through Variant A and B (slow, host/CI)
	@# Load the CI-built image into the kind node (no registry), then run the two integration
	@# smoke tests (Variant A: conductor Job; Variant B: Argo CronWorkflow). HOST/CI-ONLY:
	@# needs kind + kubectl + argo + a built shorts-creator:ci image — not present in the
	@# GPU-free sandbox, so these are deselected from the default sweep.
	@kind load docker-image shorts-creator:ci
	@uv run pytest tests/test_k8s_smoke.py -m integration -q
