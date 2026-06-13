from shared.distribution.visibility import resolve_visibility


class _YT:
    platform = "youtube"
    def allowed_visibility(self, cfg): return {"private", "public"}
    def public_label(self): return "public"
    def private_label(self): return "private"


class _TT:
    platform = "tiktok"
    def allowed_visibility(self, cfg): return {"SELF_ONLY", "PUBLIC_TO_EVERYONE"}
    def public_label(self): return "PUBLIC_TO_EVERYONE"
    def private_label(self): return "SELF_ONLY"


def test_youtube_public_after_warming_tiktok_audit_gated():
    cfg = {"youtube": {"public_after_warming": True}, "tiktok": {"audit_cleared": False}}
    assert resolve_visibility(_YT(), cfg, warmed=True) == "public"
    assert resolve_visibility(_YT(), cfg, warmed=False) == "private"
    assert resolve_visibility(_TT(), cfg, warmed=True) == "SELF_ONLY"     # audit not cleared


def test_tiktok_public_once_audit_cleared():
    assert resolve_visibility(_TT(), {"tiktok": {"audit_cleared": True}}, warmed=True) \
        == "PUBLIC_TO_EVERYONE"


def test_resolution_never_returns_a_value_outside_the_allowed_set():
    cfg = {"youtube": {"public_after_warming": True}}
    assert resolve_visibility(_YT(), cfg, warmed=True) in _YT().allowed_visibility(cfg)
