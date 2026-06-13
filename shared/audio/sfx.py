def cues_for_scenes(scenes: list[dict]) -> list[dict]:
    """Map scene kinds to transition SFX: whoosh on each cut, tick per list item,
    riser+impact on a reveal beat (verdict/takeaway/so_what)."""
    cues = []
    reveal = {"verdict", "takeaway", "so_what", "truth"}
    for i, s in enumerate(scenes):
        if i > 0:
            cues.append({"at_scene": i, "sfx": "whoosh"})
        if s["kind"] in ("item", "step"):
            cues.append({"at_scene": i, "sfx": "tick"})
        if s["kind"] in reveal:
            cues.append({"at_scene": i, "sfx": "riser"})
    return cues
