#!/usr/bin/env bash
#
# trigger.sh — manually kick off a batch run (the on-demand counterpart to the
# CronWorkflow). Submits the same `shorts-batch` WorkflowTemplate the scheduler
# uses, so a manual run and a scheduled run are byte-identical except for trigger.
#
# Usage:
#   scripts/trigger.sh                                 # today's batch, default profiles
#   scripts/trigger.sh --profiles finance,business     # choose niches
#   scripts/trigger.sh --count 4                        # videos per profile
#   scripts/trigger.sh --dry-run                        # stage metadata, post NOTHING
#   scripts/trigger.sh --watch                          # stream progress until done
#
# `concurrencyPolicy: Forbid` (ADR 0003) is enforced by Argo, so a manual
# trigger that overlaps a running batch is rejected rather than co-resident.

set -euo pipefail

PROFILES="${PROFILES:-finance,business}"
COUNT="${COUNT:-2}"
DRY_RUN="false"
WATCH=""
TEMPLATE="${TEMPLATE:-shorts-batch}"   # the WorkflowTemplate name (deploy/argo)
NAMESPACE="${NAMESPACE:-argo}"

while [ $# -gt 0 ]; do
  case "$1" in
    --profiles) PROFILES="$2"; shift 2 ;;
    --count)    COUNT="$2";    shift 2 ;;
    --dry-run)  DRY_RUN="true"; shift ;;
    --watch)    WATCH="--watch"; shift ;;
    -h|--help)  grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

command -v argo >/dev/null 2>&1 || { echo "✗ argo CLI not found" >&2; exit 1; }

echo "▸ submitting '${TEMPLATE}' — profiles=${PROFILES} count=${COUNT} dry_run=${DRY_RUN}"
argo submit --from "workflowtemplate/${TEMPLATE}" \
  -n "${NAMESPACE}" \
  -p profiles="${PROFILES}" \
  -p count="${COUNT}" \
  -p dry_run="${DRY_RUN}" \
  --generate-name "shorts-manual-" \
  ${WATCH}
