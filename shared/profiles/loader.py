from pathlib import Path

import yaml

from shared.schema import SchemaRegistry

_REG = SchemaRegistry()


def load_profile(path: Path) -> dict:
    profile = yaml.safe_load(Path(path).read_text())
    _REG.validate("profile", profile)
    return profile
