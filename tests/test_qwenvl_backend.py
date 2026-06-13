# tests/test_qwenvl_backend.py
import pytest

from shared.adapters import ModelBackend
from shared.adapters.real import QwenVLBackend


def test_qwenvl_satisfies_protocol():
    assert isinstance(QwenVLBackend(base_url="http://h:8000", model="Qwen2.5-VL"), ModelBackend)


@pytest.mark.integration
def test_vlm_judge_live(tmp_path):
    from PIL import Image
    Image.new("RGB", (108, 192), (12, 30, 18)).save(tmp_path / "hook.png")
    # Ollama OpenAI-compat endpoint
    be = QwenVLBackend(base_url="http://127.0.0.1:11434", model="qwen2.5-vl")
    j = be.vlm_judge([tmp_path / "hook.png"], {"hook": {"spoken": "x"}})
    assert set(j.scores) == {"coherence", "pacing"}      # visual sub-scores only (ADR 0016 D5)
    assert isinstance(j.observations, tuple)
