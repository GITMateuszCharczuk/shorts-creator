import json
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """An empty per-test run directory standing in for runs/<batch-id>/<video-id>/."""
    d = tmp_path / "run"
    d.mkdir()
    return d


def write_json(path: Path, obj: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))
    return path
