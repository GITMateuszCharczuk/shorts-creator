#!/usr/bin/env bash
#
# down.sh — stop the host services, reversing up.sh. Data under DATA_ROOT
# (ledgers, run artifacts) SURVIVES a teardown — that's deliberate (cross-run
# dedup depends on it). There is no cluster to tear down: the conductor is a
# host process (runner-first, ADR 0015).
#
# Host processes are stopped by the PID up.sh recorded under .run/ (precise, no
# broad `pkill -f` that could hit unrelated processes).
#
# Usage:
#   scripts/down.sh            # stop ComfyUI + Ollama started by up.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNDIR="$ROOT/.run"

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
stop_pidfile "ComfyUI" "$RUNDIR/comfyui.pid"

ok "host services down — data persists; re-run scripts/up.sh to resume"
