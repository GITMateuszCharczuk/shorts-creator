"""Generate LLM fixtures for stage 00b (best-of-N script + judge).

Run with:  uv run python tests/fixtures/backends/llm/_generate_00b_fixtures.py
Not collected by pytest (no test_ prefix).
"""
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from shared.config import resolve_config  # noqa: E402
from shared.hashing import input_hash, sha256_bytes  # noqa: E402
from stages.s00b_script.stage import _build_prompt, build_judge_prompt  # noqa: E402

DATA = json.loads((REPO / "tests/fixtures/m1/data.json").read_text())
SCRIPT = json.loads(
    (REPO / "tests/fixtures/m1/ollama_responses/script.json").read_text()
)
SCRIPT_TEXT = json.dumps(SCRIPT)  # exactly what llm() returns
OUT_DIR = Path(__file__).parent


def fixture_hash(prompt: str) -> str:
    return input_hash(
        declared_input_digests={"prompt": sha256_bytes(prompt.encode())},
        resolved_config={},
        stage_version="fake",
    )


def main() -> None:
    config_input = {"data_fixture": "data_fixture.json", "best_of_n": 1}
    resolved = resolve_config(
        global_defaults=config_input, niche={}, batch={}, per_platform={}
    )

    for seed in (7, 8):
        rng = random.Random(seed)
        gen_seed = rng.randint(0, 2**31)
        prompt = _build_prompt(DATA, resolved, gen_seed)
        h = fixture_hash(prompt)
        p = OUT_DIR / f"{h}.txt"
        p.write_text(SCRIPT_TEXT)
        print(f"seed={seed}: gen fixture {h}.txt")

        parsed = json.loads(SCRIPT_TEXT)
        judge_prompt = build_judge_prompt(parsed)
        jh = fixture_hash(judge_prompt)
        jp = OUT_DIR / f"{jh}.txt"
        jp.write_text("0.82")
        print(f"seed={seed}: judge fixture {jh}.txt")


if __name__ == "__main__":
    main()
