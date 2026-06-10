from shared.hashing import canonical_json, sha256_bytes, input_hash, cache_key


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_has_no_insignificant_whitespace():
    assert canonical_json({"a": 1}) == '{"a":1}'


def test_input_hash_stable_and_order_independent():
    digests = {"data": sha256_bytes(b"x"), "job": sha256_bytes(b"y")}
    h1 = input_hash(declared_input_digests=digests, resolved_config={"k": 1}, stage_version="1.0.0")
    h2 = input_hash(declared_input_digests=dict(reversed(list(digests.items()))),
                    resolved_config={"k": 1}, stage_version="1.0.0")
    assert h1 == h2
    assert len(h1) == 64  # hex sha256


def test_input_hash_changes_on_config_change():
    digests = {"data": sha256_bytes(b"x")}
    a = input_hash(declared_input_digests=digests, resolved_config={"k": 1}, stage_version="1.0.0")
    b = input_hash(declared_input_digests=digests, resolved_config={"k": 2}, stage_version="1.0.0")
    assert a != b


def test_generative_hash_folds_in_model_and_graph():
    digests = {"img": sha256_bytes(b"x")}
    base = input_hash(declared_input_digests=digests, resolved_config={}, stage_version="1.0.0")
    gen = input_hash(declared_input_digests=digests, resolved_config={}, stage_version="1.0.0",
                     model_id="flux.1-schnell", graph_version="g1")
    assert base != gen


def test_cache_key_includes_seed():
    assert cache_key("00b", "abc", 1) != cache_key("00b", "abc", 2)
    assert cache_key("00b", "abc", 1) == ("00b", "abc", 1)
