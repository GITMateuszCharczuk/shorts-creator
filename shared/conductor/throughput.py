from collections import defaultdict


class ThroughputBust(Exception):
    """The projected batch exceeds the overnight window — the unattended DoD rests on this
    number (spec Ch.10 open #9; deferred across ADRs 0005-0008, settled HERE)."""


def project_batch(timings: list[dict], *, n_videos: int, window_hours: float,
                  raise_on_bust: bool = False) -> dict:
    """Roll per-stage means (from timing.jsonl, M1 StageTimer + M2 compositor_mspf) into a
    serial per-video cost and project the batch against the window. Lane-fork overlap (ADR
    0011) only IMPROVES on this serial projection — so a serial fit is a sufficient gate."""
    by_stage: dict[str, list[float]] = defaultdict(list)
    for t in timings:
        by_stage[t["stage"]].append(t["elapsed_s"])
    per_video = sum(sum(v) / len(v) for v in by_stage.values())
    batch_s = per_video * n_videos
    fits = batch_s <= window_hours * 3600
    report = {"per_video_s": round(per_video, 1), "batch_s": round(batch_s, 1),
              "window_s": window_hours * 3600, "fits": fits,
              "by_stage": {k: round(sum(v) / len(v), 1) for k, v in by_stage.items()}}
    if raise_on_bust and not fits:
        raise ThroughputBust(str(report))
    return report
