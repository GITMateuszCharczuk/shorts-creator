import json
from pathlib import Path

import numpy as np
import soundfile as sf

from shared.ctx import StageContext
from shared.schema import SchemaRegistry
from shared.timing import StageTimer
from stages.s00a_research.stage import run as run_00a
from stages.s00b_script.stage import run as run_00b
from stages.s02_voice.stage import run as run_02
from stages.s03_subs.stage import run as run_03
from stages.s05_render.stage import run as run_05

REG = SchemaRegistry()


class _FakeLLM:
    def __init__(self, script_path):
        self._s = json.loads(Path(script_path).read_text())

    def llm(self, prompt, seed=None):
        return "0.88" if "Score" in prompt else json.dumps(self._s)

    def llm_json(self, prompt, seed=None):
        return dict(self._s)


class _FakeTTS:
    def __init__(self, out):
        self._out = out

    def tts(self, text):
        p = self._out / "narration.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(p, np.zeros(24000 * 3, dtype="float32"), 24000)
        return p


def run_m1_slice(*, run_dir: Path, seed: int, fixtures: Path, timing_log: Path) -> dict:
    # seed inputs
    (run_dir / "data.json").write_text((fixtures / "data.json").read_text())
    (run_dir / "aligned_words.json").write_text((fixtures / "aligned_words.json").read_text())
    assets = {
        "schema_version": "1.0.0",
        "scenes": [
            {"beat_id": "b1", "clip_path": "s1.png", "duration": 2.0},
            {"beat_id": "b2", "clip_path": "s2.png", "duration": 2.0},
        ],
    }
    (run_dir / "assets.json").write_text(json.dumps(assets))
    for img in ("s1.png", "s2.png", "logo.png"):
        _solid_png(run_dir / img)

    def ctx(stage, inp, outp, backends):
        return StageContext(
            stage=stage,
            run_dir=run_dir,
            seed=seed,
            job={"seed": seed, "video_id": "fin-0001"},
            config={"data_fixture": "data.json", "best_of_n": 1},
            input_paths=inp,
            output_paths=outp,
            backends=backends,
        )

    def _p(result):  # normalize stage outputs to run-dir-relative names (closure: needs run_dir)
        return {name: str(p.relative_to(run_dir)) for name, p in result.outputs.items()}

    produced = {}
    fake_llm = _FakeLLM(fixtures / "ollama_responses" / "script.json")
    with StageTimer("00a", timing_log):
        produced.update(_p(run_00a(ctx("00a", {}, {"data": "data.json"}, {}))))
    with StageTimer("00b", timing_log):
        produced.update(
            _p(
                run_00b(
                    ctx(
                        "00b",
                        {"data": "data.json"},
                        {"script": "script.json"},
                        {"llm": fake_llm},
                    )
                )
            )
        )
    REG.validate("script", json.loads((run_dir / "script.json").read_text()))
    with StageTimer("02", timing_log):
        produced.update(
            _p(
                run_02(
                    ctx(
                        "02",
                        {"script": "script.json"},
                        {"narration": "narration.wav"},
                        {"tts": _FakeTTS(run_dir)},
                    )
                )
            )
        )
    with StageTimer("03", timing_log):
        import stages.s03_subs.stage as s03

        orig = s03._align_to_script
        try:
            s03._align_to_script = lambda wav, txt: json.loads(
                (run_dir / "aligned_words.json").read_text()
            )
            produced.update(
                _p(
                    run_03(
                        ctx(
                            "03",
                            {"script": "script.json", "narration": "narration.wav"},
                            {"captions": "captions.ass", "word_timings": "word_timings.json"},
                            {},
                        )
                    )
                )
            )
        finally:
            s03._align_to_script = orig
    with StageTimer("05", timing_log):
        produced.update(
            _p(
                run_05(
                    ctx(
                        "05",
                        {
                            "script": "script.json",
                            "assets": "assets.json",
                            "narration": "narration.wav",
                            "captions": "captions.ass",
                        },
                        {"render": "renders/youtube.mp4"},
                        {},
                    )
                )
            )
        )
    return produced


def _solid_png(path: Path):
    from PIL import Image

    Image.new("RGB", (1080, 1920), (12, 30, 18)).save(path)
