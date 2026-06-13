import shutil
from pathlib import Path
from typing import Callable


class PreflightFailure(Exception):
    """A pre-batch gate failed — the batch must not start (ADR 0003 D8)."""


def free_space_gate(data_root: Path, *, min_free_gb: float = 80.0) -> None:
    if not Path(data_root).exists():
        raise PreflightFailure(f"data root missing: {data_root}")
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


_INSERT_UNITS = 1600          # YouTube videos.insert cost (ADR 0009 #8); config-overridable


def oauth_token_age_gate(*, token_age_days: float = 0.0, last_used_days: float = 0.0,
                         mode: str = "testing", testing_margin_days: float = 6.0,
                         production_idle_days: float = 150.0) -> None:
    """ADR 0009 #10. Testing-status refresh tokens die at 7 days -> enforce a <7d margin. Production
    tokens don't expire on a schedule (only ~6mo inactivity/revocation) -> check last-used, not age,
    so a healthy Production token doesn't false-alarm weekly."""
    if mode == "testing":
        if token_age_days > testing_margin_days:
            raise PreflightFailure(
                f"OAuth token {token_age_days:.1f}d old > {testing_margin_days}d "
                "(Testing tokens expire at 7d — refresh or move to Production)")
    else:
        if last_used_days > production_idle_days:
            raise PreflightFailure(
                f"OAuth token idle {last_used_days:.0f}d > {production_idle_days}d "
                "(Production tokens revoke on ~6mo inactivity)")


def youtube_quota_gate(*, used_units: int, planned_inserts: int, daily_quota: int = 10000,
                       insert_units: int = _INSERT_UNITS) -> None:
    """Fail the batch BEFORE fan-out if the planned inserts won't fit the day's remaining quota —
    otherwise mid-batch quota exhaustion strands videos in pending-intent (ADR 0003 D8)."""
    need = planned_inserts * insert_units
    if used_units + need > daily_quota:
        raise PreflightFailure(
            f"YouTube quota: need {need} units, only {daily_quota - used_units} left")
