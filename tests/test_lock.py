import os

import pytest

from shared.conductor.lock import LockHeld, acquire_lock, release_lock


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
