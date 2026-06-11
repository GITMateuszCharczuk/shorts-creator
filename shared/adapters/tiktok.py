from shared.adapters.base import DistributionAdapter


class TikTokAdapter(DistributionAdapter):
    """TikTok Content Posting API. The AIGC disclosure goes in post_info.aigc_content (NOT
    source_info). Publish is ASYNC: init -> upload -> poll /publish/status/fetch/; _post returns
    only after PUBLISH_COMPLETE so a 'confirmed' record means actually-published (ADR 0003)."""
    platform = "tiktok"
    _PRIVACY = {"SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"}

    def __init__(self, token, *, init=None, upload=None, poll=None):
        self._token = token
        self._init = init
        self._upload = upload
        self._poll = poll

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
        self._upload(publish_id, media_path)
        status = self._poll(publish_id)                  # blocks until PUBLISH_COMPLETE or raises
        if status != "PUBLISH_COMPLETE":
            raise RuntimeError(f"TikTok publish {publish_id} ended {status}")
        return publish_id, f"https://tiktok.com/@me/video/{publish_id}"

    def _find_existing(self, idempotency_key):
        # the intent/publishing record stored the publish_id; recovery re-polls its terminal status.
        if self._poll is None:
            return None
        pub = self._poll_by_marker(idempotency_key) if hasattr(self, "_poll_by_marker") else None
        return (pub, f"https://tiktok.com/@me/video/{pub}") if pub else None
