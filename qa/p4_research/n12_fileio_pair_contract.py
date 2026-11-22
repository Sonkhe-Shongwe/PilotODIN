"""R02.5 source-only ETW request/completion and original-handle *contract*.

Not wired to the strict reducer or native runner. Event data and witness objects
are externally supplied and are NOT authenticated by this module. Its results
are diagnostic candidates only, never file-mutation credit or native acceptance.
No native handle enumeration, filesystem reads, capture, or public path output.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Mapping

from qa.p4_research.n12_physical_destination import (
    Corroboration, PrivateAssessment, PrivateHandlePath, assess_private_destination,
)

# Conservatively treat every file-event kind except read, write, operation
# end and QueryEA as an epoch change. This intentionally includes NameCreate,
# NameDelete, Close, Rename, SetInfo and unrecognised event kinds. The actual
# Windows provider contract still requires independent native verification.
_KNOWN_NONTRANSITIONS = frozenset({15, 16, 24, 34})
# Kernel File Write and OperationEnd in the existing N12 ETW decoder.
_WRITE, _END = 16, 24


def _unsigned(value: object) -> int | None:
    """Accept only unambiguous nonnegative ETW integer tokens (never bool)."""
    if type(value) is int:
        return value if value >= 0 else None
    if type(value) is str:
        if value.startswith(("0x", "0X")) and len(value) > 2 and all(
                c in "0123456789abcdefABCDEF" for c in value[2:]):
            return int(value[2:], 16)
        if value and all("0" <= c <= "9" for c in value):
            return int(value)
    return None


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _blocked(reason: str) -> PrivateAssessment:
    return PrivateAssessment("BLOCKED", reason)


@dataclass(frozen=True)
class PrivateWriterSpan:
    """Caller-provided process/thread lifetime claim, NOT independent proof."""
    pid: int
    birth_tick: int
    exit_tick: int
    issuing_tid: int
    thread_start_tick: int
    thread_end_tick: int


@dataclass(frozen=True)
class PrivateOriginalFilePair:
    """Proposed kernel-object join; the Win32 path adapter cannot create it.

    The FileObject value requires a separate original-handle/kernel witness.
    File index/volume serial returned by GetFileInformationByHandle does NOT
    supply this kernel pointer or prove a DuplicateHandle relationship.
    """
    file_object: int
    file_key: int
    handle_observed_tick: int


@dataclass(frozen=True)
class PrivateWriteIdentity:
    """Exact write request and completion expected inside one ETW capture."""
    irp: int
    file_object: int
    file_key: int
    writer_pid: int
    issuing_tid: int
    request_tick: int
    completion_tick: int


@dataclass(frozen=True)
class _Row:
    kind: int
    tick: int
    pid: int
    irp: int | None
    file_object: int | None
    file_key: int | None
    issuing_tid: int | None
    status: int | None


@dataclass(frozen=True, repr=False)
class PrivatePairIndex:
    """A compact numeric index built ONCE from one private full capture.

    This does not validate that the caller supplied a full trace, calibrated
    loss counters, original file handles, or a genuine writer. It is an O(N log N) worst-case
    synthetic contract helper for a separately approved evidence collector.
    """
    start_tick: int
    end_tick: int
    _by_irp: Mapping[int, tuple[_Row, ...]] = field(repr=False)
    # Numeric-only indexes. The dominant WebView2 FileObject may have >200K
    # writes; checking its lifetime must not linearly rescan each benign write.
    _obj_key_ticks: Mapping[int, Mapping[int | None, tuple[int, ...]]] = field(repr=False)
    _key_obj_ticks: Mapping[int, Mapping[int | None, tuple[int, ...]]] = field(repr=False)
    _obj_guard_ticks: Mapping[int, tuple[int, ...]] = field(repr=False)
    _key_guard_ticks: Mapping[int, tuple[int, ...]] = field(repr=False)
    build_issue: str | None = None


def index_private_kernel_file_events(events: object, *, start_tick: int, end_tick: int) -> PrivatePairIndex:
    """Index only numeric event identity fields; do not retain raw paths.

    The index is private and diagnostic-only. Malformed captures get a fixed
    blocker, without spilling private paths or raising on source input.
    """
    empty = PrivatePairIndex(start_tick, end_tick, {}, {}, {}, {}, {}, "MALFORMED_ETW_EVENT_STREAM")
    if (not _positive(start_tick) or not _positive(end_tick) or start_tick >= end_tick
            or type(events) not in (tuple, list)):
        return empty
    by_irp: dict[int, list[_Row]] = defaultdict(list)
    by_obj_key: dict[int, dict[int | None, list[int]]] = defaultdict(lambda: defaultdict(list))
    by_key_obj: dict[int, dict[int | None, list[int]]] = defaultdict(lambda: defaultdict(list))
    by_obj_guard: dict[int, list[int]] = defaultdict(list)
    by_key_guard: dict[int, list[int]] = defaultdict(list)
    try:
        for event in events:
            if type(event) is not dict:
                return empty
            # The provider decoder emits an explicit boolean lifecycle flag.
            # Do not mistake a malformed process record for a Kernel-File
            # operation and accidentally manufacture a valid write pair.
            if "lifecycle" in event and type(event["lifecycle"]) is not bool:
                return empty
            if event.get("lifecycle") is True:
                # PID/thread lifetimes must come from a separate original
                # Sysmon/ETW/handle join, never invented from FileIO headers.
                continue
            kind = _unsigned(event.get("id"))
            tick = _unsigned(event.get("ticks"))
            pid = _unsigned(event.get("pid"))
            data = event.get("data")
            if (kind is None or tick is None or not start_tick <= tick <= end_tick
                    or pid is None or type(data) is not dict):
                return empty
            # Ignore unrelated provider events; their correctness is covered
            # by the full capture/loss gate, not inferred by this helper.
            # Every kernel file event with matching identity participates in
            # the guard, even an unrecognised event kind. Only known non-name
            # events may be ignored as epoch invalidators.
            def field(name: str) -> int | None:
                raw = data.get(name)
                if raw is None:
                    return None
                parsed = _unsigned(raw)
                if parsed is None:
                    raise ValueError("malformed numeric ETW field")
                return parsed
            obj = field("FileObject")
            key = field("FileKey")
            irp = field("Irp")
            tid = field("IssuingThreadId")
            if tid is None:
                tid = field("ThreadId")
            status = field("Status")
            row = _Row(kind, tick, pid, irp, obj, key, tid, status)
            if irp:
                by_irp[irp].append(row)
            # A completion may omit one/both object identity fields. Do
            # not invent a (FileObject, None) or (None, FileKey) *reuse*
            # association from an otherwise valid Event24; the request/IRP
            # join separately checks any nonzero contradicting completion ID.
            # For all non-completion kinds, missing counterpart identity is
            # still a possible alias/epoch ambiguity and remains indexed.
            if obj and (kind != _END or key):
                by_obj_key[obj][key].append(tick)
            if key and (kind != _END or obj):
                by_key_obj[key][obj].append(tick)
            # Unknown operations are not silently treated as harmless.
            guarded = kind not in _KNOWN_NONTRANSITIONS
            if guarded:
                if obj:
                    by_obj_guard[obj].append(tick)
                if key:
                    by_key_guard[key].append(tick)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return empty
    return PrivatePairIndex(
        start_tick, end_tick,
        {k: tuple(sorted(v, key=lambda x: x.tick)) for k, v in by_irp.items()},
        {k: {other: tuple(sorted(ticks)) for other, ticks in counterparts.items()}
            for k, counterparts in by_obj_key.items()},
        {k: {other: tuple(sorted(ticks)) for other, ticks in counterparts.items()}
            for k, counterparts in by_key_obj.items()},
        {k: tuple(sorted(ticks)) for k, ticks in by_obj_guard.items()},
        {k: tuple(sorted(ticks)) for k, ticks in by_key_guard.items()},
    )


def review_private_write_pair(
    *, index: PrivatePairIndex,
    write: PrivateWriteIdentity,
    writer: PrivateWriterSpan,
    original_pair: PrivateOriginalFilePair,
    write_target: PrivateHandlePath,
    permitted_roots: tuple[PrivateHandlePath, ...],
    request_time_path: str,
    corroboration: Corroboration,
) -> PrivateAssessment:
    """Source-only contract check on one uniquely completed Kernel-File write.

    Even when all supplied evidence is structurally consistent, this returns
    only a candidate. The ORIGINAL file handle and its FileObject association,
    process/thread lifetimes and capture loss MUST still be independently
    established by a separately authorised native collector. No source-only
    caller may promote this to strict FileIO path credit.
    """
    if not isinstance(index, PrivatePairIndex) or index.build_issue:
        return _blocked("ETW_INDEX_UNVERIFIED")
    if (not isinstance(write, PrivateWriteIdentity)
            or not isinstance(writer, PrivateWriterSpan)
            or not isinstance(original_pair, PrivateOriginalFilePair)):
        return _blocked("PRIVATE_IDENTITY_ENVELOPE_INVALID")
    numbers = (*vars(write).values(), *vars(writer).values(), *vars(original_pair).values())
    if not all(_positive(n) for n in numbers):
        return _blocked("PRIVATE_IDENTITY_VALUE_INVALID")
    if not isinstance(corroboration, Corroboration) or not corroboration.complete():
        return _blocked("INDEPENDENT_PROOF_INCOMPLETE")
    if not (index.start_tick <= writer.birth_tick <= writer.thread_start_tick
            < write.request_tick < write.completion_tick
            < writer.thread_end_tick <= writer.exit_tick <= index.end_tick):
        return _blocked("ORIGINAL_WRITER_LIFETIME_UNVERIFIED")
    if not (writer.pid == write.writer_pid and writer.issuing_tid == write.issuing_tid
            and original_pair.file_object == write.file_object
            and original_pair.file_key == write.file_key
            and index.start_tick <= original_pair.handle_observed_tick <= index.end_tick):
        return _blocked("ORIGINAL_WRITER_OR_FILE_PAIR_MISMATCH")
    # Original handle may have been observed before or after the write, but no
    # object/name transition can be present between observation and completion.
    first = min(original_pair.handle_observed_tick, write.request_tick)
    last = max(original_pair.handle_observed_tick, write.completion_tick)
    if (not writer.birth_tick < first or last >= writer.exit_tick):
        return _blocked("ORIGINAL_HANDLE_OBSERVATION_OUTSIDE_WRITER_LIFETIME")

    candidates = tuple(r for r in index._by_irp.get(write.irp, ())
                       if write.request_tick <= r.tick <= write.completion_tick)
    if len(candidates) != 2:
        return _blocked("ETW_IRP_LIFETIME_MISSING_OR_AMBIGUOUS")
    request, completed = candidates
    if (request.kind != _WRITE or completed.kind != _END
            or request.tick != write.request_tick
            or completed.tick != write.completion_tick):
        return _blocked("ETW_WRITE_COMPLETION_PAIR_MISMATCH")
    if not (request.pid == write.writer_pid and request.issuing_tid == write.issuing_tid
            and request.file_object == write.file_object
            and request.file_key == write.file_key):
        return _blocked("ETW_REQUEST_WRITER_OR_OBJECT_MISMATCH")
    # Completion PID need not be writer PID: Windows may complete in system
    # context. The issuing request, independent thread/process and IRP matter.
    # Kernel-File OperationEnd identifies the request by IRP. Some valid
    # provider records omit FileObject/FileKey on Event 24, as do the existing
    # generated N12 fixtures. An *absent or zero* completion identity is not
    # independent file-object evidence. A nonzero contradictory value blocks;
    # the request's identity, unique ordered IRP completion, and separately
    # required original-handle/epoch corroboration are still mandatory.
    if (completed.file_object not in (None, 0, write.file_object)
            or completed.file_key not in (None, 0, write.file_key)
            or completed.status != 0):
        return _blocked("ETW_SUCCESSFUL_COMPLETION_UNVERIFIED")

    # Check only *different* key/object associations plus name/handle epoch
    # transitions. Repeated ordinary writes to one FileObject are represented
    # by sorted timestamp arrays, not scanned for every candidate.
    def in_epoch(ticks: tuple[int, ...]) -> bool:
        i = bisect_left(ticks, first)
        return i < len(ticks) and ticks[i] <= last

    for other_key, ticks in index._obj_key_ticks.get(write.file_object, {}).items():
        if other_key != write.file_key and in_epoch(ticks):
            return _blocked("ETW_FILE_OBJECT_OR_KEY_REUSED")
    for other_obj, ticks in index._key_obj_ticks.get(write.file_key, {}).items():
        if other_obj != write.file_object and in_epoch(ticks):
            return _blocked("ETW_FILE_OBJECT_OR_KEY_REUSED")
    if (in_epoch(index._obj_guard_ticks.get(write.file_object, ()))
            or in_epoch(index._key_guard_ticks.get(write.file_key, ()))):
        return _blocked("ETW_NAME_OR_HANDLE_EPOCH_UNVERIFIED")

    # This module consumes externally supplied witness and proof claims.
    # Structural agreement alone cannot authenticate original-file handles.
    return assess_private_destination(
        write_target=write_target, allowed_roots=permitted_roots,
        request_time_path=request_time_path, corroboration=corroboration,
    )
