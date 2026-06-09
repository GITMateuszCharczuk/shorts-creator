#!/usr/bin/env bash
#
# down.sh — stop the system, reversing up.sh. The PVC is host-backed (kind
# extraMounts), so the novelty/posts ledgers and run artifacts SURVIVE a teardown
# — that's deliberate (cross-run dedup depends on it). Use --purge only if you
# really want the cluster gone; data on the host dir still remains.
#
# Host processes are stopped by the PID up.sh recorded under .run/ (precise, no
# broad `pkill -f` that could hit unrelated processes), falling back to the M0
# make target. Status is only reported on a teardown that actually happened.
#
# Usage:
#   scripts/down.sh            # stop host services, leave the cluster intact
#   scripts/down.sh --purge    # also `kind delete cluster` (data on host persists)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNDIR="$ROOT/.run"
KIND_CLUSTER="${KIND_CLUSTER:-shorts}"
PURGE="false"
[ "${1:-}" = "--purge" ] && PURGE="true"

log()  { printf '\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }

# Stop a process we started by its recorded pidfile; never pattern-kill.
stop_pidfile() {
  local name="$1" pidfile="$2" pid
  if [ -f "$pidfile" ] && pid="$(cat "$pidfile" 2>/dev/null)" && [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null && ok "$name stopped (pid $pid)"
    rm -f "$pidfile"
  else
    warn "$name: no tracked process (not started by up.sh, or already stopped) — leaving it alone"
    rm -f "$pidfile" 2>/dev/null || true
  fi
}

log "stopping host LLM plane (Ollama)"
stop_pidfile "Ollama" "$RUNDIR/ollama.pid"

log "stopping host GPU plane (ComfyUI)"
if make host-comfyui-down 2>/dev/null; then
  ok "ComfyUI stopped"
else
  warn "ComfyUI teardown target not wired (M0) or failed — stop it manually if running"
fi

if [ "$PURGE" = "true" ]; then
  log "deleting kind cluster '${KIND_CLUSTER}' (host-backed data persists)"
  kind delete cluster --name "${KIND_CLUSTER}" || true
  ok "cluster deleted"
else
  ok "cluster left intact — re-run scripts/up.sh to resume (fast path)"
fi
