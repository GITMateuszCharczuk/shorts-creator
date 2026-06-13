import pytest

from shared.layout.bind import BindError, validate_binds


def test_static_bind_always_ok():
    validate_binds(["static"], beat_data={})  # no raise (content comes from primitive.params)


def test_dotted_bind_must_exist():
    validate_binds(["item.title", "item.stat"], beat_data={"item": {"title": "x", "stat": "y"}})


def test_missing_bind_raises():
    with pytest.raises(BindError):
        validate_binds(["item.missing"], beat_data={"item": {"title": "x"}})


def test_bind_through_non_dict_raises():
    # a path that descends through a scalar must be a clear BindError, not a crash
    with pytest.raises(BindError):
        validate_binds(["item.title.deep"], beat_data={"item": {"title": "x"}})
