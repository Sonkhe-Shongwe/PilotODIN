"""G2.11 source-only, injection-tested plan for process-scoped PSS handles.

This module NEVER calls Windows APIs, enumerates a process, runs a native
capture or authenticates a file handle. On Windows it always refuses execution.
The injected backend is permitted ONLY for non-Windows synthetic fixture tests.
All outputs are fixed-label/redacted and may not earn R02.5/N12 credit.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
import os

from qa.p4_research import n12_pss_file_handle_candidates as candidate

# Microsoft processsnapshot.h. Intentionally exclude HANDLE_NAME_INFORMATION
# (private names), VA clones, handle trace and type-specific capture. These
# numerical constants specify a *future* proposal, not an implemented WinAPI.
PSS_CAPTURE_HANDLES = 0x00000004
PSS_CAPTURE_HANDLE_BASIC_INFORMATION = 0x00000010
CAPTURE_FLAGS = PSS_CAPTURE_HANDLES | PSS_CAPTURE_HANDLE_BASIC_INFORMATION
PSS_WALK_HANDLES = 2
THREAD_CONTEXT_FLAGS = 0
# The exact requested access is proposed for source review only. Real
# PssCaptureSnapshot rights/sufficiency require a separate Windows validation.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_DUP_HANDLE = 0x0040
REQUESTED_PROCESS_ACCESS = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE
MAX_ROWS = candidate.MAX_HANDLES


def _receipt(blocker: str, *, candidate_review: dict | None = None) -> dict:
    positive = candidate_review is not None and candidate_review["status"] == "CANDIDATE_ONLY"
    return {
        "scope": "g2-11-pss-injected-source-only",
        "status": "CANDIDATE_ONLY" if positive else "BLOCKED",
        "blocker": "NONE" if positive else blocker,
        "snapshots_max": 2,
        "snapshot_rows_max": MAX_ROWS,
        "original_file_handle_provenance": "NOT_VERIFIED",
        "same_object_at_write": "NOT_ESTABLISHED",
        "kernel_fileobject_etw_join": "NOT_ESTABLISHED",
        "physical_destination": "NOT_VERIFIED",
        "file_mutation_acceptance": "NOT_EVALUATED",
        "native_N12_acceptance": "NOT_EVALUATED",
        "owner_native_execution_authorized": False,
    }


def _preflight(process: object, write: object, backend: object) -> bool:
    if type(process) is not dict or type(write) is not dict:
        return False
    if set(process) != {
        "pid", "birth", "exit", "original_process_handle_verified",
        "etw_sequence_verified", "image_verified", "disposable_qa_verified",
    } or set(write) != {"pid", "birth", "handle", "request", "completion"}:
        return False
    if not all(candidate.positive(process[k]) for k in ("pid", "birth", "exit")):
        return False
    if not all(process[k] is True for k in (
        "original_process_handle_verified", "etw_sequence_verified",
        "image_verified", "disposable_qa_verified",
    )):
        return False
    if not all(candidate.positive(write[k]) for k in (
        "pid", "birth", "handle", "request", "completion",
    )):
        return False
    if (write["pid"], write["birth"]) != (process["pid"], process["birth"]):
        return False
    if not process["birth"] < write["request"] < write["completion"] < process["exit"]:
        return False
    return getattr(backend, "synthetic_only", None) is True


def _bounded_rows(backend: object, snapshot: object) -> list:
    rows = backend.walk(snapshot, PSS_WALK_HANDLES)
    iterator = iter(rows)
    collected = []
    try:
        for index, row in enumerate(iterator):
            if index >= MAX_ROWS:
                raise ValueError("snapshot rows exceed bound")
            if type(row) is not dict or set(row) != {
                "handle", "type_name", "object_type", "flags",
            }:
                raise ValueError("snapshot row contains unreviewed fields")
            collected.append(row)
    finally:
        close = getattr(iterator, "close", None)
        if callable(close):
            close()
    return collected


def review_injected_pair(*, process: object, write: object, backend: object) -> dict:
    """Exercise a *mock* two-snapshot lifetime and cleanup, never live PSS.

    Test backend protocol:
      open_process(pid, access=REQUESTED_PROCESS_ACCESS) -> context manager
      identity(handle) -> {"pid", "birth", "image", "disposable_qa"}
      capture(handle, flags=CAPTURE_FLAGS, context_flags=0) -> context manager
      tick(snapshot) -> positive FILETIME-like integer
      walk(snapshot, PSS_WALK_HANDLES) -> bounded synthetic dict rows

    Identity is still a CLAIM from the mock, not independent OS proof.
    Every successful context must be exited. The caller owns no native handle.
    """
    if os.name == "nt":
        return _receipt("NATIVE_EXECUTION_DISALLOWED")
    if not _preflight(process, write, backend):
        return _receipt("SOURCE_SCOPE_INVALID")
    try:
        with backend.open_process(process["pid"], access=REQUESTED_PROCESS_ACCESS) as handle:
            identity = backend.identity(handle)
            if (type(identity) is not dict
                    or set(identity) != {"pid", "birth", "image", "disposable_qa"}
                    or identity["pid"] != process["pid"]
                    or identity["birth"] != process["birth"]
                    or identity["image"] != "msedgewebview2.exe"
                    or identity["disposable_qa"] is not True):
                return _receipt("PROCESS_IDENTITY_UNVERIFIED")

            observations = []
            for _ in range(2):
                with backend.capture(
                        handle, flags=CAPTURE_FLAGS,
                        context_flags=THREAD_CONTEXT_FLAGS) as snapshot:
                    tick = backend.tick(snapshot)
                    rows = _bounded_rows(backend, snapshot)
                    observations.append({
                        "source": candidate.SOURCE,
                        "pid": process["pid"], "birth": process["birth"],
                        "tick": tick, "complete": True, "rows": rows,
                    })
        report = candidate.review_candidate(
            process=process, before=observations[0],
            after=observations[1], write=write,
        )
        return _receipt(report["blocker"], candidate_review=report)
    except Exception:
        # Never publish OS errors, raw handle numbers, original paths or
        # partial private observations. Context cleanup is still mandatory.
        return _receipt("MOCK_BACKEND_OR_CLEANUP_FAILED")
