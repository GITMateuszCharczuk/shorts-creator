import random

MOODS = {"confident", "tense", "uplifting", "somber", "neutral"}
ENERGIES = {"low", "mid", "high"}


class NoTrackError(Exception):
    """No library track matches (mood, energy) after anti-repeat exclusion."""


def select_track(library: list[dict], *, mood: str, energy: str, seed: int,
                 recent_ids: set[str]) -> dict:
    if mood not in MOODS or energy not in ENERGIES:
        raise ValueError(f"unknown mood/energy: {mood}/{energy}")
    pool = [t for t in library if t["mood"] == mood and t["energy"] == energy
            and t["id"] not in recent_ids]
    if not pool:
        raise NoTrackError(f"no track for {mood}/{energy} (recent={recent_ids})")
    pool.sort(key=lambda t: t["id"])               # stable order before seeded pick
    return random.Random(seed).choice(pool)
