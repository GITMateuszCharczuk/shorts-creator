from dataclasses import dataclass, fields


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    name: str
    detail: str = ""


@dataclass(frozen=True)
class SafetyThresholds:
    """The single home for every 05b numeric window (ADR 0005 D8). Loaded from
    ctx.config['safety'] via from_config(); the constructor defaults ARE the documented defaults."""
    lufs_min: float = -16.0
    lufs_max: float = -12.0
    tp_max: float = -1.0
    hook_window_s: float = 2.5
    max_hook_silence_s: float = 0.4
    max_black_run_s: float = 0.25
    duration_tol: float = 0.08

    @classmethod
    def from_config(cls, cfg: dict) -> "SafetyThresholds":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (cfg or {}).items() if k in known})
