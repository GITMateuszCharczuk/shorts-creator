import threading

# Never-co-resident (ADR 0001/0003), conductor-enforced (ADR 0015 D5): every GPU-touching
# stage execution holds this lock; the audio lane never takes it.
GPU_LOCK = threading.Lock()


def vram_free_mb(system_stats: dict) -> int:
    """Parse ComfyUI GET /system_stats; the confirm-evicted gate before diffusion stages."""
    devices = system_stats.get("devices") or []
    if not devices:
        return 0
    return int(devices[0].get("vram_free", 0) // (1024 * 1024))


def confirm_vram(min_free_mb: int, system_stats: dict) -> bool:
    return vram_free_mb(system_stats) >= min_free_mb
