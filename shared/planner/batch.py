import random

from shared.planner.lanes import next_lane
from shared.planner.rotation import pick_format
from shared.planner.topics import claim_topics


def plan_batch(*, batch_id: str, niches: list[str], per_niche: int, formats: list[dict],
               lane_history: list[str], topic_candidates: list[str], ledger_topics: set[str],
               monetization_share: float, master_seed: int,
               series_due: dict[str, dict] | None = None) -> dict:
    """The conductor's pre-fan-out brain (ADR 0015 D6): SERIES-DUE slots first (ADR 0017 D5) ->
    lane mix -> format rotation -> topic reservation -> per-video seeds. Pure + deterministic."""
    rng = random.Random(master_seed)
    series_due = series_due or {}                     # {niche: {"format":…, "lane":…}} due today
    n_total = len(niches) * per_niche
    topics = claim_topics(topic_candidates, ledger_topics=ledger_topics, n=n_total)
    videos, history, recent_formats = [], list(lane_history), []
    for niche in niches:
        for k in range(per_niche):
            if k == 0 and niche in series_due:        # the recurring-series slot, fixed format/lane
                s = series_due[niche]
                lane, fmt = s["lane"], {"id": s["format"]}
            else:
                lane = next_lane(history, monetization_share=monetization_share)
                fmt = pick_format(
                    formats, lane=lane, recent=recent_formats[-3:],
                    seed=rng.randint(0, 2**31),
                )
            videos.append({"video_id": f"{niche}-{batch_id}-{k}", "niche": niche,
                           "format": fmt["id"], "lane": lane, "topic": topics[len(videos)],
                           "seed": rng.randint(0, 2**31), "status": "pending"})
            history.append(lane)
            recent_formats.append(fmt["id"])
    return {"schema_version": "1.0.0", "batch_id": batch_id,
            "monetization_share": monetization_share, "videos": videos}
