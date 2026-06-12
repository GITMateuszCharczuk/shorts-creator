"""python -m shorts.run_batch — the nightly conductor entrypoint (ADR 0015)."""
import shutil
import time
from pathlib import Path
from typing import Callable

from shared.conductor.lock import acquire_lock, release_lock
from shared.conductor.preflight import (
    free_space_gate,
    host_health_gate,
    oauth_token_age_gate,
    youtube_quota_gate,
)
from shared.obs.metrics import render_batch_metrics, render_stage_metrics, write_metrics
from shared.obs.quarantine_rate import trailing_rate
from shared.ops.budgets import data_api_budget_gate
from shared.ops.cache_evict import evict_to_cap
from shared.ops.gc import PROTECTED, quarantine_to_delete, runs_to_delete


def batch_flow(*, lock_path: Path, data_root: Path, preflight, plan, execute, commit, backup):
    """Lock -> preflight -> (resume|plan) -> execute -> fan-in commit -> backup -> unlock.
    Commit/backup run only on success; the lock is released on EVERY path."""
    acquire_lock(lock_path)
    try:
        preflight()
        batch = plan()
        execute(batch)
        commit(batch)
        backup()
        return batch
    finally:
        release_lock(lock_path)


def build_preflight(hooks: dict) -> list:
    """The config-driven pre-flight in the canonical order (ADR 0003 D2/D8, ADR 0009 #8/#10):
    cheap local checks first, then host health, then the credential/quota/budget gates. A gate
    not wired in (tests, partial bring-up) defaults to a no-op; production_preflight always
    supplies all five."""
    noop = lambda: None   # noqa: E731
    return [hooks.get("free_space", noop), hooks.get("host_health", noop),
            hooks.get("oauth", noop), hooks.get("youtube_quota", noop),
            hooks.get("data_budget", noop)]


def production_preflight(*, cfg: dict, data_root: Path, usage: dict,
                         http_get: Callable[[str], int] | None = None):
    """Compose the five REAL gates from the resolved config + the day's usage counters into the
    single closure batch_flow calls once. cfg keys: gc.min_free_gb, hosts.comfy_url/ollama_url,
    oauth_mode, budgets.youtube_units, budgets.data_api ({source: daily cap}). usage keys:
    token_age_days, last_used_days, youtube_used_units, planned_inserts, data_api_used/planned."""
    hooks = {
        "free_space": lambda: free_space_gate(
            data_root, min_free_gb=cfg["gc"]["min_free_gb"]),
        "host_health": lambda: host_health_gate(
            comfy_url=cfg["hosts"]["comfy_url"], ollama_url=cfg["hosts"]["ollama_url"],
            get=http_get),
        "oauth": lambda: oauth_token_age_gate(
            token_age_days=usage["token_age_days"], last_used_days=usage["last_used_days"],
            mode=cfg["oauth_mode"]),
        "youtube_quota": lambda: youtube_quota_gate(
            used_units=usage["youtube_used_units"], planned_inserts=usage["planned_inserts"],
            daily_quota=cfg["budgets"]["youtube_units"]),
        "data_budget": lambda: data_api_budget_gate(
            used=usage["data_api_used"], planned=usage["data_api_planned"],
            budgets=cfg["budgets"]["data_api"]),
    }
    gates = build_preflight(hooks=hooks)

    def run() -> None:
        for g in gates:
            g()
    return run


def metered(run_stage, *, batch_id: str, textfile_dir: Path,
            baselines: dict[str, float] | None = None, slow_factor: float = 1.5):
    """Wrap the M4 run_stage (run_stage_subprocess+retries): after each stage call, write the
    per-stage series to the node-exporter textfile dir — incl. the shorts_stage_slow gauge the
    StageSlow alert reads (was-it-slow record: elapsed > p95*slow_factor when a baseline exists,
    0 otherwise). execute_batch stays pure — metrics emission lives ONLY in this wrapper."""
    textfile_dir = Path(textfile_dir)

    def wrapped(video_id: str, stage_id: str):
        out = run_stage(video_id, stage_id)
        base = (baselines or {}).get(stage_id)
        slow = 1 if base and out.elapsed_s > base * slow_factor else 0
        lbl = f'batch="{batch_id}",stage="{stage_id}",video="{video_id}"'
        write_metrics(
            textfile_dir / f"{video_id}-{stage_id}.prom",
            render_stage_metrics(batch_id=batch_id, stage=stage_id, video_id=video_id,
                                 duration_s=out.elapsed_s, status=out.status, running=0,
                                 heartbeat_ts=int(time.time()))
            + f"shorts_stage_slow{{{lbl}}} {slow}\n")
        return out
    return wrapped


def _age_days(p: Path, now: float) -> float:
    return (now - p.stat().st_mtime) / 86400


def _rmtree_guarded(data_root: Path, path: Path) -> None:
    """Defense-in-depth around shutil.rmtree: only ever under data_root, never a PROTECTED tree
    (history/models) — a bad scan must crash loudly, not reclaim unrecoverable state."""
    root = Path(data_root).resolve()
    p = Path(path).resolve()
    if not p.is_relative_to(root) or any(part in PROTECTED for part in p.relative_to(root).parts):
        raise ValueError(f"refusing to GC outside data_root or a protected tree: {p}")
    shutil.rmtree(p, ignore_errors=True)


def post_batch_sweep(data_root: Path, *, batch_id: str, resumed_ids: set[str], cfg: dict,
                     outcomes: dict[str, str], niche: str, textfile_dir: Path) -> dict:
    """Runs after backup() (ADR 0003 D8/D9): GC runs/ (keep_days/keep_count, never the active or
    reconciler-resumed batch), quarantine/ (quarantine_keep_days), and the .cache LRU (cap_gb),
    then emit the batch-level series the alerts read. All knobs from cfg["gc"] — the gc-module
    defaults are documentation only."""
    data_root = Path(data_root)
    gc = cfg["gc"]
    now = time.time()
    deleted: list[str] = []

    runs = [{"id": p.name, "age_days": _age_days(p, now), "path": p}
            for p in sorted((data_root / "runs").glob("*")) if p.is_dir()]
    for r in runs_to_delete(runs, keep_days=gc["keep_days"], keep_count=gc["keep_count"],
                            protected_ids={batch_id} | set(resumed_ids)):
        _rmtree_guarded(data_root, r["path"])
        deleted.append(str(r["path"]))

    quarantines = [{"id": p.name, "age_days": _age_days(p, now), "path": p}
                   for p in sorted((data_root / "quarantine").glob("*")) if p.is_dir()]
    for q in quarantine_to_delete(quarantines, keep_days=gc["quarantine_keep_days"]):
        _rmtree_guarded(data_root, q["path"])
        deleted.append(str(q["path"]))

    cache_entries = [{"key": f"{p.parent.name}/{p.name}", "atime": p.stat().st_atime, "path": p,
                      "size_gb": sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e9}
                     for p in sorted((data_root / ".cache").glob("*/*")) if p.is_dir()]
    for e in evict_to_cap(cache_entries, cap_gb=gc["cap_gb"]):
        _rmtree_guarded(data_root, e["path"])
        deleted.append(str(e["path"]))

    statuses = list(outcomes.values())
    window = cfg.get("obs", {}).get("quarantine_window", 20)
    write_metrics(
        Path(textfile_dir) / f"batch-{batch_id}.prom",
        render_batch_metrics(batch_id=batch_id, niche=niche, videos_total=len(statuses),
                             quarantined=statuses.count("quarantined"),
                             failed=statuses.count("failed"),
                             quarantine_rate=trailing_rate(statuses, window=window),
                             # the pre-batch trailing baseline (everything before this window);
                             # 0.0 on cold start — is_spike's strict > never false-alarms on it
                             quarantine_baseline=trailing_rate(statuses[:-window],
                                                               window=window)))
    return {"deleted": deleted}


def _build_backends(*, data_root: Path) -> dict:
    """The on-box bring-up seam (M6 Task 12 runbook), exactly as M4 left it: resolves the config
    layers (ADR 0014), the day's usage counters (OAuth token age, YouTube units, data-API calls),
    and the real collaborators — plan=resume_plan-or-plan_batch (per_niche ramp knob, default 1);
    run_stage=run_stage_subprocess+retries over stage_cmd with per-stage timeouts; persist=write
    batch.json (temp+rename); commit=commit_ledgers (novelty + feature_record); backup=one rsync
    of history/*.jsonl + credentials (spec Ch.8). Each collaborator is the tested unit above."""
    raise NotImplementedError(
        "production backend wiring lands with the on-box bring-up runbook (M6 Task 12)")


def main() -> int:
    import os
    data_root = Path(os.environ.get("DATA_ROOT", "/data/shorts"))
    b = _build_backends(data_root=data_root)   # the documented NotImplementedError seam
    cfg, batch_id = b["cfg"], b["batch_id"]
    textfile_dir = data_root / ".metrics" / "textfile"
    outcomes: dict[str, str] = {}

    def execute(batch: dict) -> None:
        from shared.conductor.executor import default_stage_order, execute_batch
        outcomes.update(execute_batch(
            batch, stage_order=default_stage_order(),
            run_stage=metered(b["run_stage"], batch_id=batch_id, textfile_dir=textfile_dir,
                              baselines=b.get("baselines")),
            persist=b["persist"]))

    batch_flow(lock_path=data_root / ".batch.lock", data_root=data_root,
               preflight=production_preflight(cfg=cfg, data_root=data_root, usage=b["usage"]),
               plan=b["plan"], execute=execute, commit=b["commit"], backup=b["backup"])
    post_batch_sweep(data_root, batch_id=batch_id, resumed_ids=b.get("resumed_ids", set()),
                     cfg=cfg, outcomes=outcomes, niche=cfg["niche"], textfile_dir=textfile_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
