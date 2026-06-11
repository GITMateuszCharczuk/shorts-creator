def pending_review(videos: list[dict], decided: dict[str, bool]) -> list[str]:
    """Passed BOTH gates and no human decision yet. A gate failure is already quarantined —
    never queued."""
    return [v["video_id"] for v in videos
            if v.get("qc_pass") and v.get("creative_pass") and v["video_id"] not in decided]
