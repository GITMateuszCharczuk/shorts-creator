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
    # bool is a subclass of int in Python -> reject it explicitly so a stray True/False in
    # data.json can never silently become a 1.0/0.0 numeric anchor for a claim.
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        raise GroundingError(f"source_ref {ref!r} is not numeric")
    return float(node)


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_number(text: str) -> float:
    # Assumes the claim value is a single normalized figure ("3.2%", "$184.21") in the SAME unit
    # as the data.json anchor; it extracts the first number and does NOT understand scale suffixes
    # (M/B/bps) or ranges -- those parse conservatively (a mismatch quarantines, never passes wrong).
    m = _NUM.search(text.replace(",", ""))
    if not m:
        raise GroundingError(f"no number in claim value {text!r}")
    return float(m.group())


def within_tolerance(parsed: float, expected: float) -> bool:
    return abs(parsed - expected) <= max(0.005 * abs(expected), 0.01)


def check_claims(claims: list[dict], data: dict[str, Any]) -> None:
    for c in claims:
        # a malformed claim is itself ungrounded -> quarantine it, never crash with a raw KeyError
        if "source_ref" not in c or "value" not in c:
            raise GroundingError(f"claim missing value/source_ref: {c!r}")
        expected = resolve_ref(data, c["source_ref"])
        parsed = parse_number(str(c["value"]))
        if not within_tolerance(parsed, expected):
            raise GroundingError(
                f"claim {c['value']!r} != data {expected} (ref {c['source_ref']})")
