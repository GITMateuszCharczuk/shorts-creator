import re
from pathlib import Path

STAGES = Path(__file__).resolve().parents[1] / "stages"
# matches the resolver-bypass smell: platform == "...", niche != '...'.
# `in` is intentionally NOT matched: `for niche in niches` / `platform in targets` are legitimate.
BAD = re.compile(r"\b(platform|niche)\b\s*(==|!=)")


def test_no_stage_branches_on_platform_or_niche():
    offenders = []
    for f in STAGES.rglob("*.py"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if BAD.search(line) and "noqa: resolver" not in line:
                offenders.append(f"{f}:{i}: {line.strip()}")
    assert not offenders, (
        "stages must resolve platform/niche via config, not branch:\n" + "\n".join(offenders))
