"""Expressive-voice A/B harness (ADR 0017 D1) — `make voice-ab`, host-only, never run in CI.

Synthesizes a FIXED reference script (hook + 3 beats with emphatic/rising prosody) through each
candidate TTS backend into runs/.voice_ab/<backend>.wav. The operator scores hook delivery,
emphasis landing, naturalness, and per-segment rate control; the winner goes to the profile's
defaults.voice_backend (a config swap, ADR 0010). A backend whose deps are absent prints SKIP.
"""
from pathlib import Path

from shared.adapters.real import ChatterboxBackend, KokoroBackend, OrpheusBackend
from shared.audio.prosody import speech_segments

_OUT = Path("runs") / ".voice_ab"
_BACKENDS = {"kokoro": KokoroBackend, "orpheus": OrpheusBackend, "chatterbox": ChatterboxBackend}


def reference_script() -> dict:
    """The fixed A/B reference: a hook + 3 beats exercising emphatic/rising prosody so every
    candidate is judged on the SAME hook delivery, emphasis landings, and rate changes."""
    return {
        "narration_beats": [
            {"text": "Ninety percent of investors get this completely wrong.",
             "prosody": "emphatic", "emphasis": ["completely wrong"]},
            {"text": "And the data says it costs them 1.5% every single year.",
             "prosody": "rising", "emphasis": ["1.5%"]},
            {"text": "Here is the part nobody talks about.",
             "prosody": "emphatic", "emphasis": ["nobody"]},
            {"text": "Fixing it takes one account setting.",
             "prosody": "rising", "emphasis": ["one"]},
        ],
        "treatment": {"energy_curve": [0.9, 0.5, 0.7, 1.0]},  # peak the hook, build to the land
    }


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    segments = speech_segments(reference_script())
    for name, cls in _BACKENDS.items():
        dst = _OUT / f"{name}.wav"
        try:
            wav = cls(out_dir=_OUT / name).tts_segments(segments)
            if wav.resolve() != dst.resolve():
                dst.write_bytes(wav.read_bytes())
            print(f"OK   {name}: {dst}")
        except Exception as e:  # deps absent / unwired backend -> SKIP, keep scoring the rest
            print(f"SKIP {name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
