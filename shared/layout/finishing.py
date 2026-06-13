class CutRateError(Exception):
    """A scene exceeds the visual-change-rate target (the slideshow tell, ADR 0005 D4)."""


def inject_finishing(manifest: dict, *, brand_kit: dict, seed: int, platform: str) -> dict:
    """ADR 0006 D5/D8: the closing end-card is OVERLAID on the final beat (no dead air appended,
    so it cannot defeat the loop bridge) + the loop flag the engine uses to trim/crossfade the
    tail back into frame 0."""
    verb = {"youtube": "Subscribe", "tiktok": "Follow"}.get(platform, "Follow")
    phrases = brand_kit.get("end_card_phrases",
                            ["Follow — the algorithm only shows us once"])
    phrase = phrases[seed % len(phrases)].replace("Follow", verb, 1)
    if verb not in phrase:   # a phrase without the "Follow" slot still gets the platform CTA verb
        phrase = f"{phrase} — {verb}"
    last = manifest["scenes"][-1]
    last["regions"].append({
        "name": "end_card", "primitive": {"type": "TextCard", "params": {"role": "display"}},
        "rect": {"x": 90, "y": 1340, "w": 900, "h": 300}, "z": 9,
        "enter": "riser_reveal", "exit": "none", "value": phrase,
        "style": brand_kit.get("styles", {}).get("brand.end_card", {})})
    manifest["markers"]["end_card"] = round(last["start"] * manifest["fps"])
    manifest["loop"] = {"bridge": True}
    return manifest


def build_thumb_cmd(*, render: str, out: str) -> list[str]:
    # hook frame = frame 1 = the designed pattern-interrupt (TikTok cover, ADR 0005 D3)
    return ["ffmpeg", "-y", "-i", str(render), "-vf", "select=eq(n\\,0),scale=1080:1920",
            "-frames:v", "1", str(out)]


def color_match_args(*, clip_mean: float, target_mean: float) -> str:
    """Per-clip exposure matching toward the batch median BEFORE the global grade (ADR 0005 D4 —
    a blanket LUT over mismatched exposures fixes nothing)."""
    delta = max(-0.3, min(0.3, (target_mean - clip_mean) / 255.0))
    return f"eq=brightness={delta:.3f}"


def assert_cut_rate(manifest: dict, *, max_scene_s: float = 4.0) -> None:
    for s in manifest["scenes"]:
        dur = s["end"] - s["start"]
        # lower bound: a zero/negative-duration scene (e.g. _scene_spans on words=[]) renders
        # 0 frames in Remotion — it must fail loud here, not slip past to the engine (M).
        if dur <= 0:
            raise CutRateError(f"scene {s.get('kind')} has non-positive duration "
                               f"{dur:.3f}s ({s['start']}->{s['end']}) — would render 0 frames")
        if dur > max_scene_s:
            raise CutRateError(f"scene {s.get('kind')} runs {dur:.1f}s "
                               f"> {max_scene_s}s — add a cut or media change")
