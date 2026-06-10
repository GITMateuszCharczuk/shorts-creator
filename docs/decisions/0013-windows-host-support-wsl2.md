# ADR 0013 — Windows host support (run the Linux stack inside WSL2)

- **Status:** Accepted (2026-06-09)
- **Builds on:** [ADR 0001](0001-lightened-runtime-architecture.md) (GPU plane is host *processes*,
  not in-kind — the decoupling that makes Windows viable),
  [ADR 0003](0003-resilience-concurrency-observability.md) (supervision + boot reconciler),
  [ADR 0011](0011-performance-and-optimization.md) (LTX/VRAM budget).
- **Touches:** ARCHITECTURE §6 (host wiring) + §8 (run); spec Ch.8 (operations); `scripts/`.
- **Origin:** the developer runs Windows; the requirement is "runnable on Windows," with the kube
  containers staying Linux. A feasibility + performance check decided the topology.
- **Extended by [ADR 0015](0015-runner-first-orchestration.md):** the control plane inside the
  WSL2 distro is now the **Python runner under a systemd timer** — kind/Argo are a deferred
  deployment profile — which shrinks this ADR's residual risk surface (no Docker/kind lifecycle to
  keep alive under Windows Update); the driver/toolchain/ext4 rules here are unchanged.

## Context

The host owns the GPU (a 16 GB Blackwell 5070 Ti) running ComfyUI + Ollama natively, with a thin
Argo/`kind` control plane orchestrating Linux CPU stages over HTTP. **GPU-in-kind was already
dropped (ADR 0001)** — the containers never touch the GPU — which is exactly what makes a Windows
host tractable: only the *host processes* need GPU access, and WSL2 provides that.

The reviewed alternative — ComfyUI/Ollama as **native Windows** apps with `kind` reaching them via
`host.docker.internal` — was rejected: the bash lifecycle (`nohup`/pidfile/`systemd`) can't manage
Windows-native processes, splitting host bring-up/teardown across two worlds for a marginal GPU-perf
gain. **Decision: run the entire Linux stack inside one WSL2 distro; Windows is just the substrate
hosting WSL2 + the NVIDIA Windows driver.** Near-zero change to the Linux design.

### Performance check (the worry was "WSL = 5% of native")

That is inverted. WSL2 GPU overhead is **workload-shaped, single-digit-to-~10%**, and this pipeline
sits at the near-native end: NVIDIA's worst case (short kernels) is **≥90% of native**, long
GPU-saturating kernels are **within ~1%**, and the dominant real penalty is **file-I/O latency —
only on `/mnt/c`**. Stage-batching keeps the GPU saturated (long kernels) and the artifact bus
already lives on ext4 (ADR 0003 D6 / this ADR D3), so both penalties are avoided by construction.
Expect a few percent, validated on the box.

## Decision

1. **One WSL2 distro runs everything** — ComfyUI + Ollama (GPU plane) **and** Docker + `kind` +
   Argo (control plane). The bash scripts (`up.sh`/`down.sh`/`trigger.sh`) run unchanged inside it.
2. **Driver discipline.** Install the **NVIDIA *Windows* driver only** (570+ for Blackwell); WSL
   injects `libcuda` via `/usr/lib/wsl/lib` — **never install a Linux GPU driver inside WSL**. Use
   the **WSL-Ubuntu CUDA toolkit** package, not the generic Linux one. Blackwell sm_120 needs **CUDA
   12.8 + cu128 torch** (already pinned, ADR 0003 D8) and a **pinned Blackwell-good Ollama** (a
   regression existed ~Nov 2025).
3. **Data on ext4, never `/mnt/c`.** The host-backed PVC (`kind extraMounts`) and the `models/`
   cache live on the WSL2 ext4 filesystem — `/mnt/c` is the one path that turns WSL2's I/O latency
   into a real penalty and has permission/inode quirks.
4. **`systemd` + stay-alive.** Enable `systemd=true` in `/etc/wsl.conf` so the supervisor
   (`Restart=always`) and the boot reconciler (ADR 0003 D9) work as designed. Because WSL2 doesn't
   self-start, a **Windows Task Scheduler task runs `wsl` at logon/boot** to keep the distro (and
   thus the daily `CronWorkflow`) alive across Windows reboots — the boot reconciler then resumes any
   interrupted batch.
5. **Networking.** Pods reach the GPU plane via **`host.docker.internal`** (Docker-Desktop/WSL2
   gateway) rather than a raw bridge IP; the `host/README` gateway-wiring deliverable gets a WSL2 row.
6. **Resource sizing.** A `.wslconfig` pins WSL2 RAM/CPU so the host-RAM model cache (ADR 0011) and
   the lane-fork CPU work have headroom instead of WSL2's defaults.
7. **A thin Windows entry point.** `scripts/win/shorts.ps1 {up|down|trigger}` wraps `wsl … bash -lc
   "./scripts/<x>.sh"` so it feels native from PowerShell; the bash scripts stay the single source of
   truth — no PowerShell reimplementation.

## Consequences

**Positive**
- "Runnable on Windows" with **near-zero divergence** from the Linux design — same scripts,
  schemas, systemd, paths, networking. Linux remains the reference target; WSL2 is the Windows path.
- The hardest part (GPU) is free because the GPU plane was already decoupled from `kind`.

**Negative / costs**
- **Tighter VRAM**: the Windows desktop + WSLg compositor consume several hundred MB of the 16 GB —
  this **hardens** the already-required "LTX quantized + tiled-VAE" decision (ADR 0011 / parity
  review) into a non-negotiable on Windows. Run the GPU plane as headless as possible.
- Two Windows-specific operational pieces (Task Scheduler keep-alive, `.wslconfig`) that have no
  Linux analogue.
- A few percent GPU overhead vs native Linux — accepted, and small for this workload.

## Open (tracked)

- Validate the **WSL2 CUDA path on the actual box** (driver + cu128 + Blackwell Ollama pin) — folds
  into the existing sm_120 validate-on-box item (ADR 0003 D8).
- The `.wslconfig` RAM/CPU numbers and the Task Scheduler unit, settled at M0/M4 against the real
  machine.
