import json

from shared.captions.ass import build_ass
from shared.ctx import StageContext, StageResult
from shared.stage import StageManifest, stage


def tag_emphasis(aligned: list[dict], emphasis_words: set[str]) -> list[dict]:
    ew = {w.lower() for w in emphasis_words}

    def hit(word: str) -> bool:
        w = word.lower()
        # match the raw token first (so "3.2%" / "$1.5m" punch words match), then a
        # sentence-punctuation-stripped form — but never strip % or $ (they carry meaning).
        return w in ew or w.strip(".,!?") in ew

    # .get: WhisperX can emit silence segments without a "word" key
    return [{**w, "emphasis": hit(w.get("word", ""))} for w in aligned]


@stage(StageManifest(
    id="03",
    inputs=["script", "narration"],
    outputs=["captions", "word_timings"],
    compute="cpu",
))
def run(ctx: StageContext) -> StageResult:
    script = json.loads(ctx.read_input("script").read_text())
    script_text = " ".join(b.get("text", "") for b in script.get("narration_beats", []))
    aligned = _align_to_script(ctx.read_input("narration"), script_text)  # WhisperX, integration
    emphasis = {w for c in script.get("captions", []) for w in c.get("emphasis", [])}
    words = tag_emphasis(aligned, emphasis)
    ass = build_ass(
        words,
        max_words=int(ctx.config.get("caption_max_words", 4)),
        font=ctx.config.get("brand_font", "Inter"),
        emphasis_hex=ctx.config.get("emphasis_hex", "00E5FF"),
        safe_bottom_pct=int(ctx.config.get("safe_bottom_pct", 18)),
    )
    out = ctx.write_output("captions")
    out.write_text(ass)
    wt = ctx.write_output("word_timings")  # word-level timings consumed by Stage 05 (M2 compositor)
    wt.write_text(json.dumps(words))
    ctx.log.info("captions built", lines=ass.count("Dialogue:"))
    return StageResult(outputs={"captions": out, "word_timings": wt})


def _align_to_script(narration_wav, script_text: str) -> list[dict]:
    import whisperx  # noqa: F401  # host-only
    _model = whisperx.load_align_model(language_code="en", device="cpu")
    # forced alignment of the KNOWN text to audio -> word timings (not transcription)
    raise NotImplementedError(
        "WhisperX alignment wired at integration bring-up; "
        "unit tests use tests/fixtures/m1/aligned_words.json"
    )
