from shared.finance.normalize import normalize

# closed prosody vocabulary -> per-segment params (rate multiplier, trailing pause seconds)
_PROSODY = {"emphatic": (0.9, 0.35), "rising": (1.05, 0.15), "measured": (1.0, 0.2),
            "fast": (1.15, 0.1), "pause": (1.0, 0.5)}


def speech_segments(script: dict) -> list[dict]:
    """One synth segment per narration beat: normalized text + rate + trailing pause from prosody,
    with rate further modulated by the treatment's energy curve (ADR 0017 D7) so the read has
    DYNAMICS (build/peak/land), not a flat line. Pure + deterministic (energy is in the script)."""
    curve = script.get("treatment", {}).get("energy_curve", [])
    segs = []
    for i, b in enumerate(script.get("narration_beats", [])):
        rate, pause = _PROSODY.get(b.get("prosody", "measured"), (1.0, 0.2))
        energy = curve[i] if i < len(curve) else 0.5         # 0..1; 0.5 = neutral
        rate *= 0.9 + 0.2 * energy                           # high-energy beats read faster
        segs.append({"text": normalize(b.get("text", "")), "rate": round(rate, 3),
                     "pause_after": pause, "emphasis": b.get("emphasis", []),
                     "energy": energy})                    # 04 reads this for duck depth/intensity
    return segs
