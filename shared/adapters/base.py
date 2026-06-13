from abc import ABC, abstractmethod
from pathlib import Path

from shared.distribution.posts_ledger import (
    already_confirmed,
    idempotency_key,
    pending_post,
    write_confirmed,
    write_intent,
    write_publishing,
)


class UnresolvedPendingPost(Exception):
    """A prior attempt left an intent/publishing record but no findable remote post (C1).

    Blind-reposting here risks a duplicate PUBLIC post for a video that may already be live, so we
    refuse and surface this for a human or a bounded retry to resolve (e.g. wait for the YouTube
    uploads playlist / TikTok publish status to settle, or confirm the post truly never landed)."""


class DistributionAdapter(ABC):
    """Exactly-once is OWNED HERE (ADR 0003 D1/0010). publish() writes to the PER-VIDEO ledger;
    the shared history/posts.jsonl is shorts.run_batch.merge_posts_to_history's job (the M6 fan-in,
    ADR 0003 D6). A retry recovers via
    _find_existing — never a blind re-post.

    This is THE distribution contract: the M0 ``shared.adapters.protocols.DistributionAdapter``
    Protocol it briefly coexisted with was retired in Task 13 (the fixture fake now subclasses
    this ABC like the real YouTube/TikTok adapters do)."""
    platform: str

    def publish(self, *, video_id, media_path, metadata, visibility,
                ledger_path: Path) -> dict | None:
        if already_confirmed(ledger_path, video_id, self.platform):
            return None
        # The idempotency key is derived INTERNALLY (C1) — never trusted from caller metadata. A
        # wrong/missing metadata["idempotency_key"] would silently defeat crash-recovery, so the
        # ledger and the _find_existing lookup both use this canonical key. For YouTube this same
        # key must be embedded in the upload DESCRIPTION at bring-up so _find_existing can match it
        # against the uploads playlist (see youtube.py).
        key = idempotency_key(video_id, self.platform)
        if pending_post(ledger_path, video_id, self.platform):
            found = self._find_existing(key)                            # crash-recovery
            if found:
                rid, url = found
                write_confirmed(ledger_path, video_id=video_id, platform=self.platform,
                                remote_id=rid, url=url)
                return {"remote_id": rid, "url": url, "recovered": True}
            # C1: pending intent/publishing but NO findable remote post. Do NOT blind-repost — the
            # video may already be live and unfindable only transiently. Refuse and escalate.
            raise UnresolvedPendingPost(
                f"{self.platform}:{video_id} is pending but no remote post was found via "
                f"_find_existing({key!r}); refusing to blind re-post (resolve manually/retry)")
        write_intent(ledger_path, video_id=video_id, platform=self.platform)
        # The derived key is exposed to _post so an adapter can embed it where its own
        # _find_existing will later search for it (YouTube: the description marker).
        self._idempotency_key = key
        # H3: persist the real remote_id in a 'publishing' record BEFORE confirming. For an async
        # adapter (TikTok) the id is the init publish_id; _post reports it the moment it is known
        # via _record_publishing so a crash after init/before confirm leaves a re-pollable id. For
        # a synchronous adapter (YouTube) _post returns the id directly and we record it below.
        self._ledger_path = ledger_path
        self._publishing_video_id = video_id
        self._publishing_recorded = False
        rid, url = self._post(media_path, metadata, visibility)    # side effect (live-verified)
        if not self._publishing_recorded:
            self._record_publishing(rid)
        write_confirmed(ledger_path, video_id=video_id, platform=self.platform,
                        remote_id=rid, url=url)
        return {"remote_id": rid, "url": url, "recovered": False}

    def _record_publishing(self, remote_id: str) -> None:
        """Persist a 'publishing' ledger record with the real remote_id (H3).

        Adapters whose first side-effecting step yields the id before completion (TikTok's init
        publish_id) MUST call this from _post right after that step, so a crash before confirm
        leaves a re-pollable id. The synchronous path calls it automatically once _post returns."""
        write_publishing(self._ledger_path, video_id=self._publishing_video_id,
                         platform=self.platform, remote_id=remote_id)
        self._publishing_recorded = True

    @abstractmethod
    def allowed_visibility(self, cfg: dict) -> set[str]: ...
    @abstractmethod
    def _post(self, media_path, metadata: dict, visibility: str) -> tuple[str, str]: ...
    @abstractmethod
    def _find_existing(self, idempotency_key: str) -> tuple[str, str] | None: ...
