from shared.ops.cache_evict import evict_to_cap


def test_evicts_least_recently_used_until_under_cap():
    entries = [{"key": "a", "size_gb": 30, "atime": 1}, {"key": "b", "size_gb": 30, "atime": 2},
               {"key": "c", "size_gb": 30, "atime": 3}]                  # 90 GB, cap 50
    evicted = evict_to_cap(entries, cap_gb=50)
    survivors = {e["key"] for e in entries} - {e["key"] for e in evicted}
    assert [e["key"] for e in evicted] == ["a", "b"]                     # oldest atime first
    assert survivors == {"c"} and sum(e["size_gb"] for e in entries if e["key"] in survivors) <= 50


def test_under_cap_evicts_nothing():
    assert evict_to_cap([{"key": "a", "size_gb": 10, "atime": 1}], cap_gb=50) == []
