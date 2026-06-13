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

    def tts_segments(self, segments):
        return self.tts("")


def run_m1_slice(*, run_dir: Path, seed: int, fixtures: Path, timing_log: Path) -> dict:
    repo = Path(__file__).resolve().parents[2]
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
    for img in ("s1.png", "s2.png"):
        _solid_png(run_dir / img)
    # the M2 compositor (05) reads run_dir/formats/<format>/layout.json + brand_kit.json and
    # the Stage-04 music mix (faked here — 04 is not part of the M1 slice).
    layout_dst = run_dir / "formats" / "ranked_list" / "layout.json"
    layout_dst.parent.mkdir(parents=True, exist_ok=True)
    layout_dst.write_text((repo / "formats" / "ranked_list" / "layout.json").read_text())
    (run_dir / "brand_kit.json").write_text(
        (repo / "tests" / "fixtures" / "m2" / "brand_kit.json").read_text())
    (run_dir / "music.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEfake")

    def ctx(stage, inp, outp, backends):
        return StageContext(
            stage=stage,
            run_dir=run_dir,
            seed=seed,
            job={"seed": seed, "video_id": "fin-0001", "platform_targets": ["youtube"]},
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
        import stages.s05_render.stage as s05

        # The compositor seams are faked like the s03 align seam above: the REAL render proof
        # moved to test_render_determinism (integration) when M2 replaced 05's ffmpeg interim.
        def _fake_render(manifest: dict, out_dir: Path) -> list[Path]:
            from stages.s01d_upscale.stage import _PLACEHOLDER_PNG

            frames_dir = out_dir / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for i in range(2):
                p = frames_dir / f"{i:05d}.png"
                p.write_bytes(_PLACEHOLDER_PNG)
                paths.append(p)
            return paths

        def _fake_encode(*, frames_glob: str, audio: Path, fps: int, out: Path) -> None:
            Path(out).write_bytes(b"\x00\x00\x00\x18ftypmp42fake")

        def _fake_thumbnail(render: Path, out: Path) -> None:
            from stages.s01d_upscale.stage import _PLACEHOLDER_PNG

            # real ffmpeg can't grab a frame off the fake mp4 bytes; content is irrelevant
            Path(out).write_bytes(_PLACEHOLDER_PNG)

        orig_render, orig_encode = s05.render_manifest_to_frames, s05._encode
        orig_thumb = s05._thumbnail
        try:
            s05.render_manifest_to_frames = _fake_render
            s05._encode = _fake_encode
            s05._thumbnail = _fake_thumbnail
            produced.update(
                _p(
                    run_05(
                        ctx(
                            "05",
                            {
                                "script": "script.json",
                                "assets": "assets.json",
                                "captions": "captions.ass",
                                "word_timings": "word_timings.json",
                                "music": "music.wav",
                                "data": "data.json",
                            },
                            {"render": "renders/youtube.mp4",
                             "thumbnail": "renders/thumbnail.jpg"},
                            {},
                        )
                    )
                )
            )
        finally:
            s05.render_manifest_to_frames = orig_render
            s05._encode = orig_encode
            s05._thumbnail = orig_thumb
    return produced


def _solid_png(path: Path):
    from PIL import Image

    Image.new("RGB", (1080, 1920), (12, 30, 18)).save(path)
