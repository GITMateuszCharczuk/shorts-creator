from shared.cache import StageCache
from shared.hashing import cache_key


def test_miss_then_hit(tmp_path):
    c = StageCache(root=tmp_path)
    k = cache_key("00b", "hashA", 7)
    assert c.get(k) is None
    c.put(k, {"script": "s.json"})
    assert c.get(k) == {"script": "s.json"}


def test_different_seed_is_a_miss(tmp_path):
    c = StageCache(root=tmp_path)
    c.put(cache_key("00b", "hashA", 7), {"script": "s.json"})
    assert c.get(cache_key("00b", "hashA", 8)) is None


def test_different_input_hash_is_a_miss(tmp_path):
    c = StageCache(root=tmp_path)
    c.put(cache_key("00b", "hashA", 7), {"script": "s.json"})
    assert c.get(cache_key("00b", "hashB", 7)) is None
