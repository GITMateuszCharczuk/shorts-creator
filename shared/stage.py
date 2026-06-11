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


def load_manifest(path: Path) -> StageManifest:
    raw = json.loads(path.read_text())
    return StageManifest(**raw)
