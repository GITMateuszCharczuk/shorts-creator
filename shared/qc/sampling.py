def sample_frames(manifest: dict, total_frames: int, cap: int = 8) -> list[int]:
    """Hook (0), end-card (last), manifest markers, + one mid-frame per scene; deduped, capped.

    The hook and end-card frames ALWAYS survive the cap — 05x's kind mapping (hook/end_card)
    is the contract M5's 05b consumes (review-driven fix: the plan's [:cap] could drop the
    end-card when truncating).
    """
    fps = manifest["fps"]
    idx = {0, total_frames - 1}
    idx.update(int(v) for v in manifest.get("markers", {}).values())
    for s in manifest.get("scenes", []):
        if s["end"] < s["start"]:
            continue   # an inverted span must not inject a nonsense frame index
        idx.add(int(((s["start"] + s["end"]) / 2) * fps))
    ordered = sorted(i for i in idx if 0 <= i < total_frames)
    if len(ordered) <= cap:
        return ordered
    # keep hook + end-card + evenly-spaced middle picks (middle capped to cap-2 so the
    # endpoints can never be truncated away)
    step = max(1, (len(ordered) - 2) // (cap - 2))
    middle = ordered[1:-1:step][:cap - 2]
    return sorted({ordered[0], ordered[-1], *middle})
