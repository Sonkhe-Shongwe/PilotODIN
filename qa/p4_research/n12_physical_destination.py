"""P4 R02.5 supplemental, default-off physical-destination source candidate.

NO startup hooks, filesystem opens/writes, application launch, collection, or
acceptance credit. Original-file handles and independently corroborated ETW
identity MUST be provided by a separately authorised collector. A result from
this module is never a strict N12 acceptance verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Literal

# Never infer a filesystem-specific directory case mode from path spelling.
# NTFS directories can be case-sensitive. A final path alone cannot justify
# case-insensitive parent/child identity, even for ASCII-only differences.
_RESERVED_DEVICE = re.compile(
    r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?$",
    re.IGNORECASE,
)
_INVALID_WIN_NAME_CHARS = frozenset('<>"|?*')

Status = Literal[
    "BLOCKED", "CONTAINED_CANDIDATE_ONLY", "OUTSIDE_CANDIDATE_ONLY"
]


@dataclass(frozen=True)
class PrivateHandlePath:
    """Private, separately observed path for an already-held file handle.

    The caller must independently attest provenance. Neither a process handle,
    reopened-by-name handle, nor a UDF string is a qualifying original file
    handle. Raw paths must never enter public diagnostics.
    """
    final_path: str = field(repr=False)
    volume_serial: int = field(repr=False)
    acquisition: str = field(repr=False)  # "original_file_handle" / "permitted_root_handle"


@dataclass(frozen=True)
class Corroboration:
    original_writer_process_handle: bool
    complete_original_writer_lifetime: bool
    same_original_file_handle: bool
    etw_fileobject_and_irp_join: bool
    successful_write_completion: bool
    request_time_path_epoch: bool
    capture_loss_independently_clear: bool
    browser_identity_complete: bool
    no_unresolved_reparse_or_alias: bool

    def complete(self) -> bool:
        return all(value is True for value in vars(self).values())


@dataclass(frozen=True)
class PrivateAssessment:
    status: Status
    reason: str
    # Never expose raw source/private paths or numerical handle identities.
    def public_receipt(self) -> dict[str, str]:
        return {
            "physical_destination_candidate": self.status,
            "reason": self.reason,
            "native_N12_acceptance": "NOT_EVALUATED",
            "file_mutation_acceptance": "NOT_EVALUATED",
        }


def _blocked(reason: str) -> PrivateAssessment:
    return PrivateAssessment("BLOCKED", reason)


def _strict_dos_components(path: str) -> tuple[str, tuple[str, ...]] | None:
    """Parse a narrow unambiguous subset of *already final* Windows paths.

    Not a symlink resolver or a general-purpose Windows path normalizer.
    UNC, volume GUID, GLOBALROOT and device aliases are rejected rather than
    incorrectly treated as in-scope. No dot or parent traversal normalization.
    """
    if not isinstance(path, str) or not path or len(path) > 32767:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in path) or "/" in path:
        return None
    if path.startswith("\\\\?\\"):
        path = path[4:]
    elif path.startswith("\\\\") or path.startswith("\\?\\"):
        return None
    if not re.fullmatch(r"[A-Za-z]:\\.*", path, flags=re.DOTALL):
        return None
    drive = path[:2].casefold()
    tail = path[3:]
    if not tail:
        return drive, ()
    pieces = tail.split("\\")
    if any((not p or p in (".", "..") or p.endswith((".", " ")) or ":" in p
            or any(ch in _INVALID_WIN_NAME_CHARS for ch in p)
            or _RESERVED_DEVICE.fullmatch(p)) for p in pieces):
        return None
    return drive, tuple(pieces)


def assess_private_destination(
    *,
    write_target: PrivateHandlePath,
    allowed_roots: tuple[PrivateHandlePath, ...],
    request_time_path: str,
    corroboration: Corroboration,
) -> PrivateAssessment:
    """Produce a supplemental *candidate* only; never override strict N12.

    Every corroboration flag must come from independent trusted capture, not
    from a model or public summary. The actual request-time path must agree
    with the original-handle final path in this conservative subset. A blocked
    result must not be converted to permission or ignored in strict auditing.
    """
    if not corroboration.complete():
        return _blocked("INCOMPLETE_INDEPENDENT_CORROBORATION")
    if write_target.acquisition != "original_file_handle":
        return _blocked("NOT_AN_ORIGINAL_FILE_HANDLE")
    if not allowed_roots or any(r.acquisition != "permitted_root_handle" for r in allowed_roots):
        return _blocked("PERMITTED_ROOT_HANDLE_EVIDENCE_MISSING")
    if (not isinstance(write_target.volume_serial, int) or
        isinstance(write_target.volume_serial, bool) or
        not 0 <= write_target.volume_serial <= 0xFFFFFFFF):
        return _blocked("INVALID_VOLUME_IDENTITY")

    target = _strict_dos_components(write_target.final_path)
    request = _strict_dos_components(request_time_path)
    if target is None or request is None:
        return _blocked("UNSUPPORTED_OR_AMBIGUOUS_PHYSICAL_PATH")
    if request != target:
        return _blocked("REQUEST_AND_ORIGINAL_HANDLE_PATH_DISAGREE")

    parsed_roots: list[tuple[str, tuple[str, ...], int]] = []
    for root in allowed_roots:
        p = _strict_dos_components(root.final_path)
        if (p is None or not p[1] or not isinstance(root.volume_serial, int)
            or isinstance(root.volume_serial, bool)
            or not 0 <= root.volume_serial <= 0xFFFFFFFF):
            return _blocked("UNSUPPORTED_OR_AMBIGUOUS_PERMITTED_ROOT")
        parsed_roots.append((p[0], p[1], root.volume_serial))

    for drive, parts, volume_id in parsed_roots:
        if (drive != target[0] or volume_id != write_target.volume_serial
                or len(target[1]) < len(parts)):
            continue
        prefix = target[1][:len(parts)]
        if prefix == parts:
            return PrivateAssessment("CONTAINED_CANDIDATE_ONLY", "MATCHING_HANDLE_DERIVED_ROOT")
        # This can be a legitimate match on ordinary NTFS, or a distinct
        # directory when case sensitivity is enabled. Neither conclusion may
        # be promoted without independently verified filesystem semantics.
        if tuple(p.casefold() for p in prefix) == tuple(p.casefold() for p in parts):
            return _blocked("DIRECTORY_CASE_MODE_UNVERIFIED")
    return PrivateAssessment("OUTSIDE_CANDIDATE_ONLY", "NO_MATCHING_HANDLE_DERIVED_ROOT")


def observe_supplied_windows_handle(handle: int) -> PrivateHandlePath:
    """Read final target from an already open, caller-authorised Windows file handle.

    Never opens a filename, never enumerates handles, never duplicates a foreign
    process handle. Do not call without independent native-operation approval.
    This adapter alone cannot correlate a handle to an ETW FileObject / IRP.
    The returned private path must not be printed, persisted to public CI or
    treated as an acceptance verdict.
    """
    if os.name != "nt":
        raise RuntimeError("WINDOWS_ADAPTER_NOT_AVAILABLE")
    if isinstance(handle, bool) or not isinstance(handle, int) or handle <= 0:
        raise RuntimeError("INVALID_SUPPLIED_HANDLE")

    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", FILETIME), ("ftLastAccessTime", FILETIME),
            ("ftLastWriteTime", FILETIME), ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD), ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD), ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_name = kernel32.GetFinalPathNameByHandleW
    get_name.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD)
    get_name.restype = wintypes.DWORD
    get_info = kernel32.GetFileInformationByHandle
    get_info.argtypes = (wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION))
    get_info.restype = wintypes.BOOL
    h = wintypes.HANDLE(handle)
    # VOLUME_NAME_DOS | FILE_NAME_NORMALIZED: only a *supplementary* observation.
    # Request-time path and reparse/alias conditions require separate checks.
    need = get_name(h, None, 0, 0)
    if need <= 0 or need > 32767:
        raise RuntimeError("FINAL_PATH_QUERY_BLOCKED")
    out = ctypes.create_unicode_buffer(need + 1)
    written = get_name(h, out, len(out), 0)
    if written <= 0 or written >= len(out):
        raise RuntimeError("FINAL_PATH_QUERY_BLOCKED")
    info = BY_HANDLE_FILE_INFORMATION()
    if not get_info(h, ctypes.byref(info)):
        raise RuntimeError("FILE_IDENTITY_QUERY_BLOCKED")
    # Acquisition is intentionally blank: the caller must review whether this
    # was genuinely an *original* file handle before constructing a witness.
    return PrivateHandlePath(out.value, int(info.dwVolumeSerialNumber), "UNVERIFIED_HANDLE_PROVENANCE")
