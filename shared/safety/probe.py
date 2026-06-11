from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    """The 05b measurement contract. Field names match the check signatures exactly so the
    integration probe (ffprobe/loudnorm/luma + render_manifest read) can't silently drift."""
    integrated_lufs: float           # ffmpeg -af loudnorm=print_format=json (input_i)
    true_peak_dbtp: float            # loudnorm input_tp
    silences: list                   # ffmpeg silencedetect -> [(start_s, end_s)]
    black_spans: list                # ffprobe/blackdetect -> [(start_s, end_s)] (luma < 16/255)
    actual_s: float                  # ffprobe format.duration of renders/youtube.mp4
    projected_s: float               # script's projected runtime (sum of segment durations)
    cta_rect: dict                   # the end_card region from render_manifest.json (x,y,w,h)


def probe(run_dir: Path, *, narration, music, render, render_manifest) -> ProbeResult:
    raise NotImplementedError(
        "Integration seam: run loudnorm on `music` (the final mix), silencedetect on `narration`, "
        "blackdetect + duration on `render`, and read the end_card rect from `render_manifest`. "
        "CI uses a fixture ProbeResult; the pure checks (Tasks 3-4) are unit-tested.")
