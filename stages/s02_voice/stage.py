import json

from shared.audio.prosody import speech_segments
from shared.ctx import StageContext, StageResult
from shared.finance.normalize import normalize
from shared.stage import StageManifest, stage


def spoken_text(script: dict) -> str:
    beats = [normalize(b.get("text", "")) for b in script.get("narration_beats", [])]
    return " ".join(beats)


def keyword_in_opening(script: dict, window_beats: int = 1) -> bool:
    # ADR 0006: the primary keyword should be SPOKEN in the opening lines (discoverability).
    kw = (script.get("primary_keyword") or "").lower()   # explicit JSON null -> "" not a crash
    if not kw:
        return False
    opening = " ".join(
        b.get("text", "") for b in script.get("narration_beats", [])[:window_beats]
    ).lower()
    return kw in opening


@stage(
    StageManifest(
        id="02", inputs=["script"], outputs=["narration"], compute="cpu", capability="tts"
    )
)
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    if not keyword_in_opening(script):
        ctx.log.warning(
            "primary keyword not in opening lines", keyword=script.get("primary_keyword")
        )
    joined = spoken_text(script)
    if not joined.strip():
        ctx.quarantine("empty narration text — nothing to synthesize")
    # per-beat prosody drives the voice (ADR 0005 D6): one segment per beat, each at its own
    # rate + trailing pause; the backend synthesizes and concatenates into narration.wav.
    segments = speech_segments(script)
    wav = ctx.backend("tts").tts_segments(segments)
    out = ctx.write_output("narration")
    if wav.resolve() != out.resolve():  # resolve: a symlink/relative alias must not self-clobber
        out.write_bytes(wav.read_bytes())
    ctx.log.info("narration synthesized", chars=len(joined), segments=len(segments))
    return StageResult(outputs={"narration": out})
