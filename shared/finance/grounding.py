import re
from typing import Any


class GroundingError(Exception):
    """A cited figure is ungrounded or out of tolerance vs data.json."""


def resolve_ref(data: dict[str, Any], ref: str) -> float:
    node: Any = data
    for part in ref.split("."):
        if not isinstance(node, dict) or part not in node:
            raise GroundingError(f"unresolved source_ref: {ref!r}")
        node = node[part]
    if isinstance(node, dict) and "value" in node:
        node = node["value"]
    if not isinstance(node, (int, float)):
        raise GroundingError(f"source_ref {ref!r} is not numeric")
    return float(node)


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_number(text: str) -> float:
    m = _NUM.search(text.replace(",", ""))
    if not m:
        raise GroundingError(f"no number in claim value {text!r}")
    return float(m.group())


def within_tolerance(parsed: float, expected: float) -> bool:
    return abs(parsed - expected) <= max(0.005 * abs(expected), 0.01)


def check_claims(claims: list[dict], data: dict[str, Any]) -> None:
    for c in claims:
        expected = resolve_ref(data, c["source_ref"])
        parsed = parse_number(c["value"])
        if not within_tolerance(parsed, expected):
            raise GroundingError(
                f"claim {c['value']!r} != data {expected} (ref {c['source_ref']})")
