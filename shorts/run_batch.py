"""python -m shorts.run_batch — the nightly conductor entrypoint (ADR 0015)."""
import json
import shutil
import time
from pathlib import Path
from typing import Callable

from shared.conductor.ledger import commit_ledgers
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
from shared.planner.batch import build_job, plan_batch


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
    supplies all five. An UNKNOWN key is a typo (e.g. "oauht") that would silently no-op a real
    gate — fail loudly instead."""
    known = {"free_space", "host_health", "oauth", "youtube_quota", "data_budget"}
    unknown = hooks.keys() - known
    if unknown:
        raise ValueError(
            f"unknown preflight hook key(s): {sorted(unknown)} (known: {sorted(known)})")
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
        # The in-flight running=1 gauge is emitted each tick by the stage subprocess's Heartbeat
        # (shorts/stage.py) into this SAME <video>-<stage>.prom; this post-completion write
        # (running=0 + duration/status) is the authoritative final overwrite.
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
    (history/models), never data_root itself, and never THROUGH a symlink (run/quarantine/cache
    dirs are real dirs — a symlink in a GC scan is suspicious, and resolve() would otherwise
    launder its target into an apparently-safe path) — a bad scan must crash loudly, not reclaim
    unrecoverable state."""
    if Path(path).is_symlink():
        raise ValueError(f"refusing to GC a symlink: {path}")
    root = Path(data_root).resolve()
    p = Path(path).resolve()
    if p == root:
        raise ValueError(f"refusing to GC data_root itself: {p}")
    if not p.is_relative_to(root) or any(part in PROTECTED for part in p.relative_to(root).parts):
        raise ValueError(f"refusing to GC outside data_root or a protected tree: {p}")
    shutil.rmtree(p, ignore_errors=True)


def load_outcome_history(data_root: Path, *, niche: str | None = None) -> list[str]:
    """Per-video terminal statuses across PRIOR batches, oldest-first, from history/batches.jsonl
    (one {"video_id","niche","batch_id","status"} line per video, appended by post_batch_sweep —
    history/ is PROTECTED so GC never reclaims it). Tolerant by design: a missing file returns []
    (cold start) and malformed/short lines are skipped, never crash the sweep."""
    path = Path(data_root) / "history" / "batches.jsonl"
    if not path.exists():
        return []
    statuses: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict) or "status" not in rec:
            continue
        if niche is not None and rec.get("niche") != niche:
            continue
        statuses.append(rec["status"])
    return statuses


def _tolerant_records(path: Path) -> list[dict]:
    """Read a posts.jsonl WITHOUT the ledger's fail-loud LedgerCorruption (read_records raises on a
    malformed line). The fan-in must survive a torn write mid-crash and pre-existing forensic
    garbage — skip any line that isn't a JSON dict, never crash. Forensic bytes are read-only here;
    callers never rewrite the file they read from."""
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def merge_posts_to_history(data_root: Path, run_dirs: list[Path]) -> int:
    """M6 fan-in (ADR 0003 D6): merge each run dir's per-video posts.jsonl into the durable
    history/posts.jsonl that shorts/audit.py reads. Only CONFIRMED records cross over (intent/
    publishing are crash-recovery state, not durable posts). Dedupe on (video_id, platform) — NOT
    video_id alone like commit_ledgers, which would over-dedupe a video posted to two platforms and
    silently drop the second. Tolerant of missing dirs/files and malformed lines on both sides; the
    history file's existing (possibly corrupt) bytes are APPENDED to, never rewritten. Idempotent:
    a resumed batch re-merging the same run dirs appends nothing. Returns the count appended."""
    data_root = Path(data_root)
    history = data_root / "history" / "posts.jsonl"
    seen = {(r["video_id"], r["platform"]) for r in _tolerant_records(history)
            if "video_id" in r and "platform" in r}
    new: list[dict] = []
    for run_dir in run_dirs:
        for rec in _tolerant_records(Path(run_dir) / "posts.jsonl"):
            if rec.get("state") != "confirmed":
                continue
            key = (rec.get("video_id"), rec.get("platform"))
            if None in key or key in seen:
                continue
            seen.add(key)
            new.append(rec)
    if new:
        history.parent.mkdir(parents=True, exist_ok=True)
        with history.open("a") as f:
            for rec in new:
                f.write(json.dumps(rec) + "\n")
    return len(new)


def historical_baseline(history_outcomes: list[str], *, window: int) -> float:
    """The QuarantineSpike baseline: the trailing quarantine rate over CROSS-BATCH history (the
    last `window` outcomes that landed BEFORE this batch). Computing it from the current batch's
    own pre-window slice is degenerate — any real batch is smaller than the window, so the slice
    is always empty -> 0.0 -> the rate > 2*baseline alert arm fires on ANY nonzero quarantine.
    [] (no history yet) -> 0.0, and is_spike's strict > keeps the cold start alarm-free."""
    return trailing_rate(history_outcomes, window=window)


def post_batch_sweep(data_root: Path, *, batch_id: str, resumed_ids: set[str], cfg: dict,
                     outcomes_by_niche: dict[str, dict[str, str]], textfile_dir: Path) -> dict:
    """Runs after backup() (ADR 0003 D8/D9): GC runs/ (keep_days/keep_count, never the active or
    reconciler-resumed batch), quarantine/ (quarantine_keep_days), the .cache LRU (cap_gb), and
    stale per-stage .prom files (keep_days), then emit the batch-level series the alerts read —
    ONE render_batch_metrics block PER NICHE (outcomes_by_niche: niche -> {video_id: status};
    the QuarantineSpike alert is per-niche via labels), all blocks in ONE atomic write so a
    scrape never sees a half-written file. The per-niche baseline comes from cross-batch history
    (historical_baseline over load_outcome_history), read BEFORE this batch's outcomes are
    appended to history/batches.jsonl for the next batch. All knobs from cfg["gc"] — the
    gc-module defaults are documentation only."""
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

    # Stale per-stage .prom files (metered writes one per video-stage): unlink past keep_days so
    # the textfile dir doesn't grow unbounded — but NEVER the batch file written just below.
    batch_prom = Path(textfile_dir) / f"batch-{batch_id}.prom"
    for prom in sorted(Path(textfile_dir).glob("*.prom")):
        if prom != batch_prom and _age_days(prom, now) > gc.get("keep_days", 7):
            prom.unlink(missing_ok=True)
            deleted.append(str(prom))

    window = cfg.get("obs", {}).get("quarantine_window", 20)
    blocks: list[str] = []
    for niche in sorted(outcomes_by_niche):
        statuses = list(outcomes_by_niche[niche].values())
        blocks.append(render_batch_metrics(
            batch_id=batch_id, niche=niche, videos_total=len(statuses),
            quarantined=statuses.count("quarantined"), failed=statuses.count("failed"),
            quarantine_rate=trailing_rate(statuses, window=window),
            quarantine_baseline=historical_baseline(
                load_outcome_history(data_root, niche=niche), window=window)))
    write_metrics(batch_prom, "".join(blocks))

    # Append this batch's outcomes so the NEXT batch has a real baseline. commit_ledgers is
    # idempotent on video_id — a reconciler-resumed batch never double-counts.
    entries = [{"video_id": vid, "niche": niche, "batch_id": batch_id, "status": status}
               for niche, vids in outcomes_by_niche.items() for vid, status in vids.items()]
    if entries:
        (data_root / "history").mkdir(parents=True, exist_ok=True)
        commit_ledgers(data_root / "history" / "batches.jsonl", entries)
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


def plan_only(*, data_root: Path, cfg: dict) -> dict:
    """M7 Variant B (ADR 0015a D1): the Argo CronWorkflow's `plan` step. PLAN-ONLY — no stages,
    no real backends (no GPU/LLM), so it must NOT go through the `_build_backends` bring-up seam.
    It resolves the batch_id, calls plan_batch over its CONFIG-SOURCED planner inputs, writes the
    planner's artifacts to the PVC, and emits the planned video_ids so Argo's `withParam` fan-out
    can instantiate the per-video WorkflowTemplate once per id.

    The planner inputs (niches/per_niche/formats/topic_candidates/lane_history/ledger_topics/
    monetization_share/master_seed/series_due) are taken from `cfg` — this is the CONFIG-SOURCED
    contract. In production the conductor sources these from the resolved config layers + the day's
    fresh topics behind `_build_backends` (the on-box bring-up seam, M6 Task 12); plan-only takes
    the SAME shape from a resolved-config dict so it is runnable with no cluster/GPU. cfg keys:
      batch_id, niches, per_niche, formats, topic_candidates, lane_history, ledger_topics,
      monetization_share, master_seed, series_due (optional), platform_targets (optional).

    Side effects on the PVC (read by the dual-mode stage CLI's resolve_argo_args + by Argo):
      - runs/<batch_id>/batch.json            — the canonical plan (what resolve_argo_args reads)
      - runs/<batch_id>/<video_id>/job.json   — the per-video job incl. the resolved profile (05b)
      - runs/<batch_id>/video_ids.json        — the planned ids as a JSON array
      - runs/<batch_id>/batch_id.txt          — the resolved batch_id (one line)
      - runs/latest/video_ids.json            — STABLE well-known copy for Argo outputs.parameters
      - runs/latest/batch_id.txt              — STABLE well-known copy (the dynamic batch_id source)

    Argo capture: file-based (robust — no stdout parsing). The CronWorkflow's `plan` step reads
    runs/latest/{video_ids.json,batch_id.txt} via outputs.parameters[].valueFrom.path. We also
    PRINT the id list as a JSON array on stdout's last line for ad-hoc/manual capture.
    Returns the plan dict.
    """
    data_root = Path(data_root)
    batch_id = cfg["batch_id"]
    batch = plan_batch(
        batch_id=batch_id,
        niches=cfg["niches"],
        per_niche=cfg.get("per_niche", 1),
        formats=cfg["formats"],
        lane_history=cfg.get("lane_history", []),
        topic_candidates=cfg["topic_candidates"],
        ledger_topics=set(cfg.get("ledger_topics", set())),
        monetization_share=cfg["monetization_share"],
        master_seed=cfg["master_seed"],
        series_due=cfg.get("series_due"),
    )

    run_dir = data_root / "runs" / batch_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(run_dir / "batch.json", json.dumps(batch, indent=2) + "\n")

    platform_targets = cfg.get("platform_targets")
    profiles_root = cfg.get("profiles_root")
    video_ids: list[str] = []
    for video in batch["videos"]:
        job = build_job(video, batch_id=batch_id, platform_targets=platform_targets,
                        profiles_root=Path(profiles_root) if profiles_root else None)
        vdir = run_dir / video["video_id"]
        vdir.mkdir(parents=True, exist_ok=True)
        _atomic_write(vdir / "job.json", json.dumps(job, indent=2) + "\n")
        video_ids.append(video["video_id"])

    ids_json = json.dumps(video_ids)
    _atomic_write(run_dir / "video_ids.json", ids_json + "\n")
    _atomic_write(run_dir / "batch_id.txt", batch_id + "\n")
    # Stable well-known path so Argo's outputs.parameters.valueFrom.path is fixed (the batch_id is
    # dynamic — Argo can't template a per-run output path), and the fanout learns the real batch_id.
    latest = data_root / "runs" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    _atomic_write(latest / "video_ids.json", ids_json + "\n")
    _atomic_write(latest / "batch_id.txt", batch_id + "\n")

    # stdout's last line is the JSON array (ad-hoc capture; the CronWorkflow uses the file path).
    print(ids_json)
    return batch


def _atomic_write(path: Path, text: str) -> None:
    """Temp+rename so a concurrent reader (resolve_argo_args / Argo's artifact reader) never sees a
    half-written file — the same durability discipline the conductor's persist hook uses."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    import os
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os
    p = argparse.ArgumentParser(prog="python -m shorts.run_batch")
    # M7 Variant B: plan WITHOUT running stages or needing real backends (no GPU/LLM). The Argo
    # CronWorkflow's `plan` step calls this; the `withParam` fan-out consumes the planned ids.
    p.add_argument("--plan-only", action="store_true",
                   help="plan the batch + write batch.json/job.json/video_ids.json, run no stages")
    p.add_argument("--config",
                   help="path to a JSON file with the resolved planner inputs for --plan-only")
    a = p.parse_args(argv)

    data_root = Path(os.environ.get("DATA_ROOT", "/data/shorts"))

    if a.plan_only:
        # CONFIG-SOURCED planner inputs. In production the conductor resolves these from the config
        # layers (ADR 0014) + the day's fresh topics behind `_build_backends` (the on-box bring-up
        # seam, M6 Task 12); the BRING-UP CONTRACT is that the same resolved-config shape is handed
        # to plan_only — via --config <file> here, or a generated ConfigMap in the cluster. We do
        # NOT fabricate planner inputs: --config (or PLAN_CONFIG env) MUST supply them.
        cfg_path = a.config or os.environ.get("PLAN_CONFIG")
        if not cfg_path:
            p.error("--plan-only requires --config <file.json> (or PLAN_CONFIG env): the resolved "
                    "planner inputs are config-sourced at bring-up, never fabricated")
        cfg = json.loads(Path(cfg_path).read_text())
        plan_only(data_root=data_root, cfg=cfg)
        return 0

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

    batch = batch_flow(
        lock_path=data_root / ".batch.lock", data_root=data_root,
        preflight=production_preflight(cfg=cfg, data_root=data_root, usage=b["usage"]),
        plan=b["plan"], execute=execute, commit=b["commit"], backup=b["backup"])
    # Per-niche tally for the sweep: plan videos carry their niche (shared/planner/batch.py) —
    # a batch spans niches, and the QuarantineSpike alert is per-niche via labels.
    niche_of = {v["video_id"]: v.get("niche", "unknown") for v in (batch or {}).get("videos", [])}
    outcomes_by_niche: dict[str, dict[str, str]] = {}
    for vid, status in outcomes.items():
        outcomes_by_niche.setdefault(niche_of.get(vid, "unknown"), {})[vid] = status
    # Fan the per-video posts.jsonl ledgers into the durable history before the sweep GCs run dirs —
    # otherwise audit reports zero posts and a reclaimed run dir loses the confirmed-post record.
    run_dirs = [data_root / "runs" / batch_id / v["video_id"]
                for v in (batch or {}).get("videos", [])]
    merge_posts_to_history(data_root, run_dirs)
    post_batch_sweep(data_root, batch_id=batch_id, resumed_ids=b.get("resumed_ids", set()),
                     cfg=cfg, outcomes_by_niche=outcomes_by_niche, textfile_dir=textfile_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
