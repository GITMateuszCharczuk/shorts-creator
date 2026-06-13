import os

import pytest

from shared.conductor import lock as lock_mod
from shared.conductor.lock import LockHeld, _pid_alive, acquire_lock, release_lock


def test_pid_alive_treats_permission_error_as_alive(monkeypatch):
    # M: a foreign-owned live process raises PermissionError on os.kill(pid, 0). Treating it
    # as dead would let acquire_lock STEAL a live lock. Conservative: PermissionError -> alive.
    def fake_kill(pid, sig):
        raise PermissionError("operation not permitted")

    monkeypatch.setattr(lock_mod.os, "kill", fake_kill)
    assert _pid_alive(12345) is True


def test_foreign_owned_live_lock_is_not_stolen(tmp_path, monkeypatch):
    lock = tmp_path / "batch.lock"
    lock.write_text("12345")                       # held by a foreign, live pid

    def fake_kill(pid, sig):
        raise PermissionError("operation not permitted")

    monkeypatch.setattr(lock_mod.os, "kill", fake_kill)
    with pytest.raises(LockHeld):                  # alive foreign holder -> never taken over
        acquire_lock(lock)
    assert lock.read_text() == "12345"             # untouched


def test_pid_alive_treats_process_lookup_as_dead(monkeypatch):
    def fake_kill(pid, sig):
        raise ProcessLookupError("no such process")

    monkeypatch.setattr(lock_mod.os, "kill", fake_kill)
    assert _pid_alive(12345) is False              # genuinely dead -> takeover allowed


def test_acquire_then_second_acquire_fails(tmp_path):
    lock = tmp_path / "batch.lock"
    acquire_lock(lock)
    with pytest.raises(LockHeld):
        acquire_lock(lock)
    release_lock(lock)


def test_stale_lock_is_taken_over(tmp_path):
    lock = tmp_path / "batch.lock"
    lock.write_text("999999999")                  # a pid that cannot exist
    acquire_lock(lock)                            # no raise: stale -> takeover
    assert lock.read_text() == str(os.getpid())


def test_unparseable_lock_is_treated_as_held(tmp_path):
    lock = tmp_path / "batch.lock"
    lock.write_text("")                           # a holder mid-write (TOCTOU window)
    with pytest.raises(LockHeld):
        acquire_lock(lock)                        # conservatively held, never stolen


def test_release_is_idempotent(tmp_path):
    lock = tmp_path / "batch.lock"
    acquire_lock(lock)
    release_lock(lock)
    release_lock(lock)  # second release must not crash


def test_reacquire_after_release(tmp_path):
    lock = tmp_path / "batch.lock"
    acquire_lock(lock)
    release_lock(lock)
    acquire_lock(lock)  # must succeed after release
    assert lock.read_text() == str(os.getpid())
    release_lock(lock)
