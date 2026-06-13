from shared.adapters.base import DistributionAdapter


class YouTubeAdapter(DistributionAdapter):
    """YouTube Data API v3 videos.insert. The altered/synthetic-content label has NO public API
    field (Studio-UI only as of 2026 — see deploy/host/oauth-production.md); disclosure rides in the
    DESCRIPTION line. _find_existing uses the uploads playlist (near-real-time, 1 unit) — NOT
    search.list, whose index lags minutes-to-hours and would risk a blind double-post (ADR 0003)."""
    platform = "youtube"

    def __init__(self, creds, *, insert=None, list_uploads=None):
        self._creds = creds
        self._insert = insert
        self._list_uploads = list_uploads

    def allowed_visibility(self, cfg):
        return {"private", "unlisted", "public"}

    def public_label(self):
        return "public"

    def private_label(self):
        return "private"

    def _insert_body(self, metadata, visibility):
        return {"snippet": {"title": metadata["title"], "description": metadata["description"],
                            "categoryId": "25"},
                "status": {"privacyStatus": visibility, "selfDeclaredMadeForKids": False}}

    def _post(self, media_path, metadata, visibility):
        # MediaFileUpload + videos().insert; injected so units stay offline and live runs are real.
        resp = self._insert(self._insert_body(metadata, visibility), media_path)
        return resp["id"], f"https://youtu.be/{resp['id']}"

    def _find_existing(self, idempotency_key):
        if self._list_uploads is None:
            return None
        hit = self._list_uploads(idempotency_key)        # playlistItems.list(uploads); desc marker
        return (hit["id"], f"https://youtu.be/{hit['id']}") if hit else None
