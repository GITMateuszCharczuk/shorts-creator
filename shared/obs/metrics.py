import os
from pathlib import Path


def render_stage_metrics(
    *, batch_id, stage, video_id, duration_s, status, running, heartbeat_ts
) -> str:
    lbl = f'batch="{batch_id}",stage="{stage}",video="{video_id}"'
    return (
        f"shorts_stage_duration_seconds{{{lbl}}} {duration_s}\n"
        f'shorts_stage_status{{{lbl},status="{status}"}} 1\n'
        f"shorts_stage_running{{{lbl}}} {running}\n"
        f"shorts_stage_heartbeat_timestamp{{{lbl}}} {heartbeat_ts}\n"
    )


def render_batch_metrics(
    *, batch_id, niche, videos_total, quarantined, failed, quarantine_rate, quarantine_baseline
) -> str:
    lbl = f'batch="{batch_id}",niche="{niche}"'
    return (
        f"shorts_batch_videos_total{{{lbl}}} {videos_total}\n"
        f"shorts_batch_quarantined_total{{{lbl}}} {quarantined}\n"
        f"shorts_batch_failed_total{{{lbl}}} {failed}\n"
        f"shorts_quarantine_rate{{{lbl}}} {quarantine_rate}\n"
        f"shorts_quarantine_baseline{{{lbl}}} {quarantine_baseline}\n"
    )


def write_metrics(path: Path, text: str) -> None:
    """Atomic write into the node-exporter textfile-collector dir (temp+rename so a scrape never
    reads a half-written file, ADR 0003 D7)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"{path}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
