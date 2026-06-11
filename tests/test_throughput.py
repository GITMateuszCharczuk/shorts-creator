import json
import time
from pathlib import Path

import pytest

from shared.layout.throughput import (
    FAIL_MS_PER_FRAME,
    TARGET_MS_PER_FRAME,
    ms_per_frame,
    within_budget,
)


def test_ms_per_frame_and_budget():
    # 60 frames rendered in 3.0s -> 50 ms/frame
    assert ms_per_frame(elapsed_s=3.0, frames=60) == 50.0
    assert within_budget(50.0) is (50.0 <= FAIL_MS_PER_FRAME)


def test_published_target_below_fail_threshold():
    assert TARGET_MS_PER_FRAME < FAIL_MS_PER_FRAME   # target leaves headroom under the tripwire


@pytest.mark.integration
def test_compositor_within_budget(tmp_path):
    from shared.layout.remotion import render_manifest_to_frames
    manifest = json.loads(
        (Path(__file__).parent / "fixtures/m2/render_manifest_golden.json").read_text())
    t0 = time.perf_counter()
    frames = render_manifest_to_frames(manifest, tmp_path)
    mspf = ms_per_frame(elapsed_s=time.perf_counter() - t0, frames=len(frames))
    Path("runs/.metrics").mkdir(parents=True, exist_ok=True)
    Path("runs/.metrics/compositor_mspf.json").write_text(json.dumps({"ms_per_frame": mspf}))
    assert within_budget(mspf), f"{mspf} ms/frame exceeds the {FAIL_MS_PER_FRAME} tripwire"
