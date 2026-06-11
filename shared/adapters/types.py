from dataclasses import dataclass
from enum import Enum


class Visibility(str, Enum):
    PRIVATE = "private"
    SELF_ONLY = "self_only"
    PUBLIC = "public"


@dataclass(frozen=True)
class PostMeta:
    title: str
    description: str
    hashtags: tuple[str, ...]
    visibility: Visibility


@dataclass(frozen=True)
class PostReceipt:
    video_id: str
    platform: str
    remote_post_id: str
    visibility: Visibility


@dataclass(frozen=True)
class Judgment:
    overall: float
    scores: dict[str, float]
    passed: bool
    # per-pass VLM observations (ADR 0016 D5); verdicts stay in the gates, not here
    observations: tuple[str, ...] = ()
