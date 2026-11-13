"""Correlate successful Windows Kernel File requests for generated N12 markers."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def number(value):
    if isinstance(value, str):
        return int(value, 16 if value.lower().startswith("0x") else 10)
    return value


def correlate(capture, events):
    fixture, writer = capture["fixture"], capture["second_writer"]
    paths = {}
    for label, path in (
        ("original", fixture["fixture"]), ("renamed", fixture["renamed_fixture"]),
        ("source", writer["source"]), ("destination", writer["destination"]),
    ):
        paths[path.casefold()] = label
        paths[(capture["device"] + path[2:]).casefold()] = label
    protected = capture["protected_root"].casefold()
    protected_prefixes = (protected + "\\", capture["device"].casefold() + protected[2:] + "\\")
    declared = (
        (fixture["child_pid"], fixture["start_window"], "fixture"),
        (writer["pid"], writer["start_window"], "second-writer"),
    )
    active, lifecycles = {}, Counter()
    opened, pending = {}, {}
    ambiguous_irps = set()
    witnessed, failed, unresolved = Counter(), Counter(), Counter()
    protected_writes = 0
    for event in sorted(events, key=lambda record: record["ticks"]):
        kind, pid, data = event["id"], event["pid"], event["data"]
        ticks = event["ticks"]
        if event.get("lifecycle"):
            process_id = number(data["ProcessID"])
            if kind == 1:
                actor = next((label for expected, (start, end), label in declared
                              if process_id == expected and start <= ticks <= end), "other")
                if actor != "other":
                    lifecycles[actor] += 1
                active[process_id] = (ticks, actor)
            elif kind == 2:
                active.pop(process_id, None)
            continue
        object_id = number(data.get("FileObject"))
        irp = number(data.get("Irp"))
        birth, actor = active.get(pid, (None, "other"))
        handle = (pid, birth, object_id)
        path_text = (data.get("FileName") or data.get("FilePath") or "").casefold()
        path = "protected" if path_text.startswith(protected_prefixes) else paths.get(path_text)
        if kind == 24:
            if irp in ambiguous_irps:
                continue
            if not irp or irp not in pending:
                continue
            operation, actor, handle, source, destination = pending.pop(irp)
            tracked = source or destination
            status = number(data.get("Status"))
            if status is None:
                if tracked:
                    unresolved[f"{actor}:{operation}:missing-status"] += 1
                continue
            if status & 0x80000000:
                if tracked:
                    failed[f"{actor}:{operation}:{tracked}"] += 1
                continue
            if tracked and handle[1] is None:
                unresolved[f"{actor}:{operation}:process-lifetime-missing"] += 1
            if operation == "open":
                if source:
                    opened[handle] = source
                if source and number(data.get("ExtraInformation")) == 2:  # FILE_CREATED
                    witnessed[f"{actor}:create:{source}"] += 1
            elif tracked and operation == "rename":
                if source and destination:
                    witnessed[f"{actor}:rename:{source}:{destination}"] += 1
                else:
                    unresolved[f"{actor}:rename:path-missing"] += 1
                opened[handle] = destination
            elif source:
                witnessed[f"{actor}:{operation}:{source}"] += 1
            if "protected" in (source, destination) and (
                operation != "open" or number(data.get("ExtraInformation")) == 2
            ):
                protected_writes += 1
            continue
        if kind == 27 and irp in pending:
            operation, owner, obj, source, previous = pending[irp]
            if operation == "rename" and obj == handle and path:
                if previous and previous != path:
                    unresolved[f"{owner}:rename:destination-ambiguous"] += 1
                pending[irp] = (operation, owner, obj, source, path)
            continue
        if kind in {12, 14}:
            opened.pop(handle, None)
        if kind not in {12, 16, 17, 18, 19} or not irp:
            continue
        operation = {12: "open", 16: "write", 18: "delete", 19: "rename"}.get(kind)
        if kind == 17 and number(data.get("InfoClass")) == 20:  # FileEndOfFileInformation
            operation = "resize"
        source = path if kind == 12 else opened.get(handle)
        if irp in pending:
            old_operation, owner, _, old_source, old_destination = pending.pop(irp)
            if old_source or old_destination:
                unresolved[f"{owner}:{old_operation}:irp-reused-before-completion"] += 1
            ambiguous_irps.add(irp)
        if irp in ambiguous_irps:
            if operation and source:
                unresolved[f"{actor}:{operation}:irp-ambiguous"] += 1
        elif operation and object_id:
            pending[irp] = (operation, actor, handle, source, None)
    for operation, actor, _, source, destination in pending.values():
        if source or destination:
            unresolved[f"{actor}:{operation}:completion-missing"] += 1
    for _, _, actor in declared:
        if lifecycles[actor] != 1:
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
