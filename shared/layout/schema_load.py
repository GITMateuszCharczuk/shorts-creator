import json
from pathlib import Path

from shared.schema import SchemaRegistry

_REG = SchemaRegistry()


def load_layout(path: Path) -> dict:
    layout = json.loads(Path(path).read_text())
    _REG.validate("layout", layout)
    return layout
