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
        host-up cluster-up build wire submit-batch test voice-ab review \
        obs-up obs-lint

help: ## list targets (grouped by section)
	@awk 'BEGIN{FS=":.*?## "} \
	     /^## /{h=$$0; sub(/^## ?/,"",h); printf "\n\033[1m%s\033[0m\n",h} \
	     /^[a-zA-Z_-]+:.*?## /{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

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

## ---- control plane (runner-first — ADR 0015; cluster targets are the DEFERRED k8s profile) ----
cluster-up: ## [deferred profile] kind cluster + the k8s profile (designed in ADR 0015a; built in M7)
	@echo "deferred (ADR 0015/0015a): the PoC needs no cluster — the Python conductor orchestrates (make trigger); the k8s profile is optional M7"; exit 1
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
	@uv run pytest -q -m "not integration"
voice-ab: ## expressive-voice A/B: reference script through each TTS backend (host-only, ADR 0017 D1)
	@uv run python -m shared.audio.voice_ab
review: ## human-at-publish ramp review CLI (ADR 0014 D2 / 0016 D2)
	@uv run python -m shorts.review

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
