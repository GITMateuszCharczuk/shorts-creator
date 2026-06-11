def sample_frames(manifest: dict, total_frames: int, cap: int = 8) -> list[int]:
    """Hook (0), end-card (last), manifest markers, + one mid-frame per scene; deduped, capped."""
    fps = manifest["fps"]
    idx = {0, total_frames - 1}
    idx.update(int(v) for v in manifest.get("markers", {}).values())
    for s in manifest.get("scenes", []):
        idx.add(int(((s["start"] + s["end"]) / 2) * fps))
    ordered = sorted(i for i in idx if 0 <= i < total_frames)
    if len(ordered) <= cap:
        return ordered
    # keep hook + end-card + evenly-spaced middle picks
    keep = {ordered[0], ordered[-1]}
    step = max(1, (len(ordered) - 2) // (cap - 2))
    keep.update(ordered[1:-1:step])
    return sorted(keep)[:cap]
