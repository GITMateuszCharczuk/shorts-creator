# ComfyUI Queue Depth Exporter

## Purpose

ComfyUI exposes a `/queue` endpoint that reports the current render backlog. Scraping this
provides the GPU-plane backpressure signal: when the queue is deep the conductor should
back off batch submission to avoid starving memory and causing OOM kills.

The metric is written to the node-exporter textfile directory and scraped by the single
`node` Prometheus job, exactly like the GPU metrics (no separate Prometheus exporter process).

## Metrics emitted

| Metric | Type | Description |
|---|---|---|
| `comfyui_queue_depth` | gauge | Total items waiting + running in ComfyUI queue |

## Endpoint reference

```
GET http://127.0.0.1:8188/queue
```

Response shape (ComfyUI ≥ 0.3):

```json
{
  "queue_running": [[...], ...],
  "queue_pending": [[...], ...]
}
```

`comfyui_queue_depth = len(queue_running) + len(queue_pending)`

Some builds expose `exec_info.queue_remaining` at `GET /prompt`; the poller below handles
both shapes with a fallback.

## Poller script

Write this to `deploy/obs/comfyui-queue-poller.sh` and make it executable (`chmod +x`).

```bash
#!/usr/bin/env bash
# ComfyUI queue-depth textfile-collector poller (M6)
# Writes comfyui_queue_depth to the node-exporter textfile directory every INTERVAL seconds,
# atomically. Requires: curl, jq.
# Usage: DATA_ROOT=/data COMFYUI_URL=http://127.0.0.1:8188 ./comfyui-queue-poller.sh

set -euo pipefail

INTERVAL="${INTERVAL:-15}"
COMFYUI_URL="${COMFYUI_URL:-http://127.0.0.1:8188}"
TEXTFILE_DIR="${DATA_ROOT:?DATA_ROOT must be set}/.metrics/textfile"
PROM_FILE="${TEXTFILE_DIR}/comfyui_queue.prom"

mkdir -p "${TEXTFILE_DIR}"

while true; do
    # Fetch the /queue endpoint; fall back to 0 on any error (ComfyUI offline / starting up)
    QUEUE_JSON=$(curl -sf --max-time 5 "${COMFYUI_URL}/queue" 2>/dev/null || echo '{}')

    # Sum running + pending list lengths
    DEPTH=$(echo "${QUEUE_JSON}" | jq -r '
        (.queue_running | if type == "array" then length else 0 end) +
        (.queue_pending | if type == "array" then length else 0 end)
    ' 2>/dev/null || echo "0")

    # Fallback: try exec_info.queue_remaining from /prompt if /queue gave nothing useful
    if [ "${DEPTH}" = "0" ] || [ -z "${DEPTH}" ]; then
        PROMPT_JSON=$(curl -sf --max-time 5 "${COMFYUI_URL}/prompt" 2>/dev/null || echo '{}')
        DEPTH=$(echo "${PROMPT_JSON}" | jq -r '.exec_info.queue_remaining // 0' 2>/dev/null || echo "0")
    fi

    DEPTH="${DEPTH:-0}"

    TMP_FILE="${PROM_FILE}.tmp"
    cat > "${TMP_FILE}" <<EOF
# HELP comfyui_queue_depth Total number of items running + pending in the ComfyUI queue.
# TYPE comfyui_queue_depth gauge
comfyui_queue_depth ${DEPTH}
EOF
    # Atomic rename so Prometheus never scrapes a half-written file (ADR 0003 D7)
    mv "${TMP_FILE}" "${PROM_FILE}"

    sleep "${INTERVAL}"
done
```

## Running the poller

### Background loop (quickstart)

```bash
DATA_ROOT=/data COMFYUI_URL=http://127.0.0.1:8188 INTERVAL=15 \
    bash deploy/obs/comfyui-queue-poller.sh &
```

### systemd unit (Linux host)

Create `/etc/systemd/system/comfyui-queue-poller.service`:

```ini
[Unit]
Description=ComfyUI queue-depth textfile-collector poller
After=network.target

[Service]
Type=simple
Environment=DATA_ROOT=/data
Environment=COMFYUI_URL=http://127.0.0.1:8188
Environment=INTERVAL=15
ExecStart=/opt/shorts-creator/deploy/obs/comfyui-queue-poller.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then: `systemctl enable --now comfyui-queue-poller`

### Windows Task Scheduler (WSL2 host)

Add a Task Scheduler entry that runs
`wsl -- bash /opt/shorts-creator/deploy/obs/comfyui-queue-poller.sh` at login with
`DATA_ROOT` and `COMFYUI_URL` in the environment.
