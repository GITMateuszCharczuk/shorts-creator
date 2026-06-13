def resume_plan(batch: dict) -> list[str]:
    """Boot-time reconciliation (ADR 0003 D9): a host reboot mid-batch leaves videos in
    running/pending; re-running them is SAFE because stages are seeded + idempotent and the
    content-addressed cache skips completed work (ADR 0009/0010).
    held videos are also re-queued — they re-run stage 06 which is an exactly-once no-op for
    already-confirmed posts; the review CLI controls whether approved is set before the re-run."""
    return [v["video_id"] for v in batch["videos"] if v["status"] in ("running", "pending", "held")]
