import pytest

from shared.adapters import ImageBackend, Img2VidBackend, RestoreBackend
from shared.adapters.real import ComfyUIBackend


def test_comfy_satisfies_protocol():
    be = ComfyUIBackend(base_url="http://h:8188", graphs={"flux": "g_flux_v3"})
    # ComfyUI genuinely provides the three GPU-graph capabilities — narrow protocols reflect that.
    assert isinstance(be, ImageBackend)
    assert isinstance(be, Img2VidBackend)
    assert isinstance(be, RestoreBackend)


def test_graph_version_exposed_for_cache_key():
    be = ComfyUIBackend(base_url="http://h:8188", graphs={"flux": "g_flux_v3"})
    assert be.graph_version("flux") == "g_flux_v3"   # folded into the generative cache key


@pytest.mark.integration
def test_generate_image_live(tmp_path):
    be = ComfyUIBackend(base_url="http://127.0.0.1:8188", graphs={"flux": "g_flux_v3"})
    p = be.generate_image("a green candlestick chart, studio lighting", seed=7)
    assert p.exists()
