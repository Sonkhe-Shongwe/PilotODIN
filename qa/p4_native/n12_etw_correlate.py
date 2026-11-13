"""Correlate successful Windows Kernel File requests for generated N12 markers."""
from __future__ import annotations

import json
import ntpath
import re
import sys
from collections import Counter
from pathlib import Path


def number(value):
    if isinstance(value, str):
        return int(value, 16 if value.lower().startswith("0x") else 10)
    return value


def canonical_file_path(value, devices):
    """Resolve drive and explicit device aliases from the capture host."""
    path = value.replace("/", "\\").casefold()
    for prefix in ("\\\\?\\", "\\??\\"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    for device, drive in devices.items():
        if path == device or path.startswith(device + "\\"):
            path = drive + path[len(device):]
            break
    drive, tail = ntpath.splitdrive(path)
    if re.fullmatch(r"[a-z]:", drive) and tail.startswith("\\"):
        return ntpath.normpath(path)
    return None


def correlate_requests(events, resolve_path, classify_process, tracked, record, *,
                       strict=False, details=None, process_bookends=None, thread_bookends=None):
    """Keep file paths and identities private until the report callback reduces them."""
    active = {}
    thread_owners = {}
    opened, pending = {}, {}
    file_names = {}
    ambiguous_irps = set()
    unresolved = Counter()

    def relevant(actor, operation, source, destination):
        return tracked(source) or tracked(destination) or (
            strict and (actor != "other" or operation == "rename" or source is None)
        )

    def flag(actor, reason, event_id, info_class):
        unresolved[f"{actor}:{reason}"] += 1
        if details is not None:
            info = info_class if type(info_class) is int and 0 <= info_class <= 255 else "unknown"
            suffix = f":info-{info}" if event_id == 17 else ""
            details[f"{actor}:event-{event_id}{suffix}:{reason}"] += 1

    for event in sorted(events, key=lambda record: record["ticks"]):
        kind, pid, data = event["id"], event["pid"], event["data"]
        ticks = event["ticks"]
        if event.get("lifecycle"):
            process_id = number(data["ProcessID"])
            if kind == 1:
                active[process_id] = ticks
            elif kind == 2:
                active.pop(process_id, None)
            elif details is not None and kind in (3, 4):
                tid = number(data["ThreadID"])
                if kind == 3:
                    thread_owners[tid] = (process_id, active.get(process_id))
                else:
                    thread_owners.pop(tid, None)
            continue
        if kind in {10, 11}:
            if strict and (file_key := number(data.get("FileKey"))):
                if kind == 10:
                    name = resolve_path(data.get("FileName") or "")
                    # A second distinct name can be an alias. Leave the key
                    # unresolved until a new name lifetime can be established.
                    file_names[file_key] = (
                        name if file_names.get(file_key, name) == name else None
                    )
                else:
                    file_names.pop(file_key, None)
            continue
        object_id = number(data.get("FileObject"))
        irp = number(data.get("Irp"))
        birth = active.get(pid)
        actor, identity = classify_process(pid, birth, ticks)
        handle = (pid, birth, object_id)
        path = resolve_path(data.get("FileName") or data.get("FilePath") or "")
        if kind == 24:
            if irp in ambiguous_irps:
                continue
            if not irp or irp not in pending:
                continue
            operation, actor, identity, handle, source, destination, requested, event_id, info_class = pending.pop(irp)
            in_scope = relevant(actor, operation, source, destination)
            status = number(data.get("Status"))
            if status is None:
                if in_scope:
                    unresolved[f"{actor}:{operation}:missing-status"] += 1
                continue
            if status & 0x80000000:
                if in_scope:
                    record(actor, identity, operation, source, destination, requested, ticks, False)
                continue
            # FILE_SUPERSEDED, FILE_CREATED and FILE_OVERWRITTEN mutate data.
            open_result = number(data.get("ExtraInformation")) if operation == "open" else None
            mutation = operation != "open" or open_result in {0, 2, 3}
            if in_scope and operation == "open" and open_result not in {0, 1, 2, 3}:
                unresolved[f"{actor}:open:unknown-open-result"] += 1
            if in_scope and mutation and handle[1] is None:
                flag(actor, f"{operation}:process-lifetime-missing", event_id, info_class)
            if operation == "open":
                if source:
                    opened[handle] = source
                operation = "create" if open_result == 2 else "overwrite"
            elif operation == "rename":
                opened[handle] = destination
            if in_scope and mutation:
                if operation == "unsupported":
                    flag(actor, "unsupported-file-operation", event_id, info_class)
                if not source or (operation == "rename" and not destination):
                    flag(actor, f"{operation}:path-missing", event_id, info_class)
                if source or destination:
                    record(actor, identity, operation, source, destination, requested, ticks, True)
            continue
        if kind == 27 and irp in pending:
            operation, owner, identity, obj, source, previous, requested, event_id, info_class = pending[irp]
            if operation == "rename" and obj == handle and path:
                if previous and previous != path:
                    unresolved[f"{owner}:rename:destination-ambiguous"] += 1
                pending[irp] = (operation, owner, identity, obj, source, path, requested, event_id, info_class)
            continue
        if strict and kind == 27 and path and relevant(actor, "rename", None, path):
            unresolved[f"{actor}:rename:request-missing-or-ambiguous"] += 1
            continue
        if kind in {12, 14}:
            opened.pop(handle, None)
        if kind not in {12, 16, 17, 18, 19, 23, 29, 34}:
            continue
        operation = {12: "open", 16: "write", 18: "delete", 19: "rename",
                     23: "unsupported", 29: "unsupported"}.get(kind)
        if operation == "unsupported" and not strict:
            operation = None
        # QueryEA (34) has no mutation operation, but a reused IRP still
        # invalidates any outstanding mutation that used the same pointer.
        info_class = number(data.get("InfoClass")) if kind == 17 else None
        if kind == 17:
            if info_class == 20:  # FileEndOfFileInformation
                operation = "resize"
            elif strict and info_class == 19:  # FileAllocationInformation
                operation = "allocate"
            elif strict:
                operation = "unsupported"
        source = path if kind == 12 else opened.get(handle)
        if strict and kind in {16, 18, 19, 23, 29}:
            file_key = number(data.get("FileKey"))
            if kind != 16 and file_key in file_names:
                file_names[file_key] = None
            if details is not None and kind == 16 and source is None:
                tid = number(data.get("IssuingThreadId", data.get("ThreadId")))
                owner = thread_owners.get(tid)
                attribution = "missing-issuing-thread" if not tid else "unmatched-thread-lifetime"
                if owner is not None and active.get(owner[0]) == owner[1]:
                    owner_pid, owner_birth = owner
                    attribution = "header-agrees" if pid == owner_pid else "header-differs"
                    if owner_birth is not None and opened.get((owner_pid, owner_birth, object_id)) is not None:
                        details[f"{actor}:event-16:write-request:issuing-thread-handle-path"] += 1
                elif thread_bookends is not None and tid in thread_bookends:
                    attribution = "bookend-header-agrees" if pid == thread_bookends[tid] else "bookend-header-differs"
                details[f"{actor}:event-16:write-request:{attribution}"] += 1
                candidate = file_names.get(file_key)
                context = "missing-key" if not file_key else "unseen-key"
                if file_key in file_names:
                    context = "ambiguous-name"
                if candidate is not None:
                    context = "tracked" if tracked(candidate) else "outside-tracked-paths"
                details[f"{actor}:event-16:write-request:file-key-context-{context}"] += 1
                if birth is None and process_bookends is not None:
                    if pid in process_bookends:
                        identity_context = "same-process-at-bookends"
                    elif pid in (0, 4):
                        identity_context = "system-header-without-bookends"
                    else:
                        identity_context = "missing-process-bookends"
                    details[f"{actor}:event-16:write-request:{identity_context}:{context}"] += 1
        if not irp or not object_id:
            if operation and relevant(actor, operation, source, None):
                unresolved[f"{actor}:{operation}:identity-missing"] += 1
            continue
        if irp in pending:
            old_operation, owner, _, _, old_source, old_destination, _, _, _ = pending.pop(irp)
            if relevant(owner, old_operation, old_source, old_destination):
                unresolved[f"{owner}:{old_operation}:irp-reused-before-completion"] += 1
            ambiguous_irps.add(irp)
        if irp in ambiguous_irps:
            if operation and relevant(actor, operation, source, None):
                unresolved[f"{actor}:{operation}:irp-ambiguous"] += 1
        elif operation:
            pending[irp] = (operation, actor, identity, handle, source, None, ticks, kind, info_class)
    for operation, actor, _, _, source, destination, _, event_id, info_class in pending.values():
        if relevant(actor, operation, source, destination):
            flag(actor, f"{operation}:completion-missing", event_id, info_class)
    return unresolved


def correlate(capture, events):
    fixture, writer = capture["fixture"], capture["second_writer"]
    paths = {fixture["fixture"].casefold(): "original", fixture["renamed_fixture"].casefold(): "renamed"}
    protected_prefix = capture["protected_root"].casefold() + "\\"
    devices = {capture["device"].casefold(): fixture["fixture"][:2].casefold()}
    declared = [(fixture["child_pid"], fixture["start_window"], "fixture")]
    if writer is not None:
        paths.update({writer["source"].casefold(): "source", writer["destination"].casefold(): "destination"})
        declared.append((writer["pid"], writer["start_window"], "second-writer"))
    witnessed, failed = Counter(), Counter()
    lifecycles = {actor: set() for _, _, actor in declared}
    protected_writes = 0

    def resolve_path(path):
        path = canonical_file_path(path, devices)
        if path and path.startswith(protected_prefix):
            return "protected"
        return paths.get(path)

    def classify_process(pid, birth, ticks):
        for expected, (start, end), actor in declared:
            if pid == expected and birth is not None and start <= birth <= end:
                lifecycles[actor].add(birth)
                return actor, None
        return "other", None

    def record(actor, identity, operation, source, destination, requested, completed, success):
        nonlocal protected_writes
        if not success:
            failed[f"{actor}:{operation}:{source or destination}"] += 1
        elif operation == "rename":
            if source and destination:
                witnessed[f"{actor}:rename:{source}:{destination}"] += 1
        elif source:
            witnessed[f"{actor}:{operation}:{source}"] += 1
        if success and "protected" in (source, destination):
            protected_writes += 1

    unresolved = correlate_requests(events, resolve_path, classify_process, bool, record)
    for _, _, actor in declared:
        if len(lifecycles[actor]) != 1:
            unresolved[f"{actor}:process-start-missing-or-ambiguous"] += 1
    return {"operations": dict(witnessed), "failed": dict(failed), "unresolved": dict(unresolved),
            "protected_writes": protected_writes}


def main():
    capture_path, events_path = map(Path, sys.argv[1:])
    capture = json.loads(capture_path.read_text(encoding="utf-8-sig"))
    with events_path.open(encoding="utf-8-sig") as stream:
        report = correlate(capture, (json.loads(line) for line in stream))
    print(json.dumps(report))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        sys.exit("Kernel File correlation could not decode the captured fields.")
