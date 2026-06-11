def group_words(words: list[dict], max_words: int) -> list[list[dict]]:
    return [words[i:i + max_words] for i in range(0, len(words), max_words)]


def _ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


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
    lines = []
    for group in group_words(words, max_words):
        start, end = group[0]["start"], group[-1]["end"]
        text = " ".join(
            (f"{{\\c&H{emphasis_hex}&}}{w['word']}{{\\c&HFFFFFF&}}" if w.get("emphasis")
             else w["word"])
            for w in group
        )
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Base,{text}")
    return header + "\n".join(lines) + "\n"
