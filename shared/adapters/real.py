import json
from pathlib import Path

import httpx

from shared.adapters.types import Judgment


class OllamaBackend:
    """ModelBackend.llm via an Ollama /api/generate endpoint on the host."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def _request(self, prompt: str, seed: int | None = None) -> tuple[str, dict]:
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        if seed is not None:
            payload["options"] = {"seed": seed, "temperature": 0.8}  # seed the SAMPLER (ADR 0009)
        return (f"{self._base}/api/generate", payload)

    def llm(self, prompt: str, seed: int | None = None) -> str:
        url, payload = self._request(prompt, seed)
        r = httpx.post(url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        return r.json()["response"]

    def llm_json(self, prompt: str, seed: int | None = None) -> dict:
        """Constrained decoding (Ollama format=json) + ONE bounded repair retry —
        malformed JSON is the #1 local-LLM failure mode (architecture re-review)."""
        url, payload = self._request(prompt, seed)
        payload["format"] = "json"
        last_err = None
        for _ in range(2):
            r = httpx.post(url, json=payload, timeout=self._timeout)
            r.raise_for_status()
            text = r.json()["response"]
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_err = e
                payload["prompt"] = (f"{prompt}\n\nYour previous output was invalid JSON "
                                     f"({e}). Return ONLY valid JSON.")
        raise ValueError(f"LLM returned invalid JSON after retry: {last_err}")

    # M2 GPU capabilities — not provided by the LLM endpoint.
    def generate_image(self, prompt: str, seed: int) -> Path:
        raise NotImplementedError("generate_image is an M2 ComfyUI backend")

    def img2vid(self, image: Path, seed: int) -> Path:
        raise NotImplementedError("img2vid is an M2 ComfyUI backend")

    def tts(self, text: str) -> Path:
        raise NotImplementedError("use KokoroBackend for tts")

    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment:
        raise NotImplementedError("vlm_judge is an M3 backend")

    def restore(self, frames: list[Path]) -> list[Path]:
        raise NotImplementedError("restore is an M2 ComfyUI backend")


class KokoroBackend:
    """ModelBackend.tts via Kokoro-82M; writes a wav and returns its path."""

    def __init__(self, out_dir: Path, voice: str = "af_heart", sample_rate: int = 24000):
        self._out = Path(out_dir)
        self._voice = voice
        self._sr = sample_rate

    def tts(self, text: str) -> Path:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline  # host-only import
        self._out.mkdir(parents=True, exist_ok=True)
        pipe = KPipeline(lang_code="a")
        audio = np.concatenate([chunk.audio for chunk in pipe(text, voice=self._voice)])
        path = self._out / "narration.wav"
        sf.write(path, audio, self._sr)
        return path

    def llm(self, prompt: str, seed: int | None = None) -> str:
        raise NotImplementedError("use OllamaBackend for llm")

    def llm_json(self, prompt: str, seed: int | None = None) -> dict:
        raise NotImplementedError("use OllamaBackend for llm_json")

    def generate_image(self, prompt: str, seed: int) -> Path:
        raise NotImplementedError
    def img2vid(self, image: Path, seed: int) -> Path:
        raise NotImplementedError
    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment:
        raise NotImplementedError
    def restore(self, frames: list[Path]) -> list[Path]:
        raise NotImplementedError
