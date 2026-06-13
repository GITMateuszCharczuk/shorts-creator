def build_caption(meta: dict, *, platform: str, disclosure_line: str,
                  affiliate: dict | None) -> dict:
    kw, body = meta["primary_keyword"], meta.get("description", "")
    lead = body if body.lower().startswith(kw.lower()) else f"{kw} — {body}"
    parts = [lead, "", " ".join(f"#{h}" for h in meta.get("hashtags", [])), "", disclosure_line]
    if affiliate:
        parts += ["", affiliate["text"], *affiliate.get("links", [])]
    return {"title": meta["title"], "description": "\n".join(p for p in parts if p)}
