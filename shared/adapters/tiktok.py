from shared.adapters.base import DistributionAdapter


class TikTokAdapter(DistributionAdapter):
    """TikTok Content Posting API. The AIGC disclosure goes in post_info.aigc_content (NOT
    source_info). Publish is ASYNC: init -> upload -> poll /publish/status/fetch/; _post returns
    only after PUBLISH_COMPLETE so a 'confirmed' record means actually-published (ADR 0003)."""
    platform = "tiktok"
    _PRIVACY = {"SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"}

    def __init__(self, token, *, init=None, upload=None, poll=None, find=None):
        self._token = token
        self._init = init
        self._upload = upload
        self._poll = poll
        self._find = find

    def allowed_visibility(self, cfg):
        return set(self._PRIVACY)

    def public_label(self):
        return "PUBLIC_TO_EVERYONE"

    def private_label(self):
        return "SELF_ONLY"

    def _init_body(self, metadata, visibility):
        return {"post_info": {"title": metadata["title"], "privacy_level": visibility,
                              "brand_content_toggle": False, "aigc_content": True},
                "source_info": {"source": "FILE_UPLOAD"}}

    def _post(self, media_path, metadata, visibility):
        publish_id = self._init(self._init_body(metadata, visibility), media_path)
        # H3: persist the publish_id BEFORE upload/poll. A crash after init but before confirm now
        # leaves a 'publishing' record carrying the publish_id for recovery to re-poll (the
        # publish_id IS the marker — TikTok has no search-by-marker, see _find_existing).
        self._record_publishing(publish_id)
        self._upload(publish_id, media_path)
        status = self._poll(publish_id)                  # blocks until PUBLISH_COMPLETE or raises
        if status != "PUBLISH_COMPLETE":
            raise RuntimeError(f"TikTok publish {publish_id} ended {status}")
        return publish_id, f"https://tiktok.com/@me/video/{publish_id}"

    def _find_existing(self, idempotency_key):
        # injected recovery hook: host wiring re-polls the publish_id stored in the ledger's
        # publishing record (TikTok has no search-by-marker; the publish_id IS the marker).
        return self._find(idempotency_key) if self._find else None
