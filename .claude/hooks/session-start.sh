#!/bin/bash
# SessionStart hook: ensure the "superpowers" Claude Code plugin is installed.
#
# Why: remote (Claude Code on the web) sessions run in an ephemeral container that
# is reclaimed when idle, so user-scoped plugins under ~/.claude do not persist.
# This hook re-installs superpowers on each session start. It is idempotent and
# fail-soft: it never blocks session startup, even with no network or no CLI.
#
# Note: a freshly installed plugin generally becomes active on the NEXT session
# (Claude Code reads plugins at startup). This hook guarantees it is present.
#
# All diagnostic output goes to stderr so it is not injected into session context.

set -uo pipefail

MARKETPLACE="obra/superpowers-marketplace"
PLUGIN="superpowers@superpowers-marketplace"

log() { echo "[session-start] $*" >&2; }

if ! command -v claude >/dev/null 2>&1; then
  log "claude CLI not found on PATH; skipping superpowers install"
  exit 0
fi

if claude plugin list 2>/dev/null | grep -q "superpowers@superpowers-marketplace"; then
  log "superpowers already installed; nothing to do"
  exit 0
fi

log "installing superpowers plugin..."
claude plugin marketplace add "$MARKETPLACE" >&2 2>&1 || log "marketplace add failed (continuing)"
claude plugin install "$PLUGIN"            >&2 2>&1 || log "plugin install failed (continuing)"

if claude plugin list 2>/dev/null | grep -q "superpowers@superpowers-marketplace"; then
  log "superpowers installed successfully"
else
  log "superpowers install did not complete (continuing without blocking session)"
fi

exit 0
