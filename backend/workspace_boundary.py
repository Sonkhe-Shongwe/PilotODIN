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
from threading import RLock

LOCK_NAME = ".pilotodin-engine.lock"
RESTORE_STAGE_NAME = ".pilotodin-restore-stage"
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
    return info


class _DirectoryPin:
    """Retain an original directory handle; never grant Windows delete sharing.

    Windows uses the full handle-derived volume/file identity. POSIX retains
    the directory descriptor for identity checks, but does not prevent rename.
    Neither implementation confines arbitrary third-party path-based opens.
    """

    def __init__(self, path, observed):
        self.handle = None
        self.path = path
        try:
            self.handle = self._open()
            self.identity = self._identity(self.handle)
            self.verify(observed)
        except BaseException:
            self.close()
            raise

    def _open(self):
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                               wintypes.HANDLE)
            create.restype = wintypes.HANDLE
            # FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES participates in
            # sharing checks; FILE_SHARE_READ | FILE_SHARE_WRITE, no DELETE.
            # OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
            # Null security attributes make the handle non-inheritable.
            handle = create(str(self.path), 0x81, 0x3, None, 3, 0x02200000, None)
            if handle is None or handle == ctypes.c_void_p(-1).value:
                raise OSError("Directory handle unavailable")
            return handle
        if os.name == "posix":
            return os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                           | getattr(os, "O_CLOEXEC", 0))
        raise WorkspaceBoundaryError("Directory handle protection unavailable")

    @staticmethod
    def _identity(handle):
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class AttributeTag(ctypes.Structure):
                _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

            class FileId(ctypes.Structure):
                _fields_ = [("volume", ctypes.c_uint64), ("identifier", ctypes.c_ubyte * 16)]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            query = kernel.GetFileInformationByHandleEx
            query.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
            query.restype = wintypes.BOOL
            attr = AttributeTag()
            identity = FileId()
            # FileAttributeTagInfo (9), FileIdInfo (18). Reject directory
            # handles with reparse attributes and missing physical identity.
            if (not query(handle, 9, ctypes.byref(attr), ctypes.sizeof(attr))
                    or not attr.attributes & 0x10 or attr.attributes & 0x400
                    or not query(handle, 18, ctypes.byref(identity), ctypes.sizeof(identity))
                    or not any(identity.identifier)):
                raise WorkspaceBoundaryError("Directory handle identity unverified")
            return identity.volume, bytes(identity.identifier)
        info = os.fstat(handle)
        if not stat.S_ISDIR(info.st_mode) or not info.st_ino:
            raise WorkspaceBoundaryError("Directory handle identity unverified")
        return info.st_dev, info.st_ino

    @staticmethod
    def _close(handle):
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            close = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
            close.argtypes = (wintypes.HANDLE,)
            close.restype = wintypes.BOOL
            close(handle)
        else:
            os.close(handle)

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self._close(handle)

    def verify(self, observed):
        before = _directory(self.path)
        if not before.st_ino or not os.path.samestat(observed, before):
            raise WorkspaceBoundaryError("Directory name identity changed")
        if self._identity(self.handle) != self.identity:
            raise WorkspaceBoundaryError("Original directory handle identity changed")
        # Compare a fresh handle opened at the current name against the
        # original handle rather than assuming Python's stat layout matches
        # the Windows 128-bit file ID representation.
        named = self._open()
        try:
            if self._identity(named) != self.identity:
                raise WorkspaceBoundaryError("Directory handle identity changed")
        finally:
            self._close(named)
        after = _directory(self.path)
        if not os.path.samestat(before, after):
            raise WorkspaceBoundaryError("Directory name identity changed")


def _close_directory_pins(pins):
    for pin in reversed(tuple(pins.values())):
        pin.close()


def _pin_directory_chain(home, root_identity, ancestors, children):
    pins = {}
    try:
        for path, identity in (*ancestors.items(), (home, root_identity),
                               *((home / name, info) for name, info in children.items())):
            pin = _DirectoryPin(path, identity)
            pins[path] = pin
        volume = pins[home].identity[0]
        if any(pin.identity[0] != volume for pin in pins.values()):
            raise WorkspaceBoundaryError("Workspace directory volume changed")
        return pins
    except BaseException:
        _close_directory_pins(pins)
        raise


def _regular(info, *, empty=False):
    if (_redirected(info) or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1 or (empty and info.st_size != 0)):
        raise WorkspaceBoundaryError("Workspace file is redirected or invalid")


def _home(value, *, create=True):
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
        if not create:
            raise
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


def _reject_restore_stage(home):
    # Any entry, even a malformed or redirected marker, blocks normal
    # admission. Never remove or interpret it as permission to activate.
    try:
        (home / RESTORE_STAGE_NAME).lstat()
    except FileNotFoundError:
        return
    raise WorkspaceBoundaryError("Restore stage requires separate activation approval")


@contextmanager
def _workspace_lease(value, *, create=True):
    """Retain the descriptor and original workspace identity for runtime checks."""
    fd = None
    try:
        try:
            home = _home(value, create=create)
            root_identity = _directory(home)
            _reject_restore_stage(home)
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
            if not os.path.samestat(root_identity, _directory(home)):
                raise WorkspaceBoundaryError("Workspace identity changed")
            _reject_restore_stage(home)
            _verify_entries(home)
        except OSError as exc:
            raise WorkspaceBoundaryError("Workspace storage unavailable or unsafe") from exc
        yield home, fd, root_identity
    finally:
        # Closing the original non-inheritable descriptor releases the OS lock.
        if fd is not None:
            os.close(fd)


@contextmanager
def engine_workspace(value):
    """Hold a non-inheritable exclusive writer lease until the caller exits."""
    with _workspace_lease(value) as (home, _, _root_identity):
        yield home


@contextmanager
def pinned_existing_directory(value, *, expected=None, workspace_children=False):
    """Retain one existing physical directory chain for a bounded operation.

    Only the known immediate workspace children may optionally be retained.
    Never create a path or pin an unbounded directory tree. The caller must
    verify before consequential writes; POSIX checks do not prevent renames.
    """
    pins = {}
    try:
        try:
            canonical = existing_fixture_home(str(value))
            root_identity = _directory(canonical)
            if expected is not None and not os.path.samestat(expected, root_identity):
                raise WorkspaceBoundaryError("Scoped directory identity changed")
            ancestors = {parent: _directory(parent) for parent in reversed(canonical.parents)}
            children = {}
            if workspace_children:
                for name in DIRECTORIES:
                    try:
                        children[name] = _directory(canonical / name)
                    except FileNotFoundError:
                        pass
            pins = _pin_directory_chain(canonical, root_identity, ancestors, children)
            observed = {**ancestors, canonical: root_identity,
                        **{canonical / name: info for name, info in children.items()}}
        except OSError as exc:
            raise WorkspaceBoundaryError("Scoped directory unavailable or unsafe") from exc

        def verify():
            try:
                for path, identity in observed.items():
                    pins[path].verify(identity)
            except OSError as exc:
                raise WorkspaceBoundaryError("Scoped directory unavailable or unsafe") from exc

        verify()
        yield verify
    finally:
        _close_directory_pins(pins)


@contextmanager
def fresh_restore_stage(value, *, expected):
    """Own a new empty destination before writing any restored payload.

    Retain a permanent nonactivation marker, even on failure or success.
    Normal engine/maintenance leases refuse the marker. No activation or
    marker-removal operation is supplied here.
    """
    canonical = existing_fixture_home(value)
    if not os.path.samestat(expected, _directory(canonical)):
        raise WorkspaceBoundaryError("Restore directory identity changed")
    with _workspace_lease(value, create=False) as (home, fd, root_identity):
        if home != canonical or not os.path.samestat(expected, root_identity):
            raise WorkspaceBoundaryError("Restore directory identity changed")
        with pinned_existing_directory(home, expected=root_identity) as verify_root:
            verify_root()
            if {entry.name for entry in home.iterdir()} != {LOCK_NAME}:
                raise WorkspaceBoundaryError("Restore destination is not empty")
            marker = home / RESTORE_STAGE_NAME
            with marker.open("xb") as output:
                identity = os.fstat(output.fileno())
                os.fsync(output.fileno())

            def verify():
                verify_root()
                _same_lock(fd, home / LOCK_NAME)
                observed = marker.lstat()
                _regular(observed, empty=True)
                if not observed.st_ino or not os.path.samestat(identity, observed):
                    raise WorkspaceBoundaryError("Restore stage marker identity changed")
                _verify_entries(home)

            verify()
            yield home, verify


@contextmanager
def existing_maintenance_workspace(value):
    """Acquire the shared lease for an existing, physically checked workspace.

    Unlike startup, maintenance must never create a missing workspace or DB.
    This coordinates cooperating writers; it is not a filesystem sandbox.
    """
    canonical = existing_fixture_home(value)
    database = canonical / "pilotodin.sqlite3"
    before = existing_fixture_file(database)
    before_root = _directory(canonical)
    with _workspace_lease(value, create=False) as (home, fd, root_identity):
        if (existing_fixture_home(str(home)) != canonical
                or not os.path.samestat(before_root, root_identity)):
            raise WorkspaceBoundaryError("Maintenance workspace identity changed")
        with pinned_existing_directory(canonical, expected=root_identity,
                                       workspace_children=True) as verify_pins:
            def verify():
                verify_pins()
                _same_lock(fd, canonical / LOCK_NAME)
                _verify_entries(canonical)
                _database_identity(canonical, before)

            verify()
            yield canonical, verify


# Keep runtime ownership through interpreter shutdown, after non-daemon
# executor threads have finished, rather than only through server.run().
_process_lease = None
_process_workspace = None
_process_directories = {}
_process_ancestors = {}
_process_scratch = None
_process_pins = {}
_pin_lock = RLock()


def _database_identity(home, previous=None):
    identity = None
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            info = (home / ("pilotodin.sqlite3" + suffix)).lstat()
        except FileNotFoundError:
            if not suffix and previous is not None:
                raise WorkspaceBoundaryError("Owned database disappeared")
            continue
        _regular(info)
        if not suffix:
            if not info.st_ino or (previous is not None
                                   and not os.path.samestat(previous, info)):
                raise WorkspaceBoundaryError("Owned database identity changed")
            identity = info
    return identity


def hold_process_workspace(value):
    global _process_lease, _process_workspace
    if _process_lease is not None:
        raise WorkspaceBoundaryError("Workspace ownership already established")
    lease = _workspace_lease(value)
    home, fd, root_identity = lease.__enter__()
    pins = {}
    try:
        # Resolve only AFTER the supplied path and lock have passed the
        # no-redirect checks. Windows short names may differ from the long
        # path previously used by storage. Require the original directory
        # and lock identities at the resolved spelling, not just a string.
        canonical = home.resolve(strict=True)
        if not canonical.is_absolute() or ".." in canonical.parts:
            raise WorkspaceBoundaryError("Workspace identity changed")
        if os.name == "nt" and (not re.fullmatch(r"[A-Za-z]:", canonical.drive)
                                or any(":" in part or part.endswith((" ", "."))
                                       for part in canonical.parts[1:])):
            raise WorkspaceBoundaryError("Workspace identity changed")
        for parent in reversed(canonical.parents):
            _directory(parent)
        current = _directory(canonical)
        if (not current.st_ino or not root_identity.st_ino
                or not os.path.samestat(root_identity, current)):
            raise WorkspaceBoundaryError("Workspace identity changed")
        _same_lock(fd, canonical / LOCK_NAME)
        # Recheck the original spelling as well; never normalize an
        # unchecked redirect into an apparently safe path.
        for parent in reversed(home.parents):
            _directory(parent)
        if not os.path.samestat(root_identity, _directory(home)):
            raise WorkspaceBoundaryError("Workspace identity changed")
        _same_lock(fd, home / LOCK_NAME)
        _verify_entries(canonical)
        database_identity = _database_identity(canonical)
        ancestor_identities = {}
        for parent in reversed(canonical.parents):
            identity = _directory(parent)
            if not identity.st_ino:
                raise WorkspaceBoundaryError("Workspace ancestor identity unverified")
            ancestor_identities[parent] = identity
        directory_identities = {}
        for name in DIRECTORIES:
            try:
                directory_identities[name] = _directory(canonical / name)
            except FileNotFoundError:
                pass
        pins = _pin_directory_chain(canonical, root_identity,
                                    ancestor_identities, directory_identities)
        _same_lock(fd, canonical / LOCK_NAME)
        _verify_entries(canonical)
    except BaseException as exc:
        _close_directory_pins(pins)
        lease.__exit__(None, None, None)
        if isinstance(exc, (OSError, RuntimeError)) and not isinstance(exc, WorkspaceBoundaryError):
            raise WorkspaceBoundaryError("Workspace storage unavailable or unsafe") from exc
        raise
    _process_lease = lease
    _process_workspace = (canonical, fd, root_identity, database_identity)
    _process_directories.update(directory_identities)
    _process_ancestors.update(ancestor_identities)
    _process_pins.update(pins)
    atexit.register(lease.__exit__, None, None, None)
    # LIFO shutdown: close directory handles before releasing writer lease.
    atexit.register(_close_directory_pins, _process_pins)
    return canonical


def existing_fixture_home(value):
    """Validate an already allocated fixture directory without creating it."""
    try:
        supplied = _home(value, create=False)
        identity = _directory(supplied)
        canonical = supplied.resolve(strict=True)
        _home(str(canonical), create=False)
        if (not identity.st_ino
                or not os.path.samestat(identity, _directory(canonical))):
            raise WorkspaceBoundaryError("Fixture workspace identity changed")
        return canonical
    except OSError as exc:
        raise WorkspaceBoundaryError("Fixture workspace unavailable or unsafe") from exc


def existing_fixture_file(path):
    """Check a regular single-link file under an existing nonredirected parent."""
    try:
        parent = existing_fixture_home(str(path.parent))
        if parent != path.parent:
            raise WorkspaceBoundaryError("Fixture file parent identity changed")
        info = path.lstat()
        _regular(info)
        return info
    except OSError as exc:
        raise WorkspaceBoundaryError("Fixture file unavailable or unsafe") from exc


def hold_fresh_fixture_workspace(value, expected):
    """Called only after a seeder's existing manifest and scope checks."""
    if existing_fixture_home(value) != expected:
        raise WorkspaceBoundaryError("Fixture workspace identity changed")
    if any(expected.iterdir()):
        raise WorkspaceBoundaryError("Fixture workspace is not empty")
    owned = hold_process_workspace(value)
    if owned != expected or {entry.name for entry in owned.iterdir()} != {LOCK_NAME}:
        raise WorkspaceBoundaryError("Fixture workspace changed during ownership admission")
    return owned


def _reject_unleased_runtime(path):
    """Prevent the compatibility import seam selecting named owned roots.

    This is a product entrypoint rule, not authentication of arbitrary
    Python code or proof that every other absolute path is disposable.
    """
    if (os.environ.get("PILOTODIN_SERVER_MODE")
            or os.environ.get("PILOTODIN_DESKTOP_SESSION")):
        raise WorkspaceBoundaryError("Runtime workspace requires writer ownership")
    parts = tuple(part.casefold() for part in path.parts)
    checkout_data = Path(__file__).resolve().parents[1] / "data"
    if (path.is_relative_to(checkout_data)
            or any(part == ".pilotodin-dev-data" or part.startswith("com.pilotodin.")
                   for part in parts)
            or any(re.fullmatch(r"pilotodin-p1-real-http-[0-9]+|p4-71-only-home-[0-9]+", part)
                   for part in parts)):
        raise WorkspaceBoundaryError("Runtime workspace requires writer ownership")
    # The five managed native QA phases also require the owned entrypoint.
    # Other historical disposable in-process QA fixtures are not promoted
    # to runtime authority by this compatibility rule.
    for i in range(len(parts) - 3):
        if parts[i:i+3] == ("pilotodin", "devqa", "runs"):
            if re.fullmatch(
                r"p(?:2-native-(?:chain|deliver-consent|two-window-deliver)|3-native-(?:semantic-context|quality-w5))-[0-9]{8}t[0-9]{6}z-[a-f0-9]{10}",
                parts[i+3],
            ):
                raise WorkspaceBoundaryError("Runtime workspace requires writer ownership")


def storage_home(value):
    """Require an explicit home; leased storage uses the admitted path."""
    if not isinstance(value, str) or not value:
        raise WorkspaceBoundaryError("Explicit local workspace required")
    if _process_workspace is None:
        supplied = Path(value)
        if not supplied.is_absolute() or ".." in supplied.parts:
            raise WorkspaceBoundaryError("Explicit local workspace required")
        _reject_unleased_runtime(supplied)
        try:
            # Before creating a missing final directory, check the physically
            # validated parent's canonical spelling as well as the input.
            try:
                _home(value, create=False)
            except FileNotFoundError:
                parent = existing_fixture_home(str(supplied.parent))
                _reject_unleased_runtime(parent / supplied.name)
                _home(value)
            canonical = existing_fixture_home(value)
            _reject_unleased_runtime(canonical)
            _reject_restore_stage(canonical)
            try:
                (canonical / LOCK_NAME).lstat()
            except FileNotFoundError:
                pass
            else:
                # A marker is not evidence of a live lock; it identifies a
                # workspace that must be reopened through its owned route.
                raise WorkspaceBoundaryError("Runtime workspace requires writer ownership")
            _verify_entries(canonical)
            return canonical
        except OSError as exc:
            raise WorkspaceBoundaryError("Workspace storage unavailable or unsafe") from exc
    owned = _process_workspace[0]
    if Path(value) != owned:
        raise WorkspaceBoundaryError("Database outside owned workspace")
    return owned


def _validate_owned_ancestors(owned):
    for parent in reversed(owned.parents):
        current = _directory(parent)
        previous = _process_ancestors.get(parent)
        if previous is None or not current.st_ino or not os.path.samestat(previous, current):
            raise WorkspaceBoundaryError("Workspace ancestor identity changed")
        _process_pins[parent].verify(current)
    _process_pins[owned].verify(_process_workspace[2])


def _validate_owned_subdirectory(owned, name, info):
    path = owned / name
    with _pin_lock:
        previous = _process_directories.setdefault(name, info)
        if not info.st_ino or not os.path.samestat(previous, info):
            raise WorkspaceBoundaryError("Workspace subdirectory identity changed")
        pin = _process_pins.get(path)
        if pin is None:
            pin = _DirectoryPin(path, info)
            if pin.identity[0] != _process_pins[owned].identity[0]:
                pin.close()
                raise WorkspaceBoundaryError("Workspace directory volume changed")
            _process_pins[path] = pin
        else:
            pin.verify(info)


def validate_process_database(home, database):
    """Recheck owned SQLite paths immediately before/after connection opening.

    A startup lease is not a permanent filesystem safety certificate. Direct
    legacy/test imports without a process lease remain a separate migration
    boundary. This check detects observed replacements, not hostile swaps
    between the check and SQLite's own path-based opens.
    """
    global _process_workspace
    if _process_workspace is None:
        return
    owned, fd, root_identity, previous = _process_workspace
    if Path(home) != owned or Path(database) != owned / "pilotodin.sqlite3":
        raise WorkspaceBoundaryError("Database outside owned workspace")
    try:
        _validate_owned_ancestors(owned)
        current = _directory(owned)
        if not current.st_ino or not os.path.samestat(root_identity, current):
            raise WorkspaceBoundaryError("Workspace identity changed")
        _same_lock(fd, owned / LOCK_NAME)
        identity = _database_identity(owned, previous)
    except OSError as exc:
        raise WorkspaceBoundaryError("Workspace database unavailable or unsafe") from exc
    if previous is None and identity is not None:
        _process_workspace = (owned, fd, root_identity, identity)


def validate_process_write(home, path, *, directory=False, missing=False,
                           absent=False, expected=None):
    """Bounded observed-identity preflight, not atomic OS handle confinement.

    The active product lease is authoritative. Unleased in-process test/legacy
    callers still use their existing explicit fixture paths. Only known product
    write families are admitted; missing parents are never created here.
    """
    if _process_workspace is None:
        return None
    owned, fd, root_identity, _ = _process_workspace
    path = Path(path)
    if Path(home) != owned or not path.is_relative_to(owned) or path == owned:
        raise WorkspaceBoundaryError("Write outside owned workspace")
    parts = path.relative_to(owned).parts
    if any(part in ("", ".", "..") or ":" in part or part.endswith((" ", "."))
           for part in parts):
        raise WorkspaceBoundaryError("Invalid workspace write path")
    root = parts[0]
    root_file = (len(parts) == 1 and not directory and
                 (root in ("ai_settings.json", "ai_settings.tmp", "ai_secrets.dpapi",
                           "resource_preferences.json", "r03-benchmark.jsonl")
                  or re.fullmatch(r"\.(?:secrets|resource-policy)-[A-Za-z0-9_-]+\.tmp", root)))
    if not root_file and root not in ("datasets", "models", "export_tmp", "backend-temp"):
        raise WorkspaceBoundaryError("Unexpected workspace write path")
    if not root_file and len(parts) == 1 and not directory:
        raise WorkspaceBoundaryError("Expected workspace directory")
    try:
        _validate_owned_ancestors(owned)
        current = _directory(owned)
        if not current.st_ino or not os.path.samestat(root_identity, current):
            raise WorkspaceBoundaryError("Workspace identity changed")
        _same_lock(fd, owned / LOCK_NAME)
        # Recheck every existing parent without following redirects.
        for i in range(1, len(parts)):
            node = owned.joinpath(*parts[:i])
            info = _directory(node)
            if i == 1:
                _validate_owned_subdirectory(owned, root, info)
        try:
            info = path.lstat()
        except FileNotFoundError:
            if directory and len(parts) == 1 and root in _process_directories:
                raise WorkspaceBoundaryError("Owned workspace subdirectory disappeared")
            if absent or missing:
                return None
            raise
        if absent:
            raise WorkspaceBoundaryError("Workspace write destination already exists")
        if directory:
            info = _directory(path)
            if len(parts) == 1:
                _validate_owned_subdirectory(owned, root, info)
        else:
            _regular(info)
        if expected is not None and (not info.st_ino or not os.path.samestat(expected, info)):
            raise WorkspaceBoundaryError("Workspace write identity changed")
        return info
    except OSError as exc:
        raise WorkspaceBoundaryError("Workspace write path unavailable or unsafe") from exc


@contextmanager
def pin_process_model_directory(home, path, *, expected=None):
    """Hold only the new model directory for publication, not cleanup."""
    if _process_workspace is None:
        # Existing explicit in-process disposable fixture compatibility.
        yield lambda: None
        return
    path = Path(path)
    owned = _process_workspace[0]
    if path.parent != owned / "models":
        raise WorkspaceBoundaryError("Unexpected model directory")
    observed = validate_process_write(home, path, directory=True, expected=expected)
    pin = None
    try:
        try:
            pin = _DirectoryPin(path, observed)
            if pin.identity[0] != _process_pins[owned].identity[0]:
                raise WorkspaceBoundaryError("Workspace directory volume changed")
        except OSError as exc:
            raise WorkspaceBoundaryError("Model directory unavailable or unsafe") from exc

        def verify():
            current = validate_process_write(home, path, directory=True, expected=observed)
            try:
                pin.verify(current)
            except OSError as exc:
                raise WorkspaceBoundaryError("Model directory unavailable or unsafe") from exc

        verify()
        yield verify
    finally:
        if pin is not None:
            pin.close()


def configure_process_scratch(home):
    """Bind ordinary Python temporary-file defaults to owned backend scratch.

    PyInstaller extraction happens before Python entry; the Rust launcher
    must still supply its pre-spawn TEMP/TMP/TMPDIR. This cannot constrain
    every third-party native DLL or an explicitly overridden temp path.
    """
    global _process_scratch
    if _process_workspace is None:
        return
    path = Path(home) / "backend-temp"
    validate_process_write(home, path, directory=True, missing=True)
    try:
        path.mkdir(exist_ok=True)
    except OSError as exc:
        raise WorkspaceBoundaryError("Backend scratch unavailable or unsafe") from exc
    validate_process_write(home, path, directory=True)
    import tempfile
    for key in ("TEMP", "TMP", "TMPDIR", "JOBLIB_TEMP_FOLDER"):
        os.environ[key] = str(path)
    tempfile.tempdir = str(path)
    _process_scratch = path


def validate_process_scratch(home):
    """Check the configured scratch identity before accepting API work."""
    if _process_workspace is None:
        return
    path = _process_scratch
    if path is None:
        raise WorkspaceBoundaryError("Backend scratch is not admitted")
    validate_process_write(home, path, directory=True)
    import tempfile
    if tempfile.tempdir != str(path) or any(
        os.environ.get(key) != str(path)
        for key in ("TEMP", "TMP", "TMPDIR", "JOBLIB_TEMP_FOLDER")
    ):
        raise WorkspaceBoundaryError("Backend scratch configuration changed")
