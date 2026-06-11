import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# ADR 0010 D5 applies to all SDK-facing code, not just stages/ — scan shared/ too.
SCAN_ROOTS = [REPO / "stages", REPO / "shared"]
# matches the resolver-bypass smell: platform == "...", niche != '...'.
# `in` is intentionally NOT matched: `for niche in niches` / `platform in targets` are legitimate.
# KNOWN LIMITS (cheap syntactic smell-catcher, not an AST proof): an aliased var
# (`plat = ...; if plat == "youtube"`), `match platform:`/`case`, and dict-dispatch
# (`ADAPTERS[platform]()`) slip past. M4+ can add AST analysis if a real bypass appears.
BAD = re.compile(r"\b(platform|niche)\b\s*(==|!=)")


def test_no_stage_branches_on_platform_or_niche():
    offenders = []
    for root in SCAN_ROOTS:
        for f in root.rglob("*.py"):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if BAD.search(line) and "noqa: resolver" not in line:
                    offenders.append(f"{f}:{i}: {line.strip()}")
    assert not offenders, (
        "stages must resolve platform/niche via config, not branch:\n" + "\n".join(offenders))
