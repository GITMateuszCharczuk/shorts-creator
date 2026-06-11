from shared.render.kenburns import zoompan_expr


def test_zoompan_scales_within_bounds():
    expr = zoompan_expr(zoom_start=1.0, zoom_end=1.12, frames=90)
    assert expr.startswith("zoompan=") and "1.12" in expr and "d=90" in expr
    assert "#" not in expr   # no comment — would be an ffmpeg filtergraph parse error
