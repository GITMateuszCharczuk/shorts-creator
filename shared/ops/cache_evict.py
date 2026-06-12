def evict_to_cap(entries: list[dict], *, cap_gb: float = 50.0) -> list[dict]:
    """LRU by atime until total <= cap (file-based cache, open #11). Returns entries to delete;
    the caller unlinks their dirs under DATA_ROOT/.cache/."""
    total = sum(e["size_gb"] for e in entries)
    evicted = []
    for e in sorted(entries, key=lambda x: x["atime"]):
        if total <= cap_gb:
            break
        evicted.append(e)
        total -= e["size_gb"]
    return evicted
