"""C4 bounded settings foundation; no storage, network or DPAPI side effects on import.

The service must supply its trusted workspace path checker. Production wiring
must require the owned lease; disposable tests supply an explicit adapter.
Observed identity checks and fsync are not hostile-race or power-loss proof.
All three existing settings services use the fixed-target store.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from threading import RLock

SETTINGS_LOCK = RLock()
PROVIDERS = ("gemini", "groq", "openrouter")
PREFERENCES = (*PROVIDERS, "auto", "local", "ollama")
RESOURCE_MODES = ("adaptive", "low_memory", "performance")
MODEL_NAME = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*"
    r"(?::[A-Za-z0-9][A-Za-z0-9_.-]*)?$"
)
# Existing writers escape non-ASCII by default. Three 512-character keys
# can occupy >16 KiB when each character escapes as a surrogate pair.
# Preserve that syntactically valid legacy envelope; actual DPAPI output
# capacity remains a distinct Windows verification boundary.
SECRET_PLAINTEXT_LIMIT = 24 * 1024
SECRET_CIPHERTEXT_LIMIT = 48 * 1024


class Kind(Enum):
    RESOURCE = ("resource_preferences.json", 4 * 1024, ".resource-policy-")
    AI = ("ai_settings.json", 16 * 1024, ".ai-settings-")
    SECRET = ("ai_secrets.dpapi", 64 * 1024, ".secrets-")

    @property
    def filename(self):
        return self.value[0]

    @property
    def limit(self):
        return self.value[1]

    @property
    def prefix(self):
        return self.value[2]


class InvalidSettings(ValueError):
    """Fixed, path/value-free validation failure."""


class SettingsIOError(OSError):
    """Fixed, path/value-free read/identity failure."""


class SettingsWriteError(OSError):
    """No retry should be inferred from an uncertain acknowledgement."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _invalid():
    return InvalidSettings("Invalid or unsupported saved settings")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def _constant(_):
    raise _invalid()


def strict_object(raw: bytes, limit: int) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise _invalid() from None
    if type(value) is not dict:
        raise _invalid()
    return value


def ai_defaults():
    # A fresh object, including the nested mutable values.
    return {
        "cloud_enabled": False, "share_aggregates": False,
        "auto_insights": False, "provider_order": list(PROVIDERS),
        "timeout_seconds": 20, "preferred_provider": "auto",
        "workspace_preferences": {}, "intelligence_mode": "hybrid",
        "local_model": "qwen3:1.7b", "local_model_enabled": True,
        "local_timeout_seconds": 60,
    }


def validate_resource(value):
    if (type(value) is not dict or set(value) != {"schema_version", "mode"}
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or type(value["mode"]) is not str
            or value["mode"] not in RESOURCE_MODES):
        raise _invalid()
    return dict(value)


def _choice(value, allowed):
    return type(value) is str and value in allowed


def _integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def validate_ai(value):
    defaults = ai_defaults()
    if type(value) is not dict or not value.keys() <= defaults.keys():
        raise _invalid()
    cfg = {**defaults, **value}
    if any(type(cfg[k]) is not bool for k in (
        "cloud_enabled", "share_aggregates", "auto_insights",
        "local_model_enabled",
    )):
        raise _invalid()
    if cfg["cloud_enabled"] and not cfg["share_aggregates"]:
        raise _invalid()
    order = cfg["provider_order"]
    if (type(order) is not list or len(order) != len(PROVIDERS)
            or any(not _choice(v, PROVIDERS) for v in order)
            or len(set(order)) != len(PROVIDERS)):
        raise _invalid()
    if not _integer(cfg["timeout_seconds"], 3, 45):
        raise _invalid()
    if not _integer(cfg["local_timeout_seconds"], 5, 180):
        raise _invalid()
    if not _choice(cfg["preferred_provider"], PREFERENCES):
        raise _invalid()
    if not _choice(cfg["intelligence_mode"], ("hybrid", "local", "cloud")):
        raise _invalid()
    model = cfg["local_model"]
    if type(model) is not str or len(model) > 80 or not MODEL_NAME.fullmatch(model):
        raise _invalid()
    workspace = cfg["workspace_preferences"]
    if (type(workspace) is not dict or len(workspace) > 12
            or any(type(k) is not str or len(k) > 40
                   or not _choice(v, PREFERENCES) for k, v in workspace.items())):
        raise _invalid()
    cfg["provider_order"] = list(order)
    cfg["workspace_preferences"] = dict(workspace)
    return cfg


def validate_keys(value):
    if type(value) is not dict or not value.keys() <= set(PROVIDERS):
        raise _invalid()
    if any(type(key) is not str or not 12 <= len(key) <= 512
           or any(char.isspace() for char in key) for key in value.values()):
        raise _invalid()
    return dict(value)


def decode(kind, raw, *, decrypt=None):
    if not isinstance(kind, Kind):
        raise _invalid()
    if kind is Kind.RESOURCE:
        return validate_resource(strict_object(raw, kind.limit))
    if kind is Kind.AI:
        return validate_ai(strict_object(raw, kind.limit))
    if type(raw) is not bytes or not 0 < len(raw) <= kind.limit or decrypt is None:
        raise _invalid()
    try:
        encrypted = base64.b64decode(raw, validate=True)
        if not 0 < len(encrypted) <= SECRET_CIPHERTEXT_LIMIT:
            raise _invalid()
        plain = decrypt(encrypted)
        return validate_keys(strict_object(plain, SECRET_PLAINTEXT_LIMIT))
    except Exception:
        # Do not expose adapter errors, ciphertext, plaintext or paths.
        raise _invalid() from None


def _redirected(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def _regular(info):
    if (_redirected(info) or not stat.S_ISREG(info.st_mode)
            or not info.st_ino or info.st_nlink != 1):
        raise SettingsIOError("Settings file identity unavailable or unsafe")


def _same_stat(first, second):
    return bool(first.st_ino and second.st_ino and os.path.samestat(first, second))


def _unchanged(first, second):
    return (_same_stat(first, second) and first.st_size == second.st_size
            and first.st_mtime_ns == second.st_mtime_ns
            and first.st_ctime_ns == second.st_ctime_ns)


@dataclass(frozen=True, repr=False)
class _Snapshot:
    data: bytes
    identity: os.stat_result


def _same_snapshot(first, second):
    if first is None or second is None:
        return first is second
    return _unchanged(first.identity, second.identity) and first.data == second.data


class Store:
    """Fixed-target replacement, scoped to a caller-admitted existing root.

    The checker is mandatory. It must validate the production workspace lease,
    pins and admitted filename; test adapters are intentionally explicit.
    Nothing here creates the root, modifies other files or sweeps old stages.
    """

    def __init__(self, home, *, check_path):
        self.home = Path(home)
        if not self.home.is_absolute() or not callable(check_path):
            raise SettingsIOError("Explicit admitted settings root required")
        self._check = check_path
        self._identity = self._root()

    def _root(self):
        try:
            info = self.home.lstat()
            if _redirected(info) or not stat.S_ISDIR(info.st_mode) or not info.st_ino:
                raise SettingsIOError("Settings root identity unavailable or unsafe")
            return info
        except (OSError, ValueError):
            raise SettingsIOError("Settings root identity unavailable or unsafe") from None

    def _verify_root(self):
        if not _same_stat(self._identity, self._root()):
            raise SettingsIOError("Settings root identity changed")

    def _admit(self, path, **options):
        self._verify_root()
        if path.parent != self.home:
            raise SettingsIOError("Settings path outside admitted root")
        try:
            self._check(path, **options)
        except Exception:
            raise SettingsIOError("Settings path unavailable or unsafe") from None
        self._verify_root()

    def _read_path(self, path, limit):
        self._verify_root()
        self._admit(path, missing=True)
        try:
            before = path.lstat()
        except FileNotFoundError:
            self._admit(path, absent=True)
            try:
                path.lstat()
            except FileNotFoundError:
                return None
            raise SettingsIOError("Settings target changed during observation")
        _regular(before)
        if before.st_size > limit:
            raise InvalidSettings("Saved settings exceed the size limit")
        self._admit(path, expected=before)
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                 | getattr(os, "O_CLOEXEC", 0))
        fd = os.open(path, flags)
        try:
            fp = os.fdopen(fd, "rb")
        except BaseException:
            os.close(fd)
            raise
        with fp:
            opened = os.fstat(fp.fileno())
            _regular(opened)
            if not _unchanged(before, opened):
                raise SettingsIOError("Settings file identity changed")
            raw = fp.read(limit + 1)
            after = os.fstat(fp.fileno())
            _regular(after)
            if len(raw) > limit:
                raise InvalidSettings("Saved settings exceed the size limit")
            if not _unchanged(opened, after) or len(raw) != after.st_size:
                raise SettingsIOError("Settings file changed during read")
            self._admit(path, expected=after)
            named = path.lstat()
            _regular(named)
            if not _unchanged(after, named):
                raise SettingsIOError("Settings file changed during read")
        self._verify_root()
        return _Snapshot(raw, after)

    def _read(self, path, limit):
        try:
            return self._read_path(path, limit)
        except InvalidSettings:
            raise
        except Exception:
            raise SettingsIOError("Settings read unavailable or unsafe") from None

    def check_target(self, kind):
        """Check the admitted root/target without reading or creating bytes."""
        if not isinstance(kind, Kind):
            raise _invalid()
        with SETTINGS_LOCK:
            self._admit(self.home / kind.filename, missing=True)

    def read(self, kind, *, decrypt=None):
        if not isinstance(kind, Kind):
            raise _invalid()
        with SETTINGS_LOCK:
            snapshot = self._read(self.home / kind.filename, kind.limit)
            if snapshot is None:
                return None
            return decode(kind, snapshot.data, decrypt=decrypt)

    def _cleanup(self, path, identity):
        if path is None or identity is None:
            return False
        try:
            self._admit(path, missing=True, expected=identity)
            try:
                actual = path.lstat()
            except FileNotFoundError:
                return True
            _regular(actual)
            if not _same_stat(actual, identity):
                return False
            path.unlink()
            return True
        except Exception:
            # Never remove a foreign, redirected or unknown stage.
            return False

    def replace(self, kind, raw, *, decrypt=None):
        """Validate old/new bytes, fsync stage, fence target and verify readback.

        Return the confirmed parsed new value only after exact readback.
        On error, distinguish observed precommit failure from ambiguity.
        No automatic recovery, retry, backup, migration or deletion.
        """
        if not isinstance(kind, Kind):
            raise _invalid()
        decode(kind, raw, decrypt=decrypt)
        target = self.home / kind.filename
        with SETTINGS_LOCK:
            old = self._read(target, kind.limit)
            if old is not None:
                decode(kind, old.data, decrypt=decrypt)
            stage = None
            identity = None
            attempted = False
            replaced = False
            try:
                self._admit(target, missing=True,
                            **({"expected": old.identity} if old is not None else {"absent": True}))
                fd, name = tempfile.mkstemp(prefix=kind.prefix, suffix=".tmp", dir=self.home)
                stage = Path(name)
                try:
                    identity = os.fstat(fd)
                    _regular(identity)
                    self._admit(stage, expected=identity)
                    fp = os.fdopen(fd, "wb")
                except BaseException:
                    os.close(fd)
                    raise
                with fp:
                    if fp.write(raw) != len(raw):
                        raise SettingsIOError("Short settings write")
                    fp.flush()
                    os.fsync(fp.fileno())
                    flushed = os.fstat(fp.fileno())
                    _regular(flushed)
                    if not _same_stat(identity, flushed) or flushed.st_size != len(raw):
                        raise SettingsIOError("Settings stage identity changed")
                prepared = self._read(stage, kind.limit)
                if (prepared is None or not _same_stat(identity, prepared.identity)
                        or prepared.data != raw):
                    raise SettingsIOError("Settings stage verification failed")
                # Re-read contents as well as identity: same-inode edits must
                # not be silently overwritten.
                current = self._read(target, kind.limit)
                if not _same_snapshot(old, current):
                    raise SettingsIOError("Settings target changed before replacement")
                self._admit(target, **(
                    {"expected": old.identity} if old is not None else {"absent": True}
                ))
                self._admit(stage, expected=prepared.identity)
                attempted = True
                os.replace(stage, target)
                replaced = True
                saved = self._read(target, kind.limit)
                if (saved is None or not _same_stat(identity, saved.identity)
                        or saved.data != raw):
                    raise SettingsIOError("Settings replacement verification failed")
                return decode(kind, saved.data, decrypt=decrypt)
            except Exception:
                code = "settings_not_committed"
                if attempted:
                    # Even a raised replace can have committed. Only classify
                    # a refusal when both the old target and owned stage remain.
                    code = "settings_commit_uncertain"
                    if not replaced:
                        try:
                            current = self._read(target, kind.limit)
                            pending = self._read(stage, kind.limit)
                            if (_same_snapshot(old, current) and pending is not None
                                    and _same_stat(identity, pending.identity)
                                    and pending.data == raw):
                                code = "settings_not_committed"
                        except Exception:
                            pass
                if stage is not None and not replaced:
                    if not self._cleanup(stage, identity) and code == "settings_not_committed":
                        code = "settings_not_committed_stage_retained"
                raise SettingsWriteError(code) from None

def owned_store(home):
    """Product adapter: require the live cooperating workspace lease.

    No environment/test-mode bypass. Disposable callers must explicitly
    inject a Store with a separate test-only checker.
    """
    try:
        from .workspace_boundary import validate_process_write
    except ImportError:
        from workspace_boundary import validate_process_write

    def check(path, **options):
        return validate_process_write(home, path, require_owned=True, **options)

    return Store(home, check_path=check)
