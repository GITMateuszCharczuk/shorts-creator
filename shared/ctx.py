import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.logging import StructuredLogger, get_logger


class Quarantined(Exception):
    """Stage signalled a hard quality/safety stop; the video is parked."""


class Degraded(Exception):
    """Stage signalled a soft degrade (e.g. budget tripped); run continues reduced."""


@dataclass
class StageResult:
    outputs: dict[str, Path] = field(default_factory=dict)
    cache_hit: bool = False


@dataclass
class StageContext:
    stage: str
    run_dir: Path
    seed: int
    job: dict[str, Any]
    config: dict[str, Any]
    input_paths: dict[str, str]
    output_paths: dict[str, str]
    backends: dict[str, Any]
    log: StructuredLogger = field(init=False)

    def __post_init__(self):
        self.log = get_logger(self.stage)

    def read_input(self, name: str) -> Path:
        if name not in self.input_paths:
            raise KeyError(f"{self.stage}: undeclared input {name!r}")
        rel = self.input_paths[name]
        if Path(rel).is_absolute():  # declared paths are run-dir-relative; never escape the sandbox
            raise ValueError(
                f"{self.stage}: input {name!r} must be run-dir-relative, got {rel!r}")
        return self.run_dir / rel

    def write_output(self, name: str) -> Path:
        if name not in self.output_paths:
            raise KeyError(f"{self.stage}: undeclared output {name!r}")
        rel = self.output_paths[name]
        if Path(rel).is_absolute():
            raise ValueError(
                f"{self.stage}: output {name!r} must be run-dir-relative, got {rel!r}")
        p = self.run_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def backend(self, capability: str) -> Any:
        if capability not in self.backends:
            raise KeyError(f"{self.stage}: no backend for capability {capability!r}")
        return self.backends[capability]

    def quarantine(self, reason: str) -> None:
        self.log.warning("quarantine", reason=reason)
        raise Quarantined(reason)

    def degrade(self, reason: str) -> None:
        self.log.warning("degrade", reason=reason)
        raise Degraded(reason)

    def set_status(self, status: str) -> None:
        """Section-scoped atomic status update for THIS stage (ADR 0012 §4): read job.json,
        set stages[self.stage].status, write-temp + rename. One writer per <video-id>/ subtree."""
        job_path = self.run_dir / "job.json"
        job = json.loads(job_path.read_text()) if job_path.exists() else {}
        # nested setdefault: set only THIS stage's status, preserving any other sub-keys
        # (started_at/attempts/... that M4/M6 may write) instead of clobbering the section.
        job.setdefault("stages", {}).setdefault(self.stage, {})["status"] = status
        tmp = job_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(job))
        os.replace(tmp, job_path)   # atomic overwrite, POSIX-guaranteed (ADR 0003 D6)
