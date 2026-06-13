import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from shared.ctx import StageContext, StageResult


@dataclass(frozen=True)
class StageManifest:
    id: str
    inputs: list[str]
    outputs: list[str]
    compute: Literal["cpu", "gpu"]
    capability: str | None = None
    resources: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.compute == "gpu" and not self.capability:
            raise ValueError(f"gpu stage {self.id} must declare a capability")


@dataclass
class RegisteredStage:
    manifest: StageManifest
    fn: Callable[[StageContext], StageResult | None]


REGISTRY: dict[str, RegisteredStage] = {}


def stage(manifest: StageManifest):
    def deco(fn: Callable[[StageContext], StageResult | None]):
        REGISTRY[manifest.id] = RegisteredStage(manifest=manifest, fn=fn)
        return fn
    return deco


def default_path(name: str) -> str:
    """Declared artifact name -> run-dir-relative path. The SINGLE mapping used everywhere a
    run-dir layout is materialised: the in-process runner (shared/runner.py) and the Argo-mode
    IO-path derivation in shorts/stage.py. Argo shares one PVC run-dir per video, so an input's
    path equals its producer's output path — both sides derive from this same function."""
    binary = {"narration": "narration.wav", "music": "music.wav", "render": "renders/youtube.mp4",
              "thumbnail": "renders/thumbnail.jpg", "captions": "captions.ass"}
    return binary.get(name, f"{name}.json")


def load_manifest(path: Path) -> StageManifest:
    raw = json.loads(path.read_text())
    try:
        return StageManifest(**raw)
    except TypeError as e:
        # an unknown or missing manifest field -> a CLEAR drift error (still strict, just legible).
        raise ValueError(f"invalid stage manifest {path}: {e}") from e
