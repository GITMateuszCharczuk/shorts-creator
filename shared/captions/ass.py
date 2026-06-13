def group_words(words: list[dict], max_words: int) -> list[list[dict]]:
    return [words[i:i + max_words] for i in range(0, len(words), max_words)]


def _ts(sec: float) -> str:
    # Round in CENTISECOND space, then divmod: %05.2f would round 59.999 -> "60.00", an illegal
    # ASS seconds value that libass parses wrong or drops the line on. Rounding cs first makes
    # the carry propagate (59.999 -> 0:01:00.00) and avoids float-floor undershoot (2.07 -> 02.06).
    cs = round(sec * 100)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _bgr(rgb_hex: str) -> str:
    """ASS colours are &HBBGGRR (BGR). Callers pass natural RGB hex; swap R<->B here."""
    r, g, b = rgb_hex[0:2], rgb_hex[2:4], rgb_hex[4:6]
    return f"{b}{g}{r}"


def _clean(word: str) -> str:
    # braces open ASS override blocks; a "{...}" in transcript text would inject styling tags
    return word.replace("{", "").replace("}", "")


def build_ass(words: list[dict], *, max_words: int, font: str, emphasis_hex: str,
              safe_bottom_pct: int) -> str:
    margin_v = int(1920 * safe_bottom_pct / 100)  # 9:16 @ 1080x1920
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Outline, Shadow, Alignment, MarginV\n"
        f"Style: Base,{font},72,&H00FFFFFF,&H00000000,&H64000000,1,4,2,2,{margin_v}\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    emphasis_bgr = _bgr(emphasis_hex)
    lines = []
    for group in group_words(words, max_words):
        start, end = group[0]["start"], group[-1]["end"]
        text = " ".join(
            # {\r} resets to the STYLE colour (not a hardcoded white) so M3 brand kits inherit
            (f"{{\\c&H{emphasis_bgr}&}}{_clean(w['word'])}{{\\r}}" if w.get("emphasis")
             else _clean(w["word"]))
            for w in group
        )
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Base,{text}")
    return header + "\n".join(lines) + "\n"
