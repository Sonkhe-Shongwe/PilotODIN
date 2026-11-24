"""Cooperating analytics-writer ownership before any database initialization.

The lease is a persistent empty file, not a PID or ownership marker. Only the
open OS lock establishes ownership. This startup preflight rejects existing
redirects; it is not a sandbox or a defense against hostile concurrent path
replacement. Full Rust/desktop and per-write path admission are separate.
"""
from __future__ import annotations

import atexit
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat

LOCK_NAME = ".pilotodin-engine.lock"
DIRECTORIES = ("datasets", "models", "backend-temp", "inference-temp", "export_tmp")
FILES = ("pilotodin.sqlite3", "pilotodin.sqlite3-journal", "pilotodin.sqlite3-wal",
         "pilotodin.sqlite3-shm", "ai_settings.json", "ai_settings.tmp",
         "ai_secrets.dpapi", "resource_preferences.json")


class WorkspaceBoundaryError(RuntimeError):
    """Fixed, path-free startup failure."""


def _redirected(info):
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & 0x400))


def _directory(path):
    info = path.lstat()
    if _redirected(info) or not stat.S_ISDIR(info.st_mode):
        raise WorkspaceBoundaryError("Workspace directory is redirected or invalid")


def _regular(info, *, empty=False):
    if (_redirected(info) or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1 or (empty and info.st_size != 0)):
        raise WorkspaceBoundaryError("Workspace file is redirected or invalid")


def _home(value):
    if not isinstance(value, str) or not value:
        raise WorkspaceBoundaryError("Explicit local workspace required")
    path = Path(value)
    if not path.is_absolute() or len(path.parts) < 2 or ".." in path.parts:
        raise WorkspaceBoundaryError("Explicit local workspace required")
    if os.name == "nt" and (not re.fullmatch(r"[A-Za-z]:", path.drive)
                            or any(":" in part or part.endswith((" ", "."))
                                   for part in path.parts[1:])):
        raise WorkspaceBoundaryError("Explicit local workspace required")
    for parent in reversed(path.parents):
        _directory(parent)
    try:
        _directory(path)
    except FileNotFoundError:
        # Only a missing final component may be created. Never recursively
        # create a caller-supplied chain of unverified ancestors.
        try:
            path.mkdir()
        except FileExistsError:
            pass
        _directory(path)
    return path


def _verify_entries(home):
    for name in DIRECTORIES:
        try:
            _directory(home / name)
        except FileNotFoundError:
            pass
    for name in FILES:
        try:
            info = (home / name).lstat()
        except FileNotFoundError:
            continue
        _regular(info)


def _same_lock(fd, path):
    opened = os.fstat(fd)
    named = path.lstat()
    _regular(opened, empty=True)
    _regular(named, empty=True)
    if not opened.st_ino or not named.st_ino or not os.path.samestat(opened, named):
        raise WorkspaceBoundaryError("Workspace lock identity unverified")


def _acquire(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt
        # The locked byte may extend beyond EOF. Do not write a marker byte.
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    elif os.name == "posix":
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        raise WorkspaceBoundaryError("Workspace locking unavailable")


@contextmanager
def engine_workspace(value):
    """Hold a non-inheritable exclusive writer lease until the caller exits."""
    fd = None
    try:
        try:
            home = _home(value)
            _verify_entries(home)
            path = home / LOCK_NAME
            try:
                _regular(path.lstat(), empty=True)
            except FileNotFoundError:
                pass
            flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                fd = os.open(path, flags)
            # Never truncate, replace, or unlink the persistent lock.
            _same_lock(fd, path)
            try:
                _acquire(fd)
            except OSError as exc:
                raise WorkspaceBoundaryError("Workspace already in use or locking unavailable") from exc
            _same_lock(fd, path)
            _directory(home)
            _verify_entries(home)
        except OSError as exc:
            raise WorkspaceBoundaryError("Workspace storage unavailable or unsafe") from exc
        yield home
    finally:
        # Closing the original non-inheritable descriptor releases the OS lock.
        if fd is not None:
            os.close(fd)


# Keep runtime ownership through interpreter shutdown, after non-daemon
# executor threads have finished, rather than only through server.run().
_process_lease = None


def hold_process_workspace(value):
    global _process_lease
    if _process_lease is not None:
        raise WorkspaceBoundaryError("Workspace ownership already established")
    lease = engine_workspace(value)
    home = lease.__enter__()
    _process_lease = lease
    atexit.register(lease.__exit__, None, None, None)
    return home
