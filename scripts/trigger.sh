#!/usr/bin/env bash
# manual batch trigger — byte-identical to the timer's path (ADR 0015 D3)
set -euo pipefail
exec "${VENV:-/srv/shorts-creator/.venv}/bin/python" -m shorts.run_batch "$@"
