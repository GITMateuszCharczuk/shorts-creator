# shorts-creator — convenience entrypoints.
#
# One-command lifecycle:
#   make up        # turn the whole system on  (host GPU + Ollama + kind/Argo)  -> scripts/up.sh
#   make trigger   # run a batch now (manual)                                   -> scripts/trigger.sh
#   make down      # stop the system (host-backed data persists)               -> scripts/down.sh
#
# The granular targets below are the single source of truth the scripts call;
# M0 fills in the bodies marked `# M0:`.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

KIND_CLUSTER ?= shorts
PROFILES     ?= finance,business
COUNT        ?= 2

.PHONY: help up down trigger dry-run \
        host-comfyui-up host-comfyui-down host-llm-up \
        host-up cluster-up build wire submit-batch test

help: ## list targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

## ---- one-command lifecycle (wrappers over scripts/) ----
up: ## turn the whole system on with one command
	@scripts/up.sh
down: ## stop the system (add ARGS=--purge to delete the cluster)
	@scripts/down.sh $(ARGS)
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

## ---- control plane (M0 wires these) ----
cluster-up: ## kind cluster + Argo + the host-backed PVC (no GPU device-plugin)
	@echo "M0: kind create cluster --name $(KIND_CLUSTER) (deploy/kind) + argo install (deploy/argo) + PVC (deploy/storage)"; exit 1
build:      ## build stage images and kind-load them
	@echo "M0: build stages/* images + kind load"; exit 1
wire:       ## verify a pod can reach host ComfyUI/LLM over the gateway (ADR 0001)
	@echo "M0: run a pod that curls ComfyUI /system_stats + Ollama /api/version"; exit 1

## ---- runs ----
submit-batch: ## scheduled-equivalent batch submit (CronWorkflow uses the same template)
	@scripts/trigger.sh --profiles $(PROFILES) --count $(COUNT)

## ---- dev ----
test: ## schema validation + golden fixtures + GPU-free full-DAG run via shared/fakes (ADR 0010)
	@echo "M0: run pytest over schemas + fixtures + faked DAG"; exit 1
