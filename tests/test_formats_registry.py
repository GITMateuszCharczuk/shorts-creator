import json
from pathlib import Path

import pytest

FORMATS = Path(__file__).resolve().parents[1] / "formats"


@pytest.mark.parametrize("fmt_dir", sorted(FORMATS.glob("*/")), ids=lambda p: p.name)
def test_format_json_matches_its_layout(fmt_dir: Path):
    # drift-catcher: format.json and layout.json describe the SAME format — the id must match
    # the directory name and the beat_pattern must be byte-identical between the two files.
    fmt = json.loads((fmt_dir / "format.json").read_text())
    layout = json.loads((fmt_dir / "layout.json").read_text())
    assert fmt["id"] == fmt_dir.name
    assert fmt["beat_pattern"] == layout["beat_pattern"]


def test_sweep_covers_all_eight_formats():
    assert len(sorted(FORMATS.glob("*/format.json"))) == 8
