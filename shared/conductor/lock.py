import os
from pathlib import Path


class LockHeld(Exception):
    """Another batch run holds the lock (concurrencyPolicy: Forbid, ADR 0015 D3)."""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OverflowError):
        return False


def acquire_lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        holder = path.read_text().strip()
        # Unparseable/empty content = a holder mid-write (the create->write window) —
        # conservatively HELD, never stolen (TOCTOU guard). A holder that crashed in that window
        # leaves an empty lock that won't self-clear, so surface the manual recovery path.
        if not holder.isdigit():
            raise LockHeld(f"lock {path} has no readable holder ({holder or 'empty'}) — a run may "
                           f"have crashed mid-write; if no batch is running, remove it: rm {path}")
        if _pid_alive(int(holder)):
            raise LockHeld(f"batch already running (lock holder pid {holder})")
        path.unlink()                              # stale: holder pid is dead — take over
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise LockHeld("lost the stale-lock takeover race")
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)


def release_lock(path: Path) -> None:
    path.unlink(missing_ok=True)
