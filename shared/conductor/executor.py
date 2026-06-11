from typing import Callable

from shared.conductor.subproc import StageOutcome

# The ADR 0011 lanes; GPU members take GPU_LOCK inside run_stage (stage-batched per stage id).
VISUAL_LANE = ["01a", "01b", "01c", "01d", "01e"]
AUDIO_LANE = ["02", "03", "04"]


class SystemicFailure(Exception):
    """Consecutive failures across videos within ONE stage — the host-down pattern, not
    per-video bad luck (ADR 0003 D4): halt the batch instead of failing N videos."""


def execute_batch(batch: dict, *, stage_order: list[str],
                  run_stage: Callable[[str, str], StageOutcome],
                  persist: Callable[[dict], None] | None = None,
                  max_consecutive_failures: int = 3) -> dict[str, str]:
    """Stage-batched execution (stage-major = GPU-swap-minimizing, ADR 0011) with per-video
    failure domains. Statuses are WRITTEN THROUGH to the batch dict and flushed via `persist`
    after every change — the boot reconciler (ADR 0003 D9) reads batch.json, so an unpersisted
    status would re-run quarantined videos after a reboot."""
    videos = {v["video_id"]: v for v in batch["videos"]}
    for v in videos.values():
        if v["status"] == "pending":
            v["status"] = "running"
    if persist:
        persist(batch)
    for stage_id in stage_order:
        consecutive_failed = 0
        for vid, v in videos.items():
            # NOTE: spec had ("quarantined", "failed") here — that omits "done", which would
            # cause already-completed videos to be re-run (plan bug). Fixed to include "done"
            # so boot-reconciler resume semantics are correct: a video that reached "done" in
            # a prior run (and was not reset to "pending") is never re-executed.
            if v["status"] in ("quarantined", "failed", "done"):
                continue                            # the video's domain is closed
            out = run_stage(vid, stage_id)
            if out.status == "failed":
                consecutive_failed += 1
                if consecutive_failed >= max_consecutive_failures:
                    v["status"] = "failed"
                    if persist:
                        persist(batch)
                    raise SystemicFailure(
                        f"{consecutive_failed} consecutive failures at stage {stage_id} — "
                        f"halting the batch (host-down pattern, ADR 0003 D4)")
            else:
                consecutive_failed = 0              # interleaved success = per-video, not systemic
            if out.status != "done":
                v["status"] = out.status
                if persist:
                    persist(batch)
    for v in videos.values():
        if v["status"] == "running":
            v["status"] = "done"
    if persist:
        persist(batch)
    return {vid: v["status"] for vid, v in videos.items()}

# Lane-fork note (ADR 0011, behind the timing metric): when `concurrency.lanes` is enabled in
# config, the conductor runs VISUAL_LANE and AUDIO_LANE in two ThreadPoolExecutor workers per
# video between 00b and 05 — each worker calling this same run_stage (subprocesses do the work;
# GPU stages serialize on GPU_LOCK). Per-video CPU fan-out (the spec M4 row's second ADR 0011
# lever) uses the same pool: within a CPU stage, the inner video loop submits subprocesses
# concurrently (concurrency.fanout: N); GPU stages are exempt (the lock). Both levers default
# OFF until the M1 timing baseline justifies them; all paths share the per-video-domain +
# write-through rules. The conductor calls confirm_vram (Task 7) before each GPU stage's video
# sweep — the confirm-evicted gate (ADR 0015 D5).
