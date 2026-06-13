import threading

from shared.conductor.gpu import GPU_LOCK, confirm_vram, vram_free_mb


def _stats_with_free_mb(free_mb: int) -> dict:
    # build system_stats whose vram_free (bytes) floors to exactly `free_mb` MiB
    return {"devices": [{"name": "cuda:0", "vram_free": free_mb * 1024 * 1024}]}


def test_confirm_vram_true_when_above_floor():
    assert confirm_vram(8000, _stats_with_free_mb(9000)) is True


def test_confirm_vram_true_at_exact_boundary():
    # H4: the never-co-resident gate is `>=` — free == floor must PASS (guards a >→>= regression)
    assert confirm_vram(8000, _stats_with_free_mb(8000)) is True


def test_confirm_vram_false_below_floor():
    assert confirm_vram(8000, _stats_with_free_mb(7999)) is False


def test_confirm_vram_false_with_no_device():
    # no GPU reported -> 0 free -> cannot satisfy any positive floor
    assert confirm_vram(1, {"devices": []}) is False


def test_parses_comfyui_system_stats():
    stats = {"devices": [{"name": "cuda:0", "vram_total": 16882998016, "vram_free": 14000000000}]}
    assert vram_free_mb(stats) == 13351          # bytes -> MiB, floor


def test_no_device_returns_zero():
    assert vram_free_mb({"devices": []}) == 0


def test_gpu_lock_serializes():
    order = []

    def worker(i):
        with GPU_LOCK:
            order.append(("in", i))
            order.append(("out", i))

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert order[0][0] == "in" and order[1] == ("out", order[0][1])   # no interleave
