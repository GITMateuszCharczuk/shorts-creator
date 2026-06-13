from abc import ABC, abstractmethod
from pathlib import Path

from shared.distribution.posts_ledger import (
    already_confirmed,
    pending_post,
    write_confirmed,
    write_intent,
)


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
        if pending_post(ledger_path, video_id, self.platform):
            found = self._find_existing(metadata["idempotency_key"])    # crash-recovery
            if found:
                rid, url = found
                write_confirmed(ledger_path, video_id=video_id, platform=self.platform,
                                remote_id=rid, url=url)
                return {"remote_id": rid, "url": url, "recovered": True}
        else:
            write_intent(ledger_path, video_id=video_id, platform=self.platform)
        rid, url = self._post(media_path, metadata, visibility)    # side effect (live-verified)
        write_confirmed(ledger_path, video_id=video_id, platform=self.platform,
                        remote_id=rid, url=url)
        return {"remote_id": rid, "url": url, "recovered": False}

    @abstractmethod
    def allowed_visibility(self, cfg: dict) -> set[str]: ...
    @abstractmethod
    def _post(self, media_path, metadata: dict, visibility: str) -> tuple[str, str]: ...
    @abstractmethod
    def _find_existing(self, idempotency_key: str) -> tuple[str, str] | None: ...
