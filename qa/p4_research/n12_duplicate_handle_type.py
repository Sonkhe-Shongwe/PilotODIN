"""G2.15: scoped DuplicateHandle/GetFileType CANDIDATE admission, source only.

No process enumeration, native execution, filesystem changes, name/path queries,
ETW mutations or approval. Windows always refuses this injected test driver.
A disk-type result NEVER proves original write ownership or FileObject identity.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
import os

MAX_HANDLES = 256
PSS_SOURCE = "PSS_WALK_HANDLES"
PROCESS_RIGHTS = 0x1040  # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE
DUPLICATE_SAME_ACCESS = 0x00000002
FILE_TYPE_UNKNOWN = 0
FILE_TYPE_DISK = 1
FILE_TYPE_CHAR = 2
FILE_TYPE_PIPE = 3

_PROCESS = frozenset({
    "pid", "birth", "exit", "original_process_handle_verified",
    "etw_sequence_verified", "image_verified", "disposable_qa_verified",
})
_SNAPSHOT = frozenset({"source", "pid", "birth", "tick", "complete", "handles"})
_REASONS = frozenset({
    "SCOPE", "PROCESS", "SNAPSHOT", "HANDLES", "IDENTITY", "DUPLICATE",
    "FILE_TYPE", "NO_DISK", "CLEANUP",
})


def _positive(value):
    return type(value) is int and 0 < value < 2**64


def _receipt(reason, disk=False):
    return {
        "scope": "g2-15-verified-process-injected-candidate-only",
        "status": "CANDIDATE_ONLY" if disk else "BLOCKED",
        "blocker": "NONE" if disk else reason if reason in _REASONS else "SCOPE",
        "disk_handle_classification": "CANDIDATE_ONLY" if disk else "NOT_VERIFIED",
        "original_writer_file_handle": "NOT_VERIFIED",
        "kernel_fileobject_etw_join": "NOT_ESTABLISHED",
        "handle_reuse_excluded": False,
        "same_object_at_write": "NOT_ESTABLISHED",
        "physical_destination": "NOT_VERIFIED",
        "native_N12_acceptance": "NOT_EVALUATED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def _validate(process, snapshot, backend):
    if os.name == "nt" or getattr(backend, "synthetic_only", None) is not True:
        return "SCOPE"
    if (type(process) is not dict or set(process) != _PROCESS
            or not all(_positive(process[k]) for k in ("pid", "birth", "exit"))
            or not process["birth"] < process["exit"]
            or not all(process[k] is True for k in (
                "original_process_handle_verified", "etw_sequence_verified",
                "image_verified", "disposable_qa_verified"))):
        return "PROCESS"
    if (type(snapshot) is not dict or set(snapshot) != _SNAPSHOT
            or snapshot["source"] != PSS_SOURCE
            or (snapshot["pid"], snapshot["birth"]) !=
                (process["pid"], process["birth"])
            or not _positive(snapshot["tick"])
            or not process["birth"] < snapshot["tick"] < process["exit"]
            or snapshot["complete"] is not True):
        return "SNAPSHOT"
    handles = snapshot["handles"]
    if (type(handles) is not list or not 1 <= len(handles) <= MAX_HANDLES
            or not all(_positive(h) for h in handles)
            or len(set(handles)) != len(handles)):
        return "HANDLES"
    return None


def review_injected(*, process, snapshot, backend):
    """Mock-only candidate check with mandatory context cleanup.

    backend.open_process(pid, access=PROCESS_RIGHTS) -> context manager
    backend.identity(process_handle) -> (pid, birth_ticks, image_basename)
    backend.duplicate(process_handle, original_handle, desired_access=0,
                      inherit=False, options=DUPLICATE_SAME_ACCESS)
                      -> context manager of LOCAL duplicate
    backend.file_type(local_duplicate) -> (DWORD type, GetLastError code).
    Any API, identity, handle or cleanup fault leaves all evidence BLOCKED.
    """
    failure = _validate(process, snapshot, backend)
    if failure is not None:
        return _receipt(failure)
    disk = False
    try:
        with backend.open_process(process["pid"], access=PROCESS_RIGHTS) as proc:
            if backend.identity(proc) != (
                    process["pid"], process["birth"], "msedgewebview2.exe"):
                return _receipt("IDENTITY")
            for original in snapshot["handles"]:
                with backend.duplicate(
                    proc, original, desired_access=0, inherit=False,
                    options=DUPLICATE_SAME_ACCESS,
                ) as local:
                    value = backend.file_type(local)
                    if (type(value) is not tuple or len(value) != 2
                            or type(value[0]) is not int
                            or type(value[1]) is not int):
                        return _receipt("FILE_TYPE")
                    file_type, error = value
                    if (file_type not in (
                            FILE_TYPE_UNKNOWN, FILE_TYPE_DISK,
                            FILE_TYPE_CHAR, FILE_TYPE_PIPE)
                            or error != 0):
                        return _receipt("FILE_TYPE")
                    if file_type == FILE_TYPE_UNKNOWN:
                        # Even GetLastError==0 means "unknown", not file proof.
                        return _receipt("FILE_TYPE")
                    if file_type == FILE_TYPE_DISK:
                        disk = True
        return _receipt("NONE", disk=disk) if disk else _receipt("NO_DISK")
    except Exception:
        # Never serialize native errors, handle values, PIDs or paths.
        return _receipt("DUPLICATE")
