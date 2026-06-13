def resolve_visibility(adapter, cfg: dict, *, warmed: bool) -> str:
    """Resolve a platform's privacy string from config, generic over the adapter (ADR 0010 D3).

    No per-platform equality branches: a platform goes public only when ITS configured gate is
    satisfied, and which gate applies is data-driven off the per-platform config keys —
      * audit-gated  (key ``audit_cleared`` present): public iff the audit has cleared;
      * warming-gated (otherwise): public iff warmed and ``public_after_warming``.
    The privacy strings live on the adapter (public_label/private_label), so YouTube's
    public/private and TikTok's PUBLIC_TO_EVERYONE/SELF_ONLY never leak in here.
    The chosen value is asserted inside allowed_visibility(), so a config typo fails loud."""
    pcfg = cfg.get(adapter.platform, {})
    public = adapter.public_label() if hasattr(adapter, "public_label") else "public"
    private = adapter.private_label() if hasattr(adapter, "private_label") else "private"
    if "audit_cleared" in pcfg:
        go_public = bool(pcfg["audit_cleared"])
    else:
        go_public = warmed and bool(pcfg.get("public_after_warming"))
    chosen = public if go_public else private
    allowed = adapter.allowed_visibility(cfg)
    # NOT an assert: assertions are stripped under `python -O`, which would let a config typo
    # silently post at an invalid (potentially public) visibility. Fail loud unconditionally.
    if chosen not in allowed:
        raise ValueError(f"{chosen} not in {adapter.platform} allowed {allowed}")
    return chosen
