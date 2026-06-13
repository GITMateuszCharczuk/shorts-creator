import random
import re
from pathlib import Path

from shared.planner.lanes import next_lane
from shared.planner.rotation import NoFormatError, pick_format
from shared.planner.topics import claim_topics
from shared.profiles.loader import load_profile

_PROFILES_ROOT = Path(__file__).resolve().parents[2] / "profiles"


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
                try:
                    fmt = pick_format(
                        formats, lane=lane, recent=recent_formats[-3:],
                        seed=rng.randint(0, 2**31),
                    )
                except NoFormatError as e:
                    # name the slot — a bare starvation deep in the loop is undebuggable
                    raise NoFormatError(f"{e} (niche={niche}, slot={k})") from e
            videos.append({"video_id": f"{niche}-{batch_id}-{k}", "niche": niche,
                           "format": fmt["id"], "lane": lane, "topic": topics[len(videos)],
                           "seed": rng.randint(0, 2**31), "status": "pending"})
            history.append(lane)
            recent_formats.append(fmt["id"])
    return {"schema_version": "1.0.0", "batch_id": batch_id,
            "monetization_share": monetization_share, "videos": videos}


def build_job(video: dict, *, batch_id: str, platform_targets: list[str] | None = None,
              profiles_root: Path | None = None) -> dict:
    """Author the per-video job.json the fan-out runner consumes (ADR 0010 D5/0012): the resolved
    profile dict 05b reads (job["profile"]["defaults"]["disclaimer"/"denylist_terms"]) is injected
    HERE — no production code authored it before, so the first real run would KeyError. stages/paths
    start empty: each stage owns its own section. An unknown niche (a profiles_root without its
    profile.yaml) fails LOUD with the niche named — a silently-missing profile is a safety hole."""
    niche = video["niche"]
    # niche indexes a filesystem path (profiles/<niche>/profile.yaml); a separator or `..` could
    # escape profiles_root, so constrain it to a slug before any path construction.
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", niche):
        raise ValueError(f"invalid niche {niche!r}")
    root = Path(profiles_root) if profiles_root is not None else _PROFILES_ROOT
    profile_path = root / niche / "profile.yaml"
    if not profile_path.exists():
        raise ValueError(f"no profile for niche {niche!r} at {profile_path}")
    profile = load_profile(profile_path)
    return {"schema_version": "1.0.0", "batch_id": batch_id, "video_id": video["video_id"],
            "niche": niche, "seed": video["seed"],
            # an explicit empty list is a config error, not an implicit YouTube publish — only a
            # missing (None) value falls back to the default target.
            "platform_targets": ["youtube"] if platform_targets is None else platform_targets,
            "profile": profile, "stages": {}, "paths": {}}
