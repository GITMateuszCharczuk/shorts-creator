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

    def _response_text(self, r: httpx.Response) -> str:
        # an Ollama error body ({"error": ...}) or a non-JSON body must become a CLEAR error,
        # not a bare KeyError/JSONDecodeError escaping to the caller.
        try:
            body = r.json()
        except ValueError as e:
            raise ValueError(f"Ollama returned a non-JSON body: {r.text[:200]!r}") from e
        if "response" not in body:
            raise ValueError(f"Ollama response missing 'response' (error body? {body})")
        return body["response"]

    def llm(self, prompt: str, seed: int | None = None) -> str:
        url, payload = self._request(prompt, seed)
        r = httpx.post(url, json=payload, timeout=self._timeout)
        r.raise_for_status()
        return self._response_text(r)

    def llm_json(self, prompt: str, seed: int | None = None) -> dict:
        """Constrained decoding (Ollama format=json) + ONE bounded repair retry —
        malformed JSON is the #1 local-LLM failure mode (architecture re-review)."""
        url, payload = self._request(prompt, seed)
        payload["format"] = "json"
        last_err = None
        for _ in range(2):
            r = httpx.post(url, json=payload, timeout=self._timeout)
            r.raise_for_status()
            try:
                return json.loads(self._response_text(r))
            except (json.JSONDecodeError, ValueError) as e:
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


# ADR 0015 D4 — everything runs in one WSL2 filesystem under DATA_ROOT; ComfyUI's output dir is
# under DATA_ROOT, so _await_output returns directly-addressable paths (no host<->pod translation).
class ComfyUIBackend:
    """ModelBackend for the host ComfyUI: FLUX (generate_image), LTX (img2vid),
    ESRGAN+RIFE+GFPGAN (restore). Each capability maps to a named, versioned graph."""

    def __init__(self, base_url: str, graphs: dict[str, str], timeout: float = 600.0):
        self._base = base_url.rstrip("/")
        self._graphs = graphs           # {capability: graph_version}
        self._timeout = timeout
        self.model_id = "comfyui"

    def graph_version(self, capability: str) -> str:
        return self._graphs[capability]

    def _submit(self, capability: str, inputs: dict, seed: int):
        import httpx
        graph = self._build_graph(capability, inputs, seed)  # JSON workflow for /prompt
        r = httpx.post(f"{self._base}/prompt", json={"prompt": graph}, timeout=self._timeout)
        r.raise_for_status()
        try:
            body = r.json()
        except ValueError as e:   # same hardening class as OllamaBackend._response_text
            raise ValueError(f"ComfyUI returned a non-JSON body: {r.text[:200]!r}") from e
        if "prompt_id" not in body:
            raise ValueError(f"ComfyUI response missing 'prompt_id' (error body? {body})")
        return self._await_output(body["prompt_id"])          # poll /history, return artifact path

    def generate_image(self, prompt: str, seed: int):
        return self._submit("flux", {"prompt": prompt}, seed)

    def img2vid(self, image, seed: int):
        return self._submit("ltx", {"image": str(image)}, seed)

    def restore(self, frames):
        return self._submit("restore", {"frames": [str(f) for f in frames]}, seed=0)

    def _build_graph(self, capability, inputs, seed):
        raise NotImplementedError("ComfyUI workflow JSON wired at host bring-up")

    def _await_output(self, prompt_id):
        raise NotImplementedError("poll /history wired at host bring-up")

    # llm/tts/vlm_judge not provided by ComfyUI
    def llm(self, prompt, seed=None):
        raise NotImplementedError

    def llm_json(self, prompt, seed=None):
        raise NotImplementedError

    def tts(self, text):
        raise NotImplementedError

    def vlm_judge(self, frames, script):
        raise NotImplementedError


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
