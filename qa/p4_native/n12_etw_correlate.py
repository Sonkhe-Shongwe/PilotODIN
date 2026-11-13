"""Correlate successful Windows Kernel File requests for generated N12 markers."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def number(value):
    if value is None:
        return None
    return int(value, 16 if str(value).lower().startswith("0x") else 10)


def correlate(capture, events):
    fixture, writer = capture["fixture"], capture["second_writer"]
    paths = {}
    for label, path in (
        ("original", fixture["fixture"]), ("renamed", fixture["renamed_fixture"]),
        ("source", writer["source"]), ("destination", writer["destination"]),
    ):
        paths[path.casefold()] = label
        paths[(capture["device"] + path[2:]).casefold()] = label
    actors = {fixture["child_pid"]: "fixture", writer["pid"]: "second-writer"}
    opened, pending = {}, {}
    witnessed, unresolved = Counter(), Counter()
    for event in events:
        kind, pid, data = event["id"], event["pid"], event["data"]
        object_id = number(data.get("FileObject"))
        irp = number(data.get("Irp"))
        actor = actors.get(pid)
        path = paths.get((data.get("FileName") or data.get("FilePath") or "").casefold())
        if kind == 24:
            if not irp or irp not in pending:
                continue
            operation, actor, object_id, source, destination = pending.pop(irp)
            status = number(data.get("Status"))
            if status is None or status & 0x80000000:
                if source:
                    unresolved[f"{actor}:{operation}:unsuccessful-or-missing-status"] += 1
                continue
            if operation == "open":
                opened[actor, object_id] = source
                if source and number(data.get("ExtraInformation")) == 2:  # FILE_CREATED
                    witnessed[f"{actor}:create:{source}"] += 1
            elif source and operation == "rename":
                if destination:
                    witnessed[f"{actor}:rename:{source}:{destination}"] += 1
                else:
                    unresolved[f"{actor}:rename:destination-missing"] += 1
                opened[actor, object_id] = destination
            elif source:
                witnessed[f"{actor}:{operation}:{source}"] += 1
            continue
        if kind == 27 and irp in pending:
            operation, owner, obj, source, previous = pending[irp]
            if operation == "rename" and owner == actor and obj == object_id and path:
                if previous and previous != path:
                    unresolved[f"{owner}:rename:destination-ambiguous"] += 1
                pending[irp] = (operation, owner, obj, source, path)
            continue
        if kind == 14:
            opened.pop((actor, object_id), None)
        if kind not in {12, 16, 17, 18, 19} or not irp:
            continue
        if irp in pending:
            old_operation, owner, _, source, _ = pending.pop(irp)
            if source:
                unresolved[f"{owner}:{old_operation}:irp-reused-before-completion"] += 1
        if not actor or not object_id:
            continue
        operation = {12: "open", 16: "write", 18: "delete", 19: "rename"}.get(kind)
        if kind == 17 and number(data.get("InfoClass")) == 20:  # FileEndOfFileInformation
            operation = "resize"
        if operation:
            source = path if kind == 12 else opened.get((actor, object_id))
            pending[irp] = (operation, actor, object_id, source, None)
    for operation, actor, _, source, _ in pending.values():
        if source:
            unresolved[f"{actor}:{operation}:completion-missing"] += 1
    return {"operations": dict(witnessed), "unresolved": dict(unresolved)}


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
