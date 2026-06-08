#!/usr/bin/env bash
#
# down.sh — stop the system. The PVC is host-backed (kind extraMounts), so the
# novelty/posts ledgers and run artifacts SURVIVE a teardown — that's deliberate
# (cross-run dedup depends on it). Use --purge only if you really want the
# cluster gone; data on the host dir still remains.
#
# Usage:
#   scripts/down.sh            # stop host services, leave the cluster intact
#   scripts/down.sh --purge    # also `kind delete cluster` (data on host persists)

set -euo pipefail

KIND_CLUSTER="${KIND_CLUSTER:-shorts}"
PURGE="false"
[ "${1:-}" = "--purge" ] && PURGE="true"

log() { printf '\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }

log "stopping host LLM plane (Ollama)"
pkill -f "ollama serve" 2>/dev/null && ok "Ollama stopped" || true

log "stopping host GPU plane (ComfyUI)"
make host-comfyui-down 2>/dev/null || pkill -f "comfyui" 2>/dev/null || true
ok "ComfyUI stopped"

if [ "$PURGE" = "true" ]; then
  log "deleting kind cluster '${KIND_CLUSTER}' (host-backed data persists)"
  kind delete cluster --name "${KIND_CLUSTER}" || true
  ok "cluster deleted"
else
  ok "cluster left intact — re-run scripts/up.sh to resume (fast path)"
fi
