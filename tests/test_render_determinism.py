import hashlib
import json
import os
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "m2"
PINNED = os.environ.get("SHORTS_TOOLCHAIN") == "pinned"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.integration
def test_golden_render_is_stable(tmp_path):
    from shared.layout.remotion import render_manifest_to_frames
    golden = sorted((FIX / "frames_golden").glob("*.png"))
    if not golden:
        pytest.skip("golden frames not yet generated (pinned-image bring-up step; see "
                    "tests/fixtures/m2/frames_golden/README.md)")
    manifest = json.loads((FIX / "render_manifest_golden.json").read_text())
    frames = render_manifest_to_frames(manifest, tmp_path)
    assert len(frames) == len(golden)
    if PINNED:
        assert [_sha(f) for f in frames] == [_sha(g) for g in golden]   # byte-identical tripwire
    else:
        import numpy as np
        from PIL import Image
        from skimage.metrics import structural_similarity as ssim
        for f, g in zip(frames, golden):
            a = np.array(Image.open(f).convert("L"))
            b = np.array(Image.open(g).convert("L"))
            assert ssim(a, b) >= 0.99                                   # advisory elsewhere
