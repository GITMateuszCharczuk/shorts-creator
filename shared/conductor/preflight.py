import shutil
from pathlib import Path
from typing import Callable


class PreflightFailure(Exception):
    """A pre-batch gate failed — the batch must not start (ADR 0003 D8)."""


def free_space_gate(data_root: Path, *, min_free_gb: float = 80.0) -> None:
    free_gb = shutil.disk_usage(data_root).free / 1e9
    if free_gb < min_free_gb:
        raise PreflightFailure(f"{free_gb:.0f} GB free < {min_free_gb} GB minimum "
                               f"(frames peak ~10 GB/cut — ADR re-review)")


def host_health_gate(
    *,
    comfy_url: str,
    ollama_url: str,
    get: Callable[[str], int] | None = None,
) -> None:
    """ADR 0003 D2 / spec Ch.8: the conductor GATES fan-out on host health — an unhealthy host
    fails the batch loudly at the start, never as N per-video retry-storms mid-run."""
    if get is None:
        import httpx
        get = lambda u: httpx.get(u, timeout=10).status_code   # noqa: E731
    for url in (f"{comfy_url}/system_stats", f"{ollama_url}/api/version"):
        if get(url) != 200:
            raise PreflightFailure(f"host service unhealthy: {url}")


def run_preflight(checks: list[Callable[[], None]]) -> None:
    for check in checks:                          # pluggable: M5 adds the OAuth token-age check
        check()
