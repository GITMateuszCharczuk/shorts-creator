import pytest

from shared.host_client import resolve, to_relative


def test_comfyui_host_absolute_path_becomes_data_root_relative():
    rel = to_relative("/srv/shorts-data/runs/b1/v1/scenes/01.png", data_root="/srv/shorts-data")
    assert rel == "runs/b1/v1/scenes/01.png" and not rel.startswith("/")


def test_already_relative_is_unchanged():
    assert to_relative("runs/b1/v1/x.png", data_root="/srv/shorts-data") == "runs/b1/v1/x.png"


def test_path_outside_data_root_is_a_hard_error():
    with pytest.raises(ValueError):
        to_relative("/tmp/elsewhere/x.png", data_root="/srv/shorts-data")


def test_dotdot_traversal_is_rejected():
    """Path traversal via .. segments must raise, not return a path outside DATA_ROOT."""
    with pytest.raises(ValueError):
        to_relative("/srv/shorts-data/../etc/passwd", data_root="/srv/shorts-data")


def test_resolve_uses_THIS_process_data_root(monkeypatch):
    monkeypatch.setenv("DATA_ROOT", "/data")
    assert str(resolve("runs/b1/v1/x.png")) == "/data/runs/b1/v1/x.png"
    monkeypatch.setenv("DATA_ROOT", "/srv/shorts-data")
    assert str(resolve("runs/b1/v1/x.png")) == "/srv/shorts-data/runs/b1/v1/x.png"
