import threading

from shared.conductor.gpu import GPU_LOCK, vram_free_mb


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
