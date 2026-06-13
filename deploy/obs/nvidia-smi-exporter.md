# nvidia-smi GPU Exporter (replaces DCGM under WSL2)

## Why not DCGM-exporter?

DCGM-exporter relies on NVML/DCGM, which is unavailable under the WSL2 paravirtualisation
layer. The WSL2 guest kernel exposes the GPU through a paravirt driver that does not surface
NVML XID events to the host NVML API.

Consequence: **XID hardware-error detection is unavailable under WSL2**. The NVML XID counter
that DCGM would normally scrape returns no data in WSL2. The GPU alert in this stack is
therefore a **VRAM-free floor** (alert when `nvidia_gpu_mem_free_mib` drops below a threshold),
not an XID-based error alert.

All GPU metrics arrive via the node-exporter **textfile collector** in
`DATA_ROOT/.metrics/textfile/nvidia.prom`. The Prometheus scrape target is the single
`node` job (node-exporter on `:9100`); no separate GPU exporter process is needed.

## Metrics emitted

| Metric | Type | Description |
|---|---|---|
| `nvidia_gpu_util` | gauge | GPU utilization % (0–100) |
| `nvidia_gpu_mem_free_mib` | gauge | Free VRAM in MiB |
| `nvidia_gpu_mem_total_mib` | gauge | Total VRAM in MiB |

## Poller script

Write this to `deploy/obs/nvidia-smi-poller.sh` and make it executable (`chmod +x`).

```bash
#!/usr/bin/env bash
# nvidia-smi textfile-collector poller (ADR 0013 / M6)
# Writes nvidia_gpu_util, nvidia_gpu_mem_free_mib, nvidia_gpu_mem_total_mib to the
# node-exporter textfile directory every INTERVAL seconds, atomically.
# Usage: DATA_ROOT=/data ./nvidia-smi-poller.sh

set -euo pipefail

INTERVAL="${INTERVAL:-15}"
TEXTFILE_DIR="${DATA_ROOT:?DATA_ROOT must be set}/.metrics/textfile"
PROM_FILE="${TEXTFILE_DIR}/nvidia.prom"

mkdir -p "${TEXTFILE_DIR}"

while true; do
    # Query: utilization.gpu, memory.free (MiB), memory.total (MiB)
    # Output is csv,noheader,nounits e.g. "42, 18432, 24576"
    IFS=', ' read -r util mem_free mem_total < <(
        nvidia-smi \
            --query-gpu=utilization.gpu,memory.free,memory.total \
            --format=csv,noheader,nounits \
            2>/dev/null | head -1
    )

    # Fallback when nvidia-smi is absent (CI / non-GPU host)
    util="${util:-0}"
    mem_free="${mem_free:-0}"
    mem_total="${mem_total:-0}"

    TMP_FILE="${PROM_FILE}.tmp"
    cat > "${TMP_FILE}" <<EOF
# HELP nvidia_gpu_util GPU utilization percent (0-100). XID error detection unavailable under WSL2.
# TYPE nvidia_gpu_util gauge
nvidia_gpu_util ${util}
# HELP nvidia_gpu_mem_free_mib Free GPU VRAM in MiB.
# TYPE nvidia_gpu_mem_free_mib gauge
nvidia_gpu_mem_free_mib ${mem_free}
# HELP nvidia_gpu_mem_total_mib Total GPU VRAM in MiB.
# TYPE nvidia_gpu_mem_total_mib gauge
nvidia_gpu_mem_total_mib ${mem_total}
EOF
    # Atomic rename so Prometheus never scrapes a half-written file (ADR 0003 D7)
    mv "${TMP_FILE}" "${PROM_FILE}"

    sleep "${INTERVAL}"
done
```

## Running the poller

### Background loop (quickstart)

```bash
DATA_ROOT=/data INTERVAL=15 bash deploy/obs/nvidia-smi-poller.sh &
```

### systemd unit (Linux host)

Create `/etc/systemd/system/nvidia-smi-poller.service`:

```ini
[Unit]
Description=nvidia-smi textfile-collector poller for node-exporter
After=network.target

[Service]
Type=simple
Environment=DATA_ROOT=/data
Environment=INTERVAL=15
ExecStart=/opt/shorts-creator/deploy/obs/nvidia-smi-poller.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then: `systemctl enable --now nvidia-smi-poller`

### Windows Task Scheduler (WSL2 host)

Because WSL2 services don't auto-start on boot without configuration, the simplest approach
on a Windows host is to add a Task Scheduler entry that runs
`wsl -- bash /opt/shorts-creator/deploy/obs/nvidia-smi-poller.sh` at login with
`DATA_ROOT` set in the task's environment.
