import random


class NoFormatError(Exception):
    """No format is lane-compatible after anti-repeat exclusion (relax `recent` upstream)."""


def pick_format(formats: list[dict], *, lane: str, recent: list[str], seed: int) -> dict:
    pool = [f for f in formats
            if f["lane_support"].get(lane, False) and f["id"] not in recent]
    if not pool:
        raise NoFormatError(f"no format for lane={lane} outside recent={recent}")
    pool.sort(key=lambda f: f["id"])                  # stable order before the seeded pick
    return random.Random(seed).choice(pool)
