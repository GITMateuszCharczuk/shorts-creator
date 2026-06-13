from pathlib import Path
from typing import Protocol, runtime_checkable

from shared.adapters.types import Judgment


# Capability-narrow protocols (one per capability). The real backends are single-capability,
# so isinstance against the NARROW protocol reflects genuine capability — no NotImplementedError
# conformance stubs needed to satisfy a fat protocol.
@runtime_checkable
class LLMBackend(Protocol):
    # seed -> reproducible best-of-N (ADR 0009)
    def llm(self, prompt: str, seed: int | None = None) -> str: ...
    # constrained JSON + bounded retry (malformed JSON is the #1 local-LLM failure)
    def llm_json(self, prompt: str, seed: int | None = None) -> dict: ...


@runtime_checkable
class ImageBackend(Protocol):
    def generate_image(self, prompt: str, seed: int) -> Path: ...


@runtime_checkable
class Img2VidBackend(Protocol):
    def img2vid(self, image: Path, seed: int) -> Path: ...


@runtime_checkable
class TTSBackend(Protocol):
    def tts(self, text: str) -> Path: ...
    def tts_segments(self, segments: list[dict]) -> Path: ...


@runtime_checkable
class VLMBackend(Protocol):
    def vlm_judge(self, frames: list[Path], script: dict) -> Judgment: ...


@runtime_checkable
class RestoreBackend(Protocol):
    def restore(self, frames: list[Path]) -> list[Path]: ...   # ESRGAN/RIFE/GFPGAN (01d, M2)


# Composite of every capability — the everything-fake FixtureBackend satisfies this, and
# all-capability type hints / the offline-DAG wiring keep working unchanged.
@runtime_checkable
class ModelBackend(LLMBackend, ImageBackend, Img2VidBackend, TTSBackend, VLMBackend,
                   RestoreBackend, Protocol):
    ...


@runtime_checkable
class LayoutEngine(Protocol):
    def render(self, render_manifest: dict) -> list[Path]: ...
