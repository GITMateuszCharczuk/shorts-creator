import pytest

from shared.layout.finishing import (
    CutRateError,
    assert_cut_rate,
    build_thumb_cmd,
    color_match_args,
    inject_finishing,
)


def _manifest():
    return {"fps": 30, "markers": {}, "scenes": [
        {"start": 0.0, "end": 2.0, "kind": "hook", "regions": []},
        {"start": 2.0, "end": 4.0, "kind": "item", "regions": []}]}


def test_end_card_injected_on_final_scene_with_platform_verb_and_loop_flag():
    m = inject_finishing(_manifest(), brand_kit={"end_card_phrases": ["Follow or you miss it"]},
                         seed=7, platform="youtube")
    last = m["scenes"][-1]
    card = next(r for r in last["regions"] if r["name"] == "end_card")
    assert "Subscribe" in card["value"]            # platform verb swap (ADR 0006 D8)
    assert m["markers"]["end_card"] == 60          # 2.0s * 30fps
    assert m["loop"]["bridge"] is True             # seamless loop (ADR 0006 D5)


def test_thumb_cmd_grabs_hook_frame():
    cmd = build_thumb_cmd(render="renders/youtube.mp4", out="thumbnail.jpg")
    s = " ".join(cmd)
    assert "-frames:v 1" in s and s.endswith("thumbnail.jpg")   # frame 1 = the designed cover


def test_color_match_args_pulls_toward_target():
    args = color_match_args(clip_mean=80.0, target_mean=120.0)
    assert "eq=brightness=" in args                # per-clip matching BEFORE the grade (D4)


def test_cut_rate_guard():
    assert_cut_rate(_manifest(), max_scene_s=4.0)  # ok
    slow = {"fps": 30, "scenes": [{"start": 0.0, "end": 9.0, "kind": "item", "regions": []}]}
    with pytest.raises(CutRateError):
        assert_cut_rate(slow, max_scene_s=4.0)     # the no-slideshow target (ADR 0005 D4)


def test_end_card_verb_fallback_when_phrase_lacks_slot():
    m = inject_finishing(_manifest(), brand_kit={"end_card_phrases": ["Don't miss out"]},
                         seed=7, platform="youtube")
    card = next(r for r in m["scenes"][-1]["regions"] if r["name"] == "end_card")
    assert "Subscribe" in card["value"]
