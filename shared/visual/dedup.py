"""Perceptual-hash cross-video deduplication (ADR 0005 D5).

Contract for malformed hashes
------------------------------
- Malformed CANDIDATE hash (phash argument): raises ``ValueError`` — the candidate is
  computed locally, so an unparseable string indicates a code bug that must surface.
- Malformed USED entry: silently skipped (treated as non-matching).  A corrupt ledger
  entry should not kill dedup for all future candidates; the ledger self-heals as that
  entry ages out.
"""


def _hamming_hex(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def is_duplicate(phash: str, used: set[str], max_distance: int = 2) -> bool:
    # Parse the candidate first — raises ValueError for bad input (see module docstring).
    candidate_int = int(phash, 16)
    for u in used:
        try:
            u_int = int(u, 16)
        except ValueError:
            # Corrupt ledger entry — skip rather than crash (self-healing contract).
            continue
        if bin(candidate_int ^ u_int).count("1") <= max_distance:
            return True
    return False


def filter_new(candidates: list[tuple[str, str]], used: set[str],
               max_distance: int = 2) -> list[tuple[str, str]]:
    return [(p, h) for p, h in candidates if not is_duplicate(h, used, max_distance)]
