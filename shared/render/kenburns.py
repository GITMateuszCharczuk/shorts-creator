def zoompan_expr(*, zoom_start: float, zoom_end: float, frames: int) -> str:
    # linear zoom from start->end across `frames`; centered. ffmpeg zoompan expression.
    # zoompan initialises zoom at 1.0, so a zoom-OUT (end < start) needs max() to clamp at the
    # END value — min() would clamp the wrong direction and the pan would undershoot immediately.
    step = (zoom_end - zoom_start) / max(frames - 1, 1)
    clamp = "min" if zoom_end >= zoom_start else "max"
    # NB: no trailing comment — ffmpeg filtergraph syntax has no `#` comments.
    return (
        f"zoompan=z='{clamp}(zoom+{step:.6f},{zoom_end})':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
    )
