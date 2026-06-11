import json

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
    text = spoken_text(script)
    if not text.strip():
        ctx.quarantine("empty narration text — nothing to synthesize")
    wav = ctx.backend("tts").tts(text)  # KokoroBackend writes narration.wav
    out = ctx.write_output("narration")
    if wav.resolve() != out.resolve():  # resolve: a symlink/relative alias must not self-clobber
        out.write_bytes(wav.read_bytes())
    ctx.log.info("narration synthesized", chars=len(text))
    return StageResult(outputs={"narration": out})
