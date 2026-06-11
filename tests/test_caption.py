from shared.distribution.caption import build_caption


def test_caption_is_keyword_first_with_disclosure():
    meta = {"title": "Rate cuts explained", "description": "The Fed just moved.",
            "hashtags": ["finance"], "primary_keyword": "interest rates"}
    cap = build_caption(meta, platform="youtube", disclosure_line="AI-generated. Educational only.",
                        affiliate=None)
    assert cap["description"][:150].lower().startswith("interest rates")
    assert "AI-generated" in cap["description"]


def test_affiliate_block_only_when_enabled():
    meta = {"title": "t", "description": "d", "hashtags": [], "primary_keyword": "k"}
    off = build_caption(meta, platform="youtube", disclosure_line="x", affiliate=None)
    on = build_caption(meta, platform="youtube", disclosure_line="x",
                       affiliate={"text": "Tools I use:", "links": ["https://ex.com/a"]})
    assert "Tools I use" not in off["description"] and "Tools I use" in on["description"]
