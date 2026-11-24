"""Dormant G2.25 generated self-file ObTrace feasibility contract.

No native calls, file reads, capture or public identity output. TDH-decoded
private property bytes and existing manifest Kernel-File events are separate
inputs; cross-provider object equality is a hypothesis tested here, not an
assumed Windows invariant. No native acceptance or mutation credit.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from qa.p4_research.n12_fileio_pair_contract import (
    PrivateWriterSpan, PrivateWriteIdentity, index_private_kernel_file_events,
)
from qa.p4_research.n12_physical_destination import PrivateHandlePath

OBTRACE = "89497f50-effe-4440-8cf2-ce6b1cdcaca7"
VERSION = 2
MAX_EVENTS = 100_000
MAX_FILE_EVENTS = 100_000
CREATE, CLOSE, DUPLICATE = 32, 33, 34


def positive(value, limit=2**64 - 1):
    return type(value) is int and 0 < value <= limit


@dataclass(frozen=True, repr=False)
class PrivateHandleEvent:
    opcode: int
    tick: int
    header_pid: int
    header_tid: int
    object_id: int
    object_type: int
    handle: int
    target_handle: int | None = None
    target_pid: int | None = None


def decode_private_obtrace(row):
    """Consume named TDH property bytes, never guess raw MOF offsets.

    The upstream decoder must provide converted common-clock ticks and the
    actual event header flags; those claims are not authenticated here.
    ObjectName is deliberately neither requested nor retained.
    """
    if type(row) is not dict or set(row) != {
        "provider", "version", "opcode", "classic", "header32", "header64",
        "tick", "pid", "tid", "properties",
    }:
        return None
    if (row["provider"] != OBTRACE or type(row["version"]) is not int
            or row["version"] != VERSION or type(row["opcode"]) is not int
            or row["opcode"] not in (CREATE, CLOSE, DUPLICATE)
            or row["classic"] is not True
            or type(row["header32"]) is not bool or type(row["header64"]) is not bool
            or row["header32"] == row["header64"]
            or not positive(row["tick"]) or not positive(row["pid"], 2**32 - 1)
            or not positive(row["tid"], 2**32 - 1)):
        return None
    op = row["opcode"]
    fields = {"Object": 4 if row["header32"] else 8, "ObjectType": 2}
    fields.update({"SourceHandle": 4, "TargetHandle": 4, "TargetProcessId": 4}
                  if op == DUPLICATE else {"Handle": 4})
    props = row["properties"]
    if type(props) is not dict or set(props) != set(fields):
        return None
    numbers = {}
    for key, width in fields.items():
        value = props[key]
        if type(value) is not bytes or len(value) != width:
            return None
        number = int.from_bytes(value, "little")
        if not positive(number):
            return None
        numbers[key] = number
    return PrivateHandleEvent(op, row["tick"], row["pid"], row["tid"],
                              numbers["Object"], numbers["ObjectType"],
                              numbers.get("Handle", numbers.get("SourceHandle")),
                              numbers.get("TargetHandle"), numbers.get("TargetProcessId"))


@dataclass(frozen=True, repr=False)
class SelfFileControl:
    """Known self-owned generated disk handle, not a foreign-handle claim."""
    handle: int
    observation_tick: int
    write: PrivateWriteIdentity
    final_path: PrivateHandlePath


@dataclass(frozen=True, repr=False)
class CaptureClaims:
    """Externally provided calibration conditions, NOT authenticated here."""
    shared_clock_calibrated: bool
    header_ownership_calibrated: bool
    both_streams_loss_reviewed: bool
    known_self_disk_handles: bool
    generated_paths_and_volume_verified: bool


def receipt(reason, checked=0):
    return {
        "status": "SOURCE_CANDIDATE_ONLY" if reason == "TWO_DISTINCT_SELF_FILE_JOINS" else "BLOCKED",
        "reason": reason,
        "checked_controls": checked,
        "original_file_handle_verified": False,
        "physical_destination_verified": False,
        "native_N12_acceptance": "NOT_EVALUATED",
        "strict_path_credit_awarded": 0,
    }


def review_generated_controls(*, obtrace_rows, file_events, writer, controls,
                              start_tick, end_tick, claims):
    """Conservative two-open control: same generated file, distinct objects.

    No duplicates are allowed in this first calibration. Any duplicate touching
    a selected object or the writer is a blocker, not silently skipped.
    The whole writer lifetime is inside both streams. Extra writer writes,
    unmatched closes, ambiguous live handles and uncertain ordering fail closed.
    Only a separately approved native experiment could authenticate the inputs.
    """
    if (type(claims) is not CaptureClaims
            or not all(v is True for v in vars(claims).values())):
        return receipt("CAPTURE_CLAIMS_INCOMPLETE")
    if (not positive(start_tick) or not positive(end_tick)
            or type(writer) is not PrivateWriterSpan
            or not all(positive(v) for v in vars(writer).values())
            or not start_tick < writer.birth_tick <= writer.thread_start_tick
            < writer.thread_end_tick <= writer.exit_tick < end_tick
            or type(controls) is not tuple or len(controls) != 2
            or any(type(c) is not SelfFileControl for c in controls)
            or type(obtrace_rows) not in (tuple, list)
            or not 0 < len(obtrace_rows) <= MAX_EVENTS
            or type(file_events) not in (tuple, list)
            or not 0 < len(file_events) <= MAX_FILE_EVENTS):
        return receipt("PRIVATE_CONTROL_ENVELOPE_INVALID")
    for c in controls:
        w, path = c.write, c.final_path
        if (not positive(c.handle, 2**32 - 1) or not positive(c.observation_tick)
                or type(w) is not PrivateWriteIdentity
                or not all(positive(v) for v in vars(w).values())
                or w.writer_pid != writer.pid or w.issuing_tid != writer.issuing_tid
                or not writer.thread_start_tick < c.observation_tick < w.request_tick
                < w.completion_tick < writer.thread_end_tick
                or type(path) is not PrivateHandlePath
                or path.acquisition != "original_file_handle"
                or type(path.final_path) is not str or not path.final_path
                or not positive(path.volume_serial, 2**32 - 1)):
            return receipt("SELF_FILE_WITNESS_INVALID")
    a, b = controls
    if (a.handle == b.handle or a.write.file_object == b.write.file_object
            or a.write.irp == b.write.irp
            or a.final_path != b.final_path
            or not a.write.completion_tick < b.write.request_tick):
        return receipt("DISTINCT_OPEN_CONTROL_UNVERIFIED")
    selected_objects = {c.write.file_object for c in controls}
    selected_handles = {c.handle for c in controls}
    decoded = []
    for row in obtrace_rows:
        event = decode_private_obtrace(row)
        if event is None or not start_tick <= event.tick <= end_tick:
            return receipt("OBJECT_EVENT_SCHEMA_OR_CLOCK_UNVERIFIED")
        if event.opcode == DUPLICATE and (event.object_id in selected_objects
                or writer.pid in (event.header_pid, event.target_pid)):
            return receipt("DUPLICATE_PROVENANCE_UNSUPPORTED")
        if event.object_id in selected_objects or (
                event.header_pid == writer.pid and event.handle in selected_handles):
            decoded.append(event)
    # This deliberately treats tied object/handle transitions as ambiguous.
    decoded.sort(key=lambda e: e.tick)
    if len({e.tick for e in decoded}) != len(decoded):
        return receipt("HANDLE_EPOCH_ORDER_AMBIGUOUS")
    active = {}
    epochs = defaultdict(list)
    for e in decoded:
        if not writer.birth_tick < e.tick < writer.exit_tick:
            return receipt("OBJECT_EVENT_OUTSIDE_WRITER_LIFETIME")
        if e.header_pid != writer.pid:
            return receipt("FOREIGN_OBJECT_OWNERSHIP_UNRESOLVED")
        if e.opcode == DUPLICATE:
            return receipt("DUPLICATE_PROVENANCE_UNSUPPORTED")
        if e.opcode == CREATE:
            if e.handle in active:
                return receipt("HANDLE_EPOCH_REUSED_OR_UNCLOSED")
            active[e.handle] = e
        elif e.opcode == CLOSE:
            first = active.pop(e.handle, None)
            if first is None or (first.object_id, first.object_type) != (e.object_id, e.object_type):
                return receipt("HANDLE_CLOSE_UNMATCHED")
            epochs[e.handle].append((first, e))
    if active:
        return receipt("HANDLE_EPOCH_REUSED_OR_UNCLOSED")
    index = index_private_kernel_file_events(file_events, start_tick=start_tick, end_tick=end_tick)
    if index.build_issue:
        return receipt("FILEIO_INDEX_UNVERIFIED")
    if len(index._write_rows_by_pid.get(writer.pid, ())) != 2:
        return receipt("WRITER_WRITE_INVENTORY_UNVERIFIED")
    checked = 0
    for c in controls:
        w = c.write
        covering = [(h, first, last) for h, spans in epochs.items() for first, last in spans
                    if first.object_id == w.file_object
                    and first.tick <= w.completion_tick and w.request_tick <= last.tick]
        if (len(covering) != 1 or covering[0][0] != c.handle
                or not covering[0][1].tick < c.observation_tick < w.request_tick
                or not w.completion_tick < covering[0][2].tick):
            return receipt("ORIGINAL_HANDLE_EPOCH_AMBIGUOUS", checked)
        # Both opens must coexist; this separates two independent object
        # identities from a sequential object-address reuse.
        other = b if c is a else a
        if not covering[0][1].tick < other.write.request_tick < covering[0][2].tick:
            return receipt("DISTINCT_OPEN_OVERLAP_UNVERIFIED", checked)
        first, last = c.observation_tick, w.completion_tick
        if (any(first <= t <= last for obj, ts in index._key_obj_ticks.get(w.file_key, {}).items()
                if obj != w.file_object for t in ts)
                or any(first <= t <= last for key, ts in index._obj_key_ticks.get(w.file_object, {}).items()
                       if key != w.file_key for t in ts)
                or any(first <= t <= last for t in index._obj_guard_ticks.get(w.file_object, ()))
                or any(first <= t <= last for t in index._key_guard_ticks.get(w.file_key, ()))):
            return receipt("FILEIO_OBJECT_OR_NAME_EPOCH_UNVERIFIED", checked)
        pair = tuple(r for r in index._by_irp.get(w.irp, ())
                     if w.request_tick <= r.tick <= w.completion_tick)
        if len(pair) != 2:
            return receipt("FILEIO_IRP_AMBIGUOUS", checked)
        request, completion = pair
        if (request.kind != 16 or completion.kind != 24
                or request.tick != w.request_tick or completion.tick != w.completion_tick
                or request.pid != writer.pid or request.issuing_tid != writer.issuing_tid
                or request.file_object != w.file_object or request.file_key != w.file_key
                or completion.status != 0
                or completion.file_object not in (None, 0, w.file_object)
                or completion.file_key not in (None, 0, w.file_key)):
            return receipt("FILEIO_REQUEST_COMPLETION_UNVERIFIED", checked)
        checked += 1
    return receipt("TWO_DISTINCT_SELF_FILE_JOINS", checked)
