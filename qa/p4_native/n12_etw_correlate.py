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


def correlate_requests(events, resolve_path, classify_process, tracked, record, *, strict=False):
    """Keep file paths and identities private until the report callback reduces them."""
    active = {}
    opened, pending = {}, {}
    ambiguous_irps = set()
    unresolved = Counter()

    def relevant(actor, operation, source, destination):
        return tracked(source) or tracked(destination) or (
            strict and (actor != "other" or operation == "rename" or source is None)
        )

    for event in sorted(events, key=lambda record: record["ticks"]):
        kind, pid, data = event["id"], event["pid"], event["data"]
        ticks = event["ticks"]
        if event.get("lifecycle"):
            process_id = number(data["ProcessID"])
            if kind == 1:
                active[process_id] = ticks
            elif kind == 2:
                active.pop(process_id, None)
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
            operation, actor, identity, handle, source, destination, requested = pending.pop(irp)
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
                unresolved[f"{actor}:{operation}:process-lifetime-missing"] += 1
            if operation == "open":
                if source:
                    opened[handle] = source
                operation = "create" if open_result == 2 else "overwrite"
            elif operation == "rename":
                opened[handle] = destination
            if in_scope and mutation:
                if operation == "unsupported":
                    unresolved[f"{actor}:unsupported-file-operation"] += 1
                if not source or (operation == "rename" and not destination):
                    unresolved[f"{actor}:{operation}:path-missing"] += 1
                if source or destination:
                    record(actor, identity, operation, source, destination, requested, ticks, True)
            continue
        if kind == 27 and irp in pending:
            operation, owner, identity, obj, source, previous, requested = pending[irp]
            if operation == "rename" and obj == handle and path:
                if previous and previous != path:
                    unresolved[f"{owner}:rename:destination-ambiguous"] += 1
                pending[irp] = (operation, owner, identity, obj, source, path, requested)
            continue
        if strict and kind == 27 and path and relevant(actor, "rename", None, path):
            unresolved[f"{actor}:rename:request-missing-or-ambiguous"] += 1
            continue
        if kind in {12, 14}:
            opened.pop(handle, None)
        if kind not in {12, 16, 17, 18, 19, 23, 29, 34}:
            continue
        operation = {12: "open", 16: "write", 18: "delete", 19: "rename",
                     23: "unsupported", 29: "unsupported", 34: "unsupported"}.get(kind)
        if operation == "unsupported" and not strict:
            operation = None
        if kind == 17:
            if number(data.get("InfoClass")) == 20:  # FileEndOfFileInformation
                operation = "resize"
            elif strict:
                operation = "unsupported"
        source = path if kind == 12 else opened.get(handle)
        if not irp or not object_id:
            if operation and relevant(actor, operation, source, None):
                unresolved[f"{actor}:{operation}:identity-missing"] += 1
            continue
        if irp in pending:
            old_operation, owner, _, _, old_source, old_destination, _ = pending.pop(irp)
            if relevant(owner, old_operation, old_source, old_destination):
                unresolved[f"{owner}:{old_operation}:irp-reused-before-completion"] += 1
            ambiguous_irps.add(irp)
        if irp in ambiguous_irps:
            if operation and relevant(actor, operation, source, None):
                unresolved[f"{actor}:{operation}:irp-ambiguous"] += 1
        elif operation:
            pending[irp] = (operation, actor, identity, handle, source, None, ticks)
    for operation, actor, _, _, source, destination, _ in pending.values():
        if relevant(actor, operation, source, destination):
            unresolved[f"{actor}:{operation}:completion-missing"] += 1
    return unresolved


def correlate(capture, events):
    fixture, writer = capture["fixture"], capture["second_writer"]
    paths = {path.casefold(): label for label, path in (
        ("original", fixture["fixture"]), ("renamed", fixture["renamed_fixture"]),
        ("source", writer["source"]), ("destination", writer["destination"]),
    )}
    protected_prefix = capture["protected_root"].casefold() + "\\"
    devices = {capture["device"].casefold(): fixture["fixture"][:2].casefold()}
    declared = (
        (fixture["child_pid"], fixture["start_window"], "fixture"),
        (writer["pid"], writer["start_window"], "second-writer"),
    )
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
