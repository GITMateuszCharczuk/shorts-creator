#!/usr/bin/env bash
#
# up.sh — turn on the host services with one command (runner-first, ADR 0015).
#
# Brings up, in dependency order, the two host planes the conductor needs:
#   1. host GPU plane — ComfyUI (FLUX/LTX/ESRGAN/RIFE/GFPGAN graphs)
#   2. host LLM plane — Ollama serving the per-batch model
# …then runs the conductor's own preflight as the wire check. No cluster:
# the Python conductor (`python -m shorts.run_batch`) orchestrates the DAG
# directly; the k8s profile is the deferred M7 path (ADR 0015a).
#
# Idempotent: re-running skips anything already healthy. Pidfiles + logs live
# under .run/ so down.sh stops exactly what we started. Pair with down.sh to
# stop, and trigger.sh to kick a batch by hand.

set -euo pipefail

# ---------- CONFIG (edit for your machine) ----------------------------------
COMFYUI_HOST="${COMFYUI_HOST:-127.0.0.1}"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"
COMFYUI_DIR="${COMFYUI_DIR:-$HOME/ComfyUI}"           # checkout that contains main.py
COMFYUI_PY="${COMFYUI_PY:-$COMFYUI_DIR/.venv/bin/python}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:14b-instruct}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"   # seconds to wait for each service
# ----------------------------------------------------------------------------

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUNDIR="$ROOT/.run"; mkdir -p "$RUNDIR"   # pidfiles so down.sh can stop exactly what we started

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
need curl
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L || warn "nvidia-smi not found — GPU plane may be unavailable"
ok "dependencies present"

# ---------- 1. host GPU plane: ComfyUI --------------------------------------
if curl -fsS -o /dev/null "http://${COMFYUI_HOST}:${COMFYUI_PORT}/system_stats" 2>/dev/null; then
  ok "ComfyUI already up"
else
  log "starting ComfyUI (host GPU plane)"
  [ -f "$COMFYUI_DIR/main.py" ] || die "ComfyUI not found at $COMFYUI_DIR (set COMFYUI_DIR)"
  [ -x "$COMFYUI_PY" ] || COMFYUI_PY="$(command -v python3)" || die "no python for ComfyUI"
  (cd "$COMFYUI_DIR" && nohup "$COMFYUI_PY" main.py \
      --listen "$COMFYUI_HOST" --port "$COMFYUI_PORT" >"$RUNDIR/comfyui.log" 2>&1 &
   echo $! > "$RUNDIR/comfyui.pid")              # so down.sh stops this exact process
  wait_http "http://${COMFYUI_HOST}:${COMFYUI_PORT}/system_stats" "ComfyUI (process)"
  # /system_stats answers before models+custom-nodes finish loading; also wait for the
  # node registry so a batch never fires against a not-actually-ready ComfyUI.
  wait_http "http://${COMFYUI_HOST}:${COMFYUI_PORT}/object_info" "ComfyUI (nodes loaded)"
fi

# ---------- 2. host LLM plane: Ollama ---------------------------------------
if curl -fsS -o /dev/null "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/version" 2>/dev/null; then
  ok "Ollama already up"
else
  log "starting Ollama (host LLM plane)"
  need ollama
  nohup ollama serve >"$RUNDIR/ollama.log" 2>&1 &
  echo $! > "$RUNDIR/ollama.pid"                 # so down.sh stops this exact process
  wait_http "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/version" "Ollama"
fi
log "ensuring model present: ${OLLAMA_MODEL}"
# Capture first so a real `ollama list` failure (daemon down) isn't masked as "model absent";
# match the full name:tag — grepping the bare name would accept any qwen2.5 variant.
installed_models="$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')" || true
grep -qx "${OLLAMA_MODEL}" <<<"${installed_models}" || ollama pull "${OLLAMA_MODEL}"
ok "LLM model ready"

# ---------- 3. wire check: the conductor's own preflight --------------------
log "verifying conductor→host reachability (the conductor's preflight, ADR 0015)"
"${VENV:-$ROOT/.venv}/bin/python" -m shorts.run_batch --preflight-only \
  || die "conductor preflight failed — see output above"

# ---------- done -------------------------------------------------------------
ok "system is UP"
cat <<EOF

  Next:
    scripts/trigger.sh                       # run a batch now (manual trigger)
    scripts/down.sh                          # stop the system (host-backed data persists)

  The systemd timer (deploy/host/shorts-batch.timer) fires the nightly batch
  automatically — trigger.sh is for on-demand runs (same conductor, ADR 0015 D3).
EOF
