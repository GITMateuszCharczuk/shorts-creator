import json
import shutil
import subprocess
from pathlib import Path

from shared.ctx import StageContext, StageResult
from shared.layout.encode import build_nvenc_cmd
from shared.layout.remotion import render_manifest_to_frames
from shared.layout.resolve import resolve
from shared.layout.schema_load import load_layout
from shared.stage import StageManifest, stage


def platform_delta(manifest: dict, platform: str) -> dict:
    m = json.loads(json.dumps(manifest))  # deep copy
    verb = {"youtube": "Subscribe", "tiktok": "Follow"}.get(platform, "Follow")
    m.setdefault("cta", {})["verb"] = verb
    for scene in m.get("scenes", []):                  # retarget the injected CTABump verb (D10)
        for r in scene.get("regions", []):
            if r.get("name") == "cta_bump":
                r["primitive"].setdefault("params", {})["verb"] = verb
    return m


def _encode(*, frames_glob: str, audio: Path, fps: int, out: Path) -> None:
    r = subprocess.run(
        build_nvenc_cmd(frames_glob=frames_glob, audio=audio, fps=fps, out=out),
        capture_output=True, text=True)
    if r.returncode != 0:
        # surface the ffmpeg stderr tail — a bare CalledProcessError gives the conductor nothing
        raise RuntimeError(f"nvenc encode failed (exit {r.returncode}):\n{r.stderr[-2000:]}")


@stage(StageManifest(id="05", inputs=["script", "assets", "captions",
                                      "word_timings", "music", "data"],
                     outputs=["render"], compute="cpu"))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    layout = load_layout(ctx.run_dir / f"formats/{script['format']}/layout.json")
    words = json.loads(ctx.read_input("word_timings").read_text())  # declared input (no bypass)
    assets = json.loads(ctx.read_input("assets").read_text())
    brand_kit = json.loads(
        (ctx.run_dir / ctx.config.get("brand_kit", "brand_kit.json")).read_text())
    beat_data = {"beats": _beats_from_script(script)}  # the typed per-beat data 00b emitted
    media = {i: s["clip_path"] for i, s in enumerate(assets["scenes"])}  # beat -> CHOSEN asset
    if len(media) < len(beat_data["beats"]):
        # an asset under-delivery renders the brand-dark fallback — visible in QC, but log it
        ctx.log.warning("fewer assets than beats", assets=len(media),
                        beats=len(beat_data["beats"]))
    out = ctx.write_output("render")                   # primary cut: renders/youtube.mp4
    primary = None
    for plat in ctx.job.get("platform_targets", ["youtube"]):   # a REAL cut per platform target
        manifest = resolve(layout=layout, beat_data=beat_data, brand_kit=brand_kit,
                           timings=_scene_spans(words, beat_data), seed=ctx.seed,
                           safe_rect=_safe_rect(plat, ctx.config),   # per-platform reflow (D4)
                           media=media, words=words)
        cut = out if plat == "youtube" else out.parent / f"{plat}.mp4"
        if primary is None:   # persist the PRIMARY cut's manifest for 05x keyframe sampling —
            # the per-platform workdir copy is rmtree'd right after encode
            (ctx.run_dir / "render_manifest.json").write_text(
                json.dumps(manifest, sort_keys=True))
        workdir = out.parent / plat
        frames = render_manifest_to_frames(platform_delta(manifest, plat), workdir)
        _encode(frames_glob=str(frames[0].parent / "%05d.png"),
                audio=ctx.read_input("music"),   # the 04 duck+loudnorm MIX
                fps=30, out=cut)
        shutil.rmtree(workdir)    # frames are ~10 GB/cut — delete immediately after encode
        primary = primary or cut
        ctx.log.info("cut rendered", scenes=len(manifest["scenes"]), platform=plat)
    return StageResult(outputs={"render": primary})


def _beats_from_script(script: dict) -> list[dict]:
    ld = script["layout_data"]
    if ld["kind"] == "ranked_list":
        return [{"kind": "item", "item": it} for it in ld["items"]]
    # head_to_head: one "round" beat per round (sides + that round's metrics), then a "verdict"
    # beat — so the beat_pattern arc is real and vs_badge/stat_bars (on:[round]) and verdict
    # (on:[verdict]) render on their own beats (ADR 0007a §7b).
    beats = [{"kind": "round", "side_a": ld["side_a"], "side_b": ld["side_b"], "round": rnd}
             for rnd in ld["round"]]
    beats.append({"kind": "verdict", "side_a": ld["side_a"], "side_b": ld["side_b"],
                  "verdict": ld["verdict"]})
    return beats


def _scene_spans(words: list[dict], beat_data: dict) -> list[dict]:
    # word-timed cuts (ADR 0007a §2): partition words into n contiguous groups; each scene
    # spans its group's first->last word — NOT a flat division.
    n = len(beat_data["beats"])
    if n == 0:
        return []   # resolve() pairs beats with timings; zero beats -> zero spans (no crash)
    k, m = divmod(len(words), n)
    spans, idx = [], 0
    for s in range(n):
        size = k + (1 if s < m else 0)
        grp = words[idx:idx + size]
        idx += size
        spans.append({"start": grp[0]["start"], "end": grp[-1]["end"]} if grp
                     else {"start": 0.0, "end": 0.0})
    return spans


def _safe_rect(platform: str, config: dict) -> dict:
    # per-platform safe insets reflow the SAME layout (the load-bearing per-platform delta).
    insets = {"youtube": {"top": 0.06, "bottom": 0.10}, "tiktok": {"top": 0.08, "bottom": 0.16}}
    p = insets.get(platform, {"top": 0.06, "bottom": 0.12})
    return {"x": 0, "y": int(1920 * p["top"]), "w": 1080,
            "h": int(1920 * (1 - p["top"] - p["bottom"]))}
