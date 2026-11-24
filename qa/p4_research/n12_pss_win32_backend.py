"""G2.12 dormant Windows PSS API adapter. NOT connected to N12 or acceptance.

This module can name and sample handles of exactly one pre-verified WebView2
process, but cannot authenticate the writer-owned ORIGINAL handle, exclude
reuse across snapshots, or link a handle to Kernel-File FileObject/IRP.
No existing runner imports/starts the native backend. Any live use requires
fresh source-pinned one-use approval and an independently reviewed caller.
No owner paths, process IDs, handle values or OS errors in public receipts.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from contextlib import contextmanager
from dataclasses import dataclass
import ntpath
import os
import re
from typing import Iterator

from qa.p4_research.n12_pss_file_handle_candidates import MAX_HANDLES

# Source review against processsnapshot.h. Do NOT enable handle-name, VA clone,
# trace, thread, or type-specific capture flags.
PSS_CAPTURE_HANDLES = 0x00000004
PSS_CAPTURE_HANDLE_BASIC_INFORMATION = 0x00000010
PSS_FLAGS = PSS_CAPTURE_HANDLES | PSS_CAPTURE_HANDLE_BASIC_INFORMATION
PSS_WALK_HANDLES = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_DUP_HANDLE = 0x0040
PROCESS_RIGHTS = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE
PSS_HANDLE_HAVE_TYPE = 0x01
PSS_HANDLE_HAVE_NAME = 0x02
DUPLICATE_SAME_ACCESS = 0x00000002
FILE_TYPE_UNKNOWN = 0
FILE_TYPE_DISK = 1
FILE_TYPE_CHAR = 2
FILE_TYPE_PIPE = 3
ERROR_NO_MORE_ITEMS = 259
TYPE_NAME_MAX_BYTES = 128
CONSENT = "I_APPROVE_ONE_N12_PSS_FILE_HANDLE_FEASIBILITY"
SOURCE_ENV = "PILOTODIN_N12_APPROVED_SOURCE"
CONSENT_ENV = "PILOTODIN_N12_PSS_HANDLE_CONSENT"


class PssScopeError(Exception):
    """Fixed-label failure; never includes native paths or handle values."""


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


def _ticks(t: _FileTime) -> int:
    return (int(t.high) << 32) | int(t.low)


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("exit_status", ctypes.c_uint32), ("peb", ctypes.c_void_p),
        ("affinity", ctypes.c_size_t), ("base_priority", ctypes.c_int32),
        ("pid", ctypes.c_uint32), ("parent_pid", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class _ThreadInfo(ctypes.Structure):
    _fields_ = [
        ("exit_status", ctypes.c_uint32), ("teb", ctypes.c_void_p),
        ("pid", ctypes.c_uint32), ("tid", ctypes.c_uint32),
        ("affinity", ctypes.c_size_t), ("priority", ctypes.c_int32),
        ("base_priority", ctypes.c_int32), ("start_address", ctypes.c_void_p),
    ]


class _MutantInfo(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_int32), ("abandoned", ctypes.c_int32),
        ("owner_pid", ctypes.c_uint32), ("owner_tid", ctypes.c_uint32),
    ]


class _EventInfo(ctypes.Structure):
    _fields_ = [("manual_reset", ctypes.c_int32), ("signaled", ctypes.c_int32)]


class _SectionInfo(ctypes.Structure):
    _fields_ = [
        ("base_address", ctypes.c_void_p), ("allocation_attrs", ctypes.c_uint32),
        ("maximum_size", ctypes.c_int64),
    ]


class _SemaphoreInfo(ctypes.Structure):
    _fields_ = [("count", ctypes.c_int32), ("maximum", ctypes.c_int32)]


class _TypeInfo(ctypes.Union):
    _fields_ = [
        ("process", _ProcessInfo), ("thread", _ThreadInfo),
        ("mutant", _MutantInfo), ("event", _EventInfo),
        ("section", _SectionInfo), ("semaphore", _SemaphoreInfo),
    ]


class _HandleEntry(ctypes.Structure):
    """PSS_HANDLE_ENTRY C layout: pointers are NEVER public evidence."""
    _fields_ = [
        ("handle", ctypes.c_void_p), ("flags", ctypes.c_uint32),
        ("object_type", ctypes.c_int32), ("capture_time", _FileTime),
        ("attributes", ctypes.c_uint32), ("granted_access", ctypes.c_uint32),
        ("handle_count", ctypes.c_uint32), ("pointer_count", ctypes.c_uint32),
        ("paged_pool_charge", ctypes.c_uint32),
        ("nonpaged_pool_charge", ctypes.c_uint32),
        ("creation_time", _FileTime),
        ("type_name_bytes", ctypes.c_uint16), ("type_name", ctypes.c_void_p),
        ("object_name_bytes", ctypes.c_uint16), ("object_name", ctypes.c_void_p),
        ("type_info", _TypeInfo),
    ]


def _require_one_use_scope(env: object) -> None:
    """A future approved hosted capture ONLY. No current workflow sets this."""
    if type(env) is not dict or os.name != "nt":
        raise PssScopeError("NATIVE_PSS_SCOPE_NOT_AUTHORIZED")
    required = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Windows",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REF_NAME": "feature/live-dev-workspace-20261023",
        CONSENT_ENV: CONSENT,
    }
    if any(env.get(k) != v for k, v in required.items()):
        raise PssScopeError("NATIVE_PSS_SCOPE_NOT_AUTHORIZED")
    sha = env.get(SOURCE_ENV)
    if (type(sha) is not str or re.fullmatch(r"[0-9a-f]{40}", sha) is None
            or env.get("PILOTODIN_N12_PSS_REVIEWED_SHA") != sha):
        raise PssScopeError("NATIVE_PSS_SOURCE_NOT_VERIFIED")
    # These are necessary, NOT sufficient: caller must still prove process
    # ancestry, transient ETW loss and file object identity. A private
    # fresh-marker/source-pinning reviewer must be added before any activation.


def _binding(dll: object, name: str, returns: object, args: list) -> object:
    function = getattr(dll, name)
    function.restype = returns
    function.argtypes = args
    return function


@dataclass(frozen=True)
class _PrivateSnapshot:
    handle: int
    tick: int


@dataclass(frozen=True, repr=False)
class _PrivateDiskCandidates:
    """Private, ephemeral PSS handle numbers. NEVER serialize or log instances.

    A disk classification is not a claim about the original object at write
    time. PSS values may be reused before DuplicateHandle can inspect them.
    """
    handles: tuple[int, ...]
    snapshot_tick: int
    total_rows: int
    unclassified_rows: int

    def __str__(self) -> str:
        return "<G2.16 private handle candidates, no public receipt>"

    __repr__ = __str__


class _Win32PssApi:
    """Direct Win32 ABI, constructed only AFTER strict scope authorization."""

    def __init__(self) -> None:
        # Not referenced at import time or on synthetic CI.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        ptr = ctypes.c_void_p
        dword = ctypes.c_uint32
        pdword = ctypes.POINTER(dword)
        pptr = ctypes.POINTER(ptr)
        ptime = ctypes.POINTER(_FileTime)
        self.open_process_fn = _binding(kernel, "OpenProcess", ptr, [dword, ctypes.c_int32, dword])
        self.close_handle_fn = _binding(kernel, "CloseHandle", ctypes.c_int32, [ptr])
        self.process_id_fn = _binding(kernel, "GetProcessId", dword, [ptr])
        self.process_times_fn = _binding(
            kernel, "GetProcessTimes", ctypes.c_int32,
            [ptr, ptime, ptime, ptime, ptime])
        self.image_fn = _binding(
            kernel, "QueryFullProcessImageNameW", ctypes.c_int32,
            [ptr, dword, ptr, pdword])
        self.now_fn = _binding(kernel, "GetSystemTimeAsFileTime", None, [ptime])
        self.get_current_process_fn = _binding(kernel, "GetCurrentProcess", ptr, [])
        self.duplicate_fn = _binding(
            kernel, "DuplicateHandle", ctypes.c_int32,
            [ptr, ptr, ptr, pptr, dword, ctypes.c_int32, dword])
        self.file_type_fn = _binding(kernel, "GetFileType", dword, [ptr])
        self.capture_fn = _binding(
            kernel, "PssCaptureSnapshot", dword, [ptr, dword, dword, pptr])
        self.free_fn = _binding(kernel, "PssFreeSnapshot", dword, [ptr, ptr])
        self.marker_create_fn = _binding(kernel, "PssWalkMarkerCreate", dword, [ptr, pptr])
        self.marker_free_fn = _binding(kernel, "PssWalkMarkerFree", dword, [ptr])
        self.walk_fn = _binding(
            kernel, "PssWalkSnapshot", dword,
            [ptr, dword, ptr, ctypes.POINTER(_HandleEntry), dword])

    def open_process(self, pid: int) -> int:
        raw = self.open_process_fn(PROCESS_RIGHTS, 0, pid)
        if not raw:
            raise PssScopeError("TARGET_PROCESS_OPEN_UNVERIFIED")
        return int(raw)

    def close_process(self, handle: int) -> None:
        if not self.close_handle_fn(handle):
            raise PssScopeError("TARGET_PROCESS_CLOSE_UNVERIFIED")

    @contextmanager
    def duplicate(self, process_handle: int, original_handle: int) -> Iterator[int]:
        """Duplicate one preselected foreign handle into THIS process only.

        DUPLICATE_CLOSE_SOURCE must never be set: that would close WebView2's
        original handle. Even partial/native-error returns close any LOCAL
        duplicate before reporting a fixed-label blocker.
        """
        if (type(process_handle) is not int or process_handle <= 0
                or type(original_handle) is not int
                or not 0 < original_handle < 2**64):
            raise PssScopeError("DUPLICATE_HANDLE_SCOPE_UNVERIFIED")
        duplicate = ctypes.c_void_p()
        try:
            success = self.duplicate_fn(
                process_handle, original_handle, self.get_current_process_fn(),
                ctypes.byref(duplicate), 0, 0, DUPLICATE_SAME_ACCESS)
            if not success or not duplicate.value:
                raise PssScopeError("DUPLICATE_HANDLE_UNAVAILABLE")
            yield int(duplicate.value)
        finally:
            if duplicate.value and not self.close_handle_fn(int(duplicate.value)):
                raise PssScopeError("DUPLICATE_HANDLE_CLEANUP_UNVERIFIED")

    def file_type(self, local_handle: int) -> tuple[int, int]:
        """No file contents, filename resolution, or metadata/name queries."""
        if type(local_handle) is not int or local_handle <= 0:
            raise PssScopeError("FILE_TYPE_SCOPE_UNVERIFIED")
        ctypes.set_last_error(0)  # Save true Win32 last-error through WinDLL.
        kind = int(self.file_type_fn(local_handle))
        error = int(ctypes.get_last_error())
        return kind, error

    def identity(self, handle: int) -> tuple[int, int, str]:
        pid = self.process_id_fn(handle)
        if not pid:
            raise PssScopeError("TARGET_PROCESS_IDENTITY_UNVERIFIED")
        created, exited, kernel, user = (_FileTime() for _ in range(4))
        if not self.process_times_fn(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel), ctypes.byref(user)):
            raise PssScopeError("TARGET_PROCESS_IDENTITY_UNVERIFIED")
        # QueryFullProcessImageNameW returns a full DOS image path.
        buffer = ctypes.create_unicode_buffer(32768)
        count = ctypes.c_uint32(len(buffer))
        if not self.image_fn(handle, 0, ctypes.cast(buffer, ctypes.c_void_p),
                             ctypes.byref(count)) or count.value == 0:
            raise PssScopeError("TARGET_PROCESS_IMAGE_UNVERIFIED")
        name = ntpath.basename(buffer.value).casefold()
        return (int(pid), _ticks(created), name)

    def current_ticks(self) -> int:
        time = _FileTime()
        self.now_fn(ctypes.byref(time))
        return _ticks(time)

    def capture(self, process_handle: int) -> _PrivateSnapshot:
        start_tick = self.current_ticks()
        handle = ctypes.c_void_p()
        result = self.capture_fn(process_handle, PSS_FLAGS, 0, ctypes.byref(handle))
        if result or not handle.value:
            # A failed API call should normally clear HPSS. If it returns a
            # non-null partial snapshot, attempt to free that local handle
            # instead of abandoning it. Either failure remains BLOCKED.
            if handle.value:
                self.free(int(handle.value))
            raise PssScopeError("PSS_CAPTURE_INCOMPLETE")
        end_tick = self.current_ticks()
        # The timestamp is a caller clock observation, NOT an authenticated
        # FILETIME of the original handle's life at the write request.
        if end_tick < start_tick or end_tick - start_tick > 10_000_000:
            self.free(int(handle.value))
            raise PssScopeError("PSS_CAPTURE_CLOCK_UNVERIFIED")
        return _PrivateSnapshot(int(handle.value), end_tick)

    def free(self, snapshot: int) -> None:
        # PssFreeSnapshot requires current-process pseudo handle for a
        # locally captured snapshot. Do not call CloseHandle on HPSS.
        if self.free_fn(self.get_current_process_fn(), snapshot):
            raise PssScopeError("PSS_SNAPSHOT_CLEANUP_UNVERIFIED")

    def marker_open(self) -> int:
        handle = ctypes.c_void_p()
        if self.marker_create_fn(None, ctypes.byref(handle)) or not handle.value:
            raise PssScopeError("PSS_WALK_MARKER_UNAVAILABLE")
        return int(handle.value)

    def marker_close(self, marker: int) -> None:
        if self.marker_free_fn(marker):
            raise PssScopeError("PSS_WALK_MARKER_CLEANUP_UNVERIFIED")

    def walk_next(self, snapshot: int, marker: int) -> dict | None:
        row = _HandleEntry()
        rc = self.walk_fn(snapshot, PSS_WALK_HANDLES, marker,
                          ctypes.byref(row), ctypes.sizeof(row))
        if rc == ERROR_NO_MORE_ITEMS:
            return None
        if rc:
            raise PssScopeError("PSS_HANDLE_WALK_INCOMPLETE")
        if (row.flags & PSS_HANDLE_HAVE_NAME or row.object_name_bytes
                or row.object_name):
            # The requested capture must never return private object names.
            raise PssScopeError("PSS_PRIVATE_NAME_CAPTURE_UNEXPECTED")
        if not row.handle or row.flags & ~0x0F:
            raise PssScopeError("PSS_HANDLE_ENTRY_INVALID")
        if row.type_name_bytes > TYPE_NAME_MAX_BYTES or row.type_name_bytes % 2:
            raise PssScopeError("PSS_HANDLE_TYPE_UNVERIFIED")
        type_name = ""
        if row.flags & PSS_HANDLE_HAVE_TYPE:
            if not row.type_name or not row.type_name_bytes:
                raise PssScopeError("PSS_HANDLE_TYPE_UNVERIFIED")
            # Pointer is valid only while this walk marker remains alive.
            type_name = ctypes.wstring_at(
                row.type_name, row.type_name_bytes // 2)
        # No object name, raw process image, private path or ETW pointer.
        return {
            "handle": int(row.handle), "type_name": type_name,
            "object_type": int(row.object_type), "flags": int(row.flags),
        }


class ScopedPssApiAdapter:
    """One-process, two-snapshot facility. No source activates it today."""

    def __init__(self, api: object) -> None:
        self._api = api

    @contextmanager
    def open_verified_child(self, *, pid: int, birth: int) -> Iterator[int]:
        if type(pid) is not int or pid <= 0 or type(birth) is not int or birth <= 0:
            raise PssScopeError("TARGET_PROCESS_SCOPE_INVALID")
        handle = self._api.open_process(pid)
        try:
            actual = self._api.identity(handle)
            if (type(actual) is not tuple or len(actual) != 3
                    or actual != (pid, birth, "msedgewebview2.exe")):
                raise PssScopeError("TARGET_PROCESS_IDENTITY_UNVERIFIED")
            yield handle
        finally:
            self._api.close_process(handle)

    @contextmanager
    def snapshot(self, handle: int) -> Iterator[_PrivateSnapshot]:
        captured = self._api.capture(handle)
        try:
            if (not isinstance(captured, _PrivateSnapshot)
                    or type(captured.tick) is not int or captured.tick <= 0
                    or type(captured.handle) is not int or captured.handle <= 0):
                raise PssScopeError("PSS_CAPTURE_INCOMPLETE")
            yield captured
        finally:
            # Also free a snapshot if its metadata is unusable.
            if isinstance(captured, _PrivateSnapshot) and captured.handle:
                self._api.free(captured.handle)

    def collect_private_rows(self, snapshot: _PrivateSnapshot) -> list[dict]:
        marker = self._api.marker_open()
        rows = []
        try:
            while True:
                result = self._api.walk_next(snapshot.handle, marker)
                if result is None:
                    return rows
                if len(rows) >= MAX_HANDLES:
                    raise PssScopeError("PSS_SNAPSHOT_ROW_LIMIT")
                if (type(result) is not dict or
                        set(result) != {"handle", "type_name", "object_type", "flags"}):
                    raise PssScopeError("PSS_ROW_SCHEMA_UNVERIFIED")
                rows.append(result)
        finally:
            self._api.marker_close(marker)

    def collect_private_disk_candidates(self, *, pid: int, birth: int) -> _PrivateDiskCandidates:
        """Legacy dormant PID-opened source candidate, not the retained HANDLE.

        The new process handle is verified by PID/birth/image, but is NOT the
        original process query handle retained by the N12 child observer.
        """
        with self.open_verified_child(pid=pid, birth=birth) as process:
            return self._disk_candidates_on_process_handle(process)

    def collect_from_retained_original_process(
            self, *, process_handle: int, pid: int, birth: int,
            acquisition_rights: int) -> _PrivateDiskCandidates:
        """Classify using a caller-owned, still-open original process HANDLE.

        Rights declaration is necessary but NOT independently validated;
        Win32 enforces them. Current N12 observer retains only query 0x1000
        handles, so those do not qualify for DuplicateHandle 0x1040 here.
        The caller retains ownership and MUST close the original HANDLE.
        There is no live caller, no original FileObject/IRP/path proof.
        """
        if (type(process_handle) is not int or process_handle <= 0
                or type(pid) is not int or pid <= 0
                or type(birth) is not int or birth <= 0
                or type(acquisition_rights) is not int
                or acquisition_rights != PROCESS_RIGHTS):
            raise PssScopeError("RETAINED_PROCESS_SCOPE_OR_RIGHTS_UNVERIFIED")
        expected = (pid, birth, "msedgewebview2.exe")
        if self._api.identity(process_handle) != expected:
            raise PssScopeError("TARGET_PROCESS_IDENTITY_UNVERIFIED")
        result = self._disk_candidates_on_process_handle(process_handle)
        if self._api.identity(process_handle) != expected:
            raise PssScopeError("TARGET_PROCESS_IDENTITY_UNVERIFIED")
        return result

    def _disk_candidates_on_process_handle(self, process: int) -> _PrivateDiskCandidates:
        """No names, system scans, original handle closure or acceptance."""
        with self.snapshot(process) as capture:
            rows = self.collect_private_rows(capture)
            if not rows:
                raise PssScopeError("PSS_SNAPSHOT_ROW_LIMIT")
            seen = set()
            private_disk = []
            unclassified = 0
            for row in rows:
                if (type(row) is not dict
                        or set(row) != {"handle", "type_name",
                                        "object_type", "flags"}):
                    raise PssScopeError("PSS_ROW_SCHEMA_UNVERIFIED")
                handle = row["handle"]
                flags = row["flags"]
                if (type(handle) is not int or not 0 < handle < 2**64
                        or handle in seen
                        or type(flags) is not int or flags & ~0x0F
                        or flags & PSS_HANDLE_HAVE_NAME
                        or type(row["type_name"]) is not str
                        or type(row["object_type"]) is not int):
                    raise PssScopeError("PSS_ROW_SCHEMA_UNVERIFIED")
                seen.add(handle)
                with self._api.duplicate(process, handle) as local:
                    kind, error = self._api.file_type(local)
                    if type(kind) is not int or type(error) is not int:
                        raise PssScopeError("FILE_TYPE_SCOPE_UNVERIFIED")
                    if kind == FILE_TYPE_UNKNOWN:
                        unclassified += 1
                    elif error != 0 or kind not in (
                            FILE_TYPE_DISK, FILE_TYPE_CHAR, FILE_TYPE_PIPE):
                        raise PssScopeError("FILE_TYPE_SCOPE_UNVERIFIED")
                    elif kind == FILE_TYPE_DISK:
                        private_disk.append(handle)
            # Ephemeral original handle numbers, NOT kernel FileObject
            # identity. Numeric handle reuse after snapshot is unresolved.
            return _PrivateDiskCandidates(
                tuple(private_disk), capture.tick, len(rows), unclassified)


def prepare_native_backend(env: object) -> ScopedPssApiAdapter:
    """Dormant until a NEW approved source-pinned native workflow exists.

    This function is NEVER called by current product, N12 or test workflows.
    """
    _require_one_use_scope(env)
    return ScopedPssApiAdapter(_Win32PssApi())


def redacted_blocker(reason: str) -> dict:
    """Only fixed labels can cross the synthetic/native boundary."""
    allowed = frozenset({
        "NATIVE_PSS_SCOPE_NOT_AUTHORIZED", "NATIVE_PSS_SOURCE_NOT_VERIFIED",
        "TARGET_PROCESS_SCOPE_INVALID", "TARGET_PROCESS_IDENTITY_UNVERIFIED",
        "TARGET_PROCESS_OPEN_UNVERIFIED", "TARGET_PROCESS_CLOSE_UNVERIFIED",
        "TARGET_PROCESS_IMAGE_UNVERIFIED", "PSS_CAPTURE_INCOMPLETE",
        "PSS_CAPTURE_CLOCK_UNVERIFIED", "PSS_SNAPSHOT_CLEANUP_UNVERIFIED",
        "PSS_WALK_MARKER_UNAVAILABLE", "PSS_WALK_MARKER_CLEANUP_UNVERIFIED",
        "PSS_HANDLE_WALK_INCOMPLETE", "PSS_PRIVATE_NAME_CAPTURE_UNEXPECTED",
        "PSS_HANDLE_ENTRY_INVALID", "PSS_HANDLE_TYPE_UNVERIFIED",
        "PSS_SNAPSHOT_ROW_LIMIT", "PSS_ROW_SCHEMA_UNVERIFIED",
        "DUPLICATE_HANDLE_SCOPE_UNVERIFIED", "DUPLICATE_HANDLE_UNAVAILABLE",
        "DUPLICATE_HANDLE_CLEANUP_UNVERIFIED", "FILE_TYPE_SCOPE_UNVERIFIED",
    })
    return {
        "scope": "g2-12-unactivated-windows-pss-candidate",
        "status": "BLOCKED",
        "blocker": reason if reason in allowed else "UNVERIFIED",
        "original_writer_file_handle": "NOT_VERIFIED",
        "fileobject_etw_correlation": "NOT_ESTABLISHED",
        "handle_reuse_excluded": False,
        "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }
