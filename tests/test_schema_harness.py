import pytest

from shared.schema import SchemaError, version_compatible


def test_same_version_ok():
    assert version_compatible(schema="1.2.0", instance="1.2.0") is True


def test_minor_mismatch_warns_but_ok():
    with pytest.warns(UserWarning):
        assert version_compatible(schema="1.3.0", instance="1.2.0") is True


def test_major_mismatch_raises():
    with pytest.raises(SchemaError):
        version_compatible(schema="2.0.0", instance="1.9.0")


def test_missing_instance_version_raises():
    with pytest.raises(SchemaError):
        version_compatible(schema="1.0.0", instance=None)
