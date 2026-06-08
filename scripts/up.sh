#!/usr/bin/env bash
#
# up.sh — turn on the WHOLE system with one command.
#
# Brings up, in dependency order, the three planes the pipeline needs:
#   1. host GPU plane — ComfyUI (FLUX/LTX/ESRGAN/RIFE/GFPGAN graphs)
#   2. host LLM plane — Ollama serving the per-batch model
#   3. control plane  — the kind cluster + Argo + the host-backed PVC
# …then verifies a pod can actually reach the host endpoints (the ADR 0001
# cluster<->host contract) before declaring the system ready.
#
# Idempotent: re-running skips anything already healthy. Pair with down.sh
# to stop, and trigger.sh to kick a batch by hand.
#
# This is the convenience wrapper over the M0 `make` targets; where a piece is
# not wired yet it is called through its make target so there is a single
# source of truth (see Makefile). Adjust the CONFIG block for your machine.

set -euo pipefail

# ---------- CONFIG (edit for your machine) ----------------------------------
COMFYUI_HOST="${COMFYUI_HOST:-127.0.0.1}"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:14b-instruct}"
KIND_CLUSTER="${KIND_CLUSTER:-shorts}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"   # seconds to wait for each service
# ----------------------------------------------------------------------------

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log()  { printf '\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }

# Poll an HTTP endpoint until it answers or we hit HEALTH_TIMEOUT.
wait_http() {
  local url="$1" name="$2" t=0
  log "waiting for $name ($url)…"
  until curl -fsS -o /dev/null "$url" 2>/dev/null; do
    t=$((t+2)); [ "$t" -ge "$HEALTH_TIMEOUT" ] && die "$name not healthy after ${HEALTH_TIMEOUT}s"
    sleep 2
  done
  ok "$name healthy"
}

# ---------- 0. preflight -----------------------------------------------------
log "preflight: checking dependencies"
need docker; need kind; need kubectl; need curl
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L || warn "nvidia-smi not found — GPU plane may be unavailable"
ok "dependencies present"

# ---------- 1. host GPU plane: ComfyUI --------------------------------------
if curl -fsS -o /dev/null "http://${COMFYUI_HOST}:${COMFYUI_PORT}/system_stats" 2>/dev/null; then
  ok "ComfyUI already up"
else
  log "starting ComfyUI (host GPU plane)"
  make host-comfyui-up                     # M0: starts ComfyUI + ensures graphs/models
  wait_http "http://${COMFYUI_HOST}:${COMFYUI_PORT}/system_stats" "ComfyUI"
fi

# ---------- 2. host LLM plane: Ollama ---------------------------------------
if curl -fsS -o /dev/null "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/version" 2>/dev/null; then
  ok "Ollama already up"
else
  log "starting Ollama (host LLM plane)"
  if command -v ollama >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama.log 2>&1 &
  else
    make host-llm-up                       # M0: fallback bring-up if ollama not on PATH
  fi
  wait_http "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/version" "Ollama"
fi
log "ensuring model present: ${OLLAMA_MODEL}"
ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}" || ollama pull "${OLLAMA_MODEL}"
ok "LLM model ready"

# ---------- 3. control plane: kind + Argo + PVC -----------------------------
if kind get clusters 2>/dev/null | grep -qx "${KIND_CLUSTER}"; then
  ok "kind cluster '${KIND_CLUSTER}' already exists"
else
  log "creating kind cluster + Argo + host-backed PVC"
  make cluster-up                          # M0: kind create + argo install + PVC (no GPU device-plugin)
fi
kubectl wait --for=condition=Available deployment --all -n argo --timeout="${HEALTH_TIMEOUT}s" 2>/dev/null \
  || warn "argo deployments not all Available yet — check 'kubectl get pods -n argo'"

# ---------- 4. wire check: pod -> host endpoints ----------------------------
log "verifying cluster→host reachability (ADR 0001 contract)"
make wire                                  # M0: runs a pod that curls ComfyUI + Ollama over the gateway

# ---------- done -------------------------------------------------------------
ok "system is UP"
cat <<EOF

  Next:
    scripts/trigger.sh                       # run a batch now (manual trigger)
    scripts/trigger.sh --dry-run             # stage everything, post nothing
    scripts/down.sh                          # stop the system (host-backed data persists)

  The CronWorkflow also fires the daily batch automatically — trigger.sh is for on-demand runs.
EOF
