import pytest

from shared.adapters import ModelBackend
from shared.adapters.real import ComfyUIBackend


def test_comfy_satisfies_protocol():
    be = ComfyUIBackend(base_url="http://h:8188", graphs={"flux": "g_flux_v3"})
    assert isinstance(be, ModelBackend)
    assert hasattr(be, "restore")   # restore is part of ModelBackend (added to the M0 Protocol)


def test_graph_version_exposed_for_cache_key():
    be = ComfyUIBackend(base_url="http://h:8188", graphs={"flux": "g_flux_v3"})
    assert be.graph_version("flux") == "g_flux_v3"   # folded into the generative cache key


@pytest.mark.integration
def test_generate_image_live(tmp_path):
    be = ComfyUIBackend(base_url="http://127.0.0.1:8188", graphs={"flux": "g_flux_v3"})
    p = be.generate_image("a green candlestick chart, studio lighting", seed=7)
    assert p.exists()
