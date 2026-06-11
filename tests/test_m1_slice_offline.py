import json
import shutil
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "m1"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required for render")
def test_m1_slice_produces_mp4(run_dir, tmp_path):
    from tests.helpers.m1 import run_m1_slice  # thin harness wiring fakes + StageTimer

    timing = tmp_path / "timing.jsonl"
    result = run_m1_slice(run_dir=run_dir, seed=7, fixtures=FIX, timing_log=timing)
    mp4 = run_dir / result["render"]
    assert mp4.exists() and mp4.stat().st_size > 0
    stages_timed = {json.loads(line)["stage"] for line in timing.read_text().splitlines()}
    assert {"00a", "00b", "02", "03", "05"}.issubset(stages_timed)
