"""Correlate successful Windows Kernel File requests for generated N12 markers."""
from __future__ import annotations

import json
import ntpath
import re
import sys
from xml.etree import ElementTree as ET
from collections import Counter
from pathlib import Path


# Microsoft FSCTL codes observed in the Kernel-File Event 23 InfoClass field.
FSCTL_GET_REPARSE_POINT = 0x000900A8  # Retrieves reparse-point data; read-only.
FSCTL_GET_OBJECT_ID = 0x0009009C  # Retrieves an existing object identifier; read-only.
FSCTL_READ_USN_JOURNAL = 0x000900BB  # Reads USN change-journal records; read-only.
FSCTL_SET_COMPRESSION = 0x0009C040  # Changes a file/directory compression state.


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


def name_transition_key(kind, data):
    try:
        if kind in {10, 11}:
            key = number(data.get("FileKey", data.get("FileObject")))
        elif kind in {13, 14, 18, 19, 26, 27, 28, 29} or (
            kind == 17 and number(data.get("InfoClass")) not in {19, 20}
        ):
            key = number(data.get("FileKey"))
        else:
            return None
    except (TypeError, ValueError):
        return None
    return key if type(key) is int and key > 0 else None


def correlate_requests(events, resolve_path, classify_process, tracked, record, *,
                       strict=False, details=None, process_bookends=None, thread_bookends=None,
                       rundown=None, rundown_guard_events=None, rundown_recovered_keys=None,
                       rundown_invalidations=None, initial_process_births=None,
                       preopened_control_file_keys=None, preopened_control_file_objects=None):
    """Keep file paths and identities private until the report callback reduces them."""
    active = dict(initial_process_births or {})
    thread_owners = {}
    opened, pending = {}, {}
    file_names = {}
    invalidated_names = {}
    ambiguous_irps = set()
    unresolved = Counter()
    invalidation_reasons = {}
    ordered_events = sorted(events, key=lambda record: record["ticks"])
    name_transition_ticks = set()
    if strict and details is not None:
        # ETW records at the same timestamp have no proven order here.
        name_transition_ticks = {
            (key, event["ticks"])
            for event in ordered_events if not event.get("lifecycle")
            if (key := name_transition_key(event["id"], event["data"]))
        }
    rundown_names = {}
    name_events = {}
    rundown_unsafe_keys = set()
    if strict and rundown is not None:
        for entry in rundown:
            try:
                key = number(entry.get("key"))
            except (TypeError, ValueError):
                continue
            if type(key) is not int or key <= 0:
                continue
            raw_path = entry.get("path")
            path = resolve_path(raw_path) if isinstance(raw_path, str) else None
            rundown_names.setdefault(key, set()).add(path)

        # The rundown is a stop-time snapshot. A key is eligible only when no
        # observed in-window event could have changed or reused its name/object.
        guard_events = ordered_events if rundown_guard_events is None else rundown_guard_events
        name_events = {}
        invalidating_kinds = {11, 12, 14, 18, 19, 27, 29}
        for guarded in guard_events:
            if guarded.get("lifecycle"):
                continue
            kind = guarded.get("id")
            data = guarded.get("data", {})
            if kind == 10:
                # NameCreate is a name association, not by itself a lifetime
                # break. It may corroborate the stop-time rundown only when
                # the observed canonical name is unique and exactly agrees.
                try:
                    name_key = number(data.get("FileKey", data.get("FileObject")))
                except (TypeError, ValueError):
                    name_key = None
                if type(name_key) is int and name_key > 0:
                    raw_name = data.get("FileName")
                    name = resolve_path(raw_name) if isinstance(raw_name, str) else None
                    name_events.setdefault(name_key, set()).add(name)
                    if details is not None:
                        if not isinstance(raw_name, str) or not raw_name.strip():
                            form = "missing"
                        else:
                            normalized = raw_name.replace("/", "\\").casefold()
                            if normalized.startswith("\\device\\"):
                                form = "device-mapped" if name is not None else "device-unmapped"
                                if name is None:
                                    parts = normalized.split("\\")
                                    device_token = parts[2] if len(parts) > 2 else "unknown"
                                    details[f"n12:name-event-10:unmapped-device-{device_token}"] += 1
                            elif re.match(r"^[a-z]:\\", normalized):
                                form = "drive-rooted" if name is not None else "drive-unresolved"
                            elif normalized.startswith("\\\\"):
                                form = "unc"
                            elif normalized.startswith("\\"):
                                form = "rooted-other"
                            else:
                                form = "relative-or-other"
                        details[f"n12:name-event-10:path-form-{form}"] += 1
                continue
            invalidates = kind in invalidating_kinds
            if kind == 17:
                try:
                    info_class = number(data.get("InfoClass"))
                except (TypeError, ValueError):
                    info_class = None
                invalidates = info_class not in {19, 20}
            if not invalidates:
                continue
            for field in ("FileKey", "FileObject"):
                try:
                    key = number(data.get(field))
                except (TypeError, ValueError):
                    key = None
                if type(key) is int and key > 0:
                    rundown_unsafe_keys.add(key)
                    reason = f"event-{kind}:{field}"
                    invalidation_reasons.setdefault(key, Counter())[reason] += 1
                    if rundown_invalidations is not None:
                        rundown_invalidations.setdefault(key, Counter())[reason] += 1

        for key, names in name_events.items():
            rundown_paths = rundown_names.get(key)
            if len(names) == 1 and None not in names and rundown_paths is not None and names == rundown_paths:
                continue
            reason = "event-10:NameAmbiguous" if len(names) != 1 or None in names else "event-10:NameMismatch"
            rundown_unsafe_keys.add(key)
            invalidation_reasons.setdefault(key, Counter())[reason] += 1
            if rundown_invalidations is not None:
                rundown_invalidations.setdefault(key, Counter())[reason] += 1

    def relevant(actor, operation, source, destination):
        return tracked(source) or tracked(destination) or (
            strict and (actor != "other" or operation == "rename" or source is None)
        )

    def flag(actor, reason, event_id, info_class):
        unresolved[f"{actor}:{reason}"] += 1
        if details is not None:
            max_info = 0xFFFFFFFF if event_id == 23 else 255
            info = info_class if type(info_class) is int and 0 <= info_class <= max_info else "unknown"
            if event_id == 23:
                suffix = f":fsctl-0x{info:08X}" if type(info) is int else ":fsctl-unknown"
            else:
                suffix = f":info-{info}" if event_id == 17 else ""
            details[f"{actor}:event-{event_id}{suffix}:{reason}"] += 1

    def count_compression(operation, outcome):
        if details is not None and operation == "compression":
            details[f"compression-request:{outcome}"] += 1

    for event in ordered_events:
        kind, pid, data = event["id"], event["pid"], event["data"]
        ticks = event["ticks"]
        if event.get("lifecycle"):
            process_id = number(data.get("ProcessID", data.get("ProcessId")))
            if kind == 1:
                active[process_id] = ticks
            elif kind == 2:
                active.pop(process_id, None)
            elif details is not None and kind in (3, 4):
                tid = number(data.get("ThreadID", data.get("TThreadId")))
                if kind == 3:
                    thread_owners[tid] = (process_id, active.get(process_id))
                else:
                    thread_owners.pop(tid, None)
            continue
        if strict and details is not None and (key := name_transition_key(kind, data)):
            if kind == 10:
                name = resolve_path(data.get("FileName") or "")
                # A distinct name may be an alias. Only NameDelete resets the
                # prior name evidence for this key.
                if key not in invalidated_names:
                    file_names[key] = name if file_names.get(key, name) == name else None
            elif kind == 11:
                file_names.pop(key, None)
                invalidated_names.pop(key, None)
            elif file_names.get(key) is not None:
                invalidated_names.setdefault(key, (kind, number(data.get("FileObject"))))
        if kind in {10, 11}:
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
            (operation, actor, identity, handle, source, destination, requested,
             event_id, info_class, write_name_context) = pending.pop(irp)
            in_scope = relevant(actor, operation, source, destination)
            status = number(data.get("Status"))
            if status is None:
                count_compression(operation, "missing-status")
                if in_scope and operation != "query":
                    unresolved[f"{actor}:{operation}:missing-status"] += 1
                continue
            if status & 0x80000000:
                count_compression(operation, "failed-completion")
                if in_scope and operation != "query":
                    record(actor, identity, operation, source, destination, requested, ticks, False)
                continue
            if operation == "compression":
                outcome = "unresolved-path" if source is None else (
                    "protected" if tracked(source) else "outside-protected"
                )
                count_compression(operation, f"successful-completion:{outcome}")
            if write_name_context is not None:
                context, _, invalidation = write_name_context.partition(":")
                details[f"write-path-gap:{context}"] += 1
                if invalidation:
                    details[f"write-name-invalidation:{invalidation}"] += 1
            # FILE_SUPERSEDED, FILE_CREATED and FILE_OVERWRITTEN mutate data.
            open_result = number(data.get("ExtraInformation")) if operation == "open" else None
            mutation = operation != "query" and (operation != "open" or open_result in {0, 2, 3})
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
            (operation, owner, identity, obj, source, previous, requested,
             event_id, info_class, write_name_context) = pending[irp]
            if operation == "rename" and obj == handle and path:
                if previous and previous != path:
                    unresolved[f"{owner}:rename:destination-ambiguous"] += 1
                pending[irp] = (operation, owner, identity, obj, source, path, requested,
                                event_id, info_class, write_name_context)
            continue
        if strict and kind == 27 and path and relevant(actor, "rename", None, path):
            unresolved[f"{actor}:rename:request-missing-or-ambiguous"] += 1
            continue
        if kind in {12, 14}:
            opened.pop(handle, None)
        if kind not in {12, 16, 17, 18, 19, 23, 29, 34}:
            continue
        # Event 23 carries the FSCTL code in the provider's InfoClass field.
        # Keep unknown codes unsupported; classify only documented operations.
        info_class = number(data.get("InfoClass")) if kind in {17, 23} else None
        operation = {12: "open", 16: "write", 18: "delete", 19: "rename",
                     23: "unsupported", 29: "unsupported"}.get(kind)
        if kind == 23:
            if not strict:
                operation = None
            elif info_class in {FSCTL_GET_REPARSE_POINT, FSCTL_GET_OBJECT_ID, FSCTL_READ_USN_JOURNAL}:
                operation = "query"
            elif info_class == FSCTL_SET_COMPRESSION:
                operation = "compression"
        if operation == "unsupported" and not strict:
            operation = None
        # QueryEA (34) has no mutation operation, but a reused IRP still
        # invalidates any outstanding mutation that used the same pointer.
        if kind == 17:
            if info_class == 20:  # FileEndOfFileInformation
                operation = "resize"
            elif strict and info_class == 19:  # FileAllocationInformation
                operation = "allocate"
            elif strict:
                operation = "unsupported"
        source = path if kind == 12 else opened.get(handle)
        if strict and source is None and kind in {16, 17, 23} and operation != "query" and details is not None:
            raw_key = data.get("FileKey")
            if kind in {17, 23} and raw_key is None:
                raw_key = data.get("FileObject")
            try:
                context_key = number(raw_key)
            except (TypeError, ValueError):
                context_key = None
            if type(context_key) is not int or context_key <= 0:
                rundown_context = "missing-file-key"
            elif context_key in rundown_unsafe_keys:
                rundown_context = "lifetime-invalidated"
            elif context_key not in rundown_names:
                rundown_context = "not-in-rundown"
            else:
                context_names = rundown_names.get(context_key)
                if context_names is None or len(context_names) != 1 or None in context_names:
                    rundown_context = "ambiguous-rundown-name"
                else:
                    rundown_context = "unusable-rundown-path"
            if kind == 23:
                code_label = f"fsctl-0x{info_class:08X}" if type(info_class) is int else "fsctl-unknown"
                details[f"{actor}:event-23:{code_label}:rundown-context-{rundown_context}"] += 1
            else:
                details[f"{actor}:event-{kind}:{operation}:rundown-context-{rundown_context}"] += 1
            if rundown_context == "lifetime-invalidated":
                for reason in invalidation_reasons.get(context_key, {}):
                    details[f"{actor}:event-{kind}:{operation}:rundown-invalidated-by-{reason}"] += 1
            if type(context_key) is int and context_key > 0:
                for source_label, candidates in (
                    ("event10", name_events.get(context_key, set())),
                    ("rundown", rundown_names.get(context_key, set())),
                ):
                    if not candidates:
                        continue
                    details[f"{actor}:event-{kind}:{operation}:name-candidate-set-size-{source_label}-{len(candidates)}"] += 1
                    for candidate in candidates:
                        category = (
                            "unresolved" if candidate is None
                            else "protected" if tracked(candidate)
                            else "outside-protected"
                        )
                        details[f"{actor}:event-{kind}:{operation}:name-candidates-{source_label}-{category}"] += 1
        if strict and source is None and kind in {16, 17, 23}:
            # Write requests expose FileKey. Set-information events can expose
            # only FileObject. Never substitute a stop-time name for an
            # ambiguous key or a key whose lifetime changed during the trace.
            raw_key = data.get("FileKey")
            if kind in {17, 23} and raw_key is None:
                raw_key = data.get("FileObject")
            try:
                rundown_key = number(raw_key)
            except (TypeError, ValueError):
                rundown_key = None
            names = rundown_names.get(rundown_key)
            if (type(rundown_key) is int and rundown_key > 0
                    and rundown_key not in rundown_unsafe_keys
                    and names is not None and len(names) == 1):
                recovered = next(iter(names))
                if recovered is not None:
                    source = recovered
                    if rundown_recovered_keys is not None:
                        rundown_recovered_keys.add(rundown_key)
                    if details is not None:
                        details[f"{actor}:event-{kind}:rundown-path-recovered"] += 1
        if (details is not None and operation and source is not None
                and actor in {"other", "unattributed"} and tracked(source)):
            file_key = number(data.get("FileKey"))
            if file_key in (preopened_control_file_keys or set()):
                details[f"{actor}:event-{kind}:{operation}:preopened-control-filekey-match"] += 1
            if object_id in (preopened_control_file_objects or set()):
                details[f"{actor}:event-{kind}:{operation}:preopened-control-fileobject-match"] += 1
        write_name_context = None
        if strict and details is not None and kind == 16 and source is None:
            file_key = number(data.get("FileKey"))
            tid = number(data.get("IssuingThreadId", data.get("ThreadId")))
            owner = thread_owners.get(tid)
            issuing_thread_path = False
            attribution = "missing-issuing-thread" if not tid else "unmatched-thread-lifetime"
            if owner is not None and active.get(owner[0]) == owner[1]:
                owner_pid, owner_birth = owner
                attribution = "header-agrees" if pid == owner_pid else "header-differs"
                if owner_birth is not None and opened.get((owner_pid, owner_birth, object_id)) is not None:
                    issuing_thread_path = True
                    details[f"{actor}:event-16:write-request:issuing-thread-handle-path"] += 1
            elif thread_bookends is not None and tid in thread_bookends:
                attribution = "bookend-header-agrees" if pid == thread_bookends[tid] else "bookend-header-differs"
            details[f"{actor}:event-16:write-request:{attribution}"] += 1
            candidate = file_names.get(file_key)
            context = "missing-key" if not file_key else "unseen-key"
            if file_key in file_names:
                context = "ambiguous-name"
            if file_key in invalidated_names:
                context = "invalidated-name"
            elif candidate is not None:
                context = "tracked" if tracked(candidate) else "outside-tracked-paths"
            details[f"{actor}:event-16:write-request:file-key-context-{context}"] += 1
            write_name_context = context
            if (file_key, ticks) in name_transition_ticks:
                write_name_context = "same-timestamp-name-transition"
            elif issuing_thread_path:
                write_name_context = "issuing-thread-handle-candidate"
            if write_name_context == "invalidated-name":
                invalidating_kind, invalidating_object = invalidated_names[file_key]
                object_relation = "missing-object"
                if invalidating_object:
                    object_relation = "same-object" if invalidating_object == object_id else "different-object"
                write_name_context = f"invalidated-name:event-{invalidating_kind}:{object_relation}"
            if birth is None and process_bookends is not None:
                if pid in process_bookends:
                    identity_context = "same-process-at-bookends"
                elif pid in (0, 4):
                    identity_context = "system-header-without-bookends"
                else:
                    identity_context = "missing-process-bookends"
                details[f"{actor}:event-16:write-request:{identity_context}:{context}"] += 1
        if details is not None and operation and operation != "query":
            process_context = (
                "stable-bookend" if process_bookends is not None and pid in process_bookends
                else "etw-lifecycle" if birth is not None
                else "bookends-unavailable" if process_bookends is None
                else "not-stable-at-bookends"
            )
            details[f"{actor}:event-{kind}:{operation}:process-context-{process_context}"] += 1
            if actor == "other":
                details[f"other:event-{kind}:process-image-{identity or 'unavailable'}"] += 1
            if kind in {16, 17, 18, 19, 23, 29}:
                tid = number(data.get("IssuingThreadId", data.get("ThreadId")))
                owner = thread_owners.get(tid)
                owner_pid, owner_birth = None, None
                if owner is not None and active.get(owner[0]) == owner[1]:
                    owner_pid, owner_birth = owner
                    thread_context = "lifecycle-owner-header-agrees" if pid == owner_pid else "lifecycle-owner-header-differs"
                elif thread_bookends is not None and tid in thread_bookends:
                    owner_pid = thread_bookends[tid]
                    owner_birth = active.get(owner_pid)
                    thread_context = "bookend-owner-header-agrees" if pid == owner_pid else "bookend-owner-header-differs"
                else:
                    thread_context = "missing-thread-id" if not tid else "thread-owner-unavailable"
                details[f"{actor}:event-{kind}:{operation}:thread-context-{thread_context}"] += 1
                if owner_pid is not None:
                    owner_actor, owner_identity = classify_process(owner_pid, owner_birth, ticks)
                    owner_label = (
                        owner_identity if owner_actor == "other" and owner_identity
                        else owner_actor
                    )
                    details[f"{actor}:event-{kind}:{operation}:issuing-thread-owner-{owner_label}"] += 1
        count_compression(operation, "observed")
        if not irp or not object_id:
            count_compression(operation, "missing-request-identity")
            if operation and operation != "query" and relevant(actor, operation, source, None):
                unresolved[f"{actor}:{operation}:identity-missing"] += 1
            continue
        if irp in pending:
            old_operation, owner, _, _, old_source, old_destination, *_ = pending.pop(irp)
            count_compression(old_operation, "irp-reused-before-completion")
            if old_operation != "query" and relevant(owner, old_operation, old_source, old_destination):
                unresolved[f"{owner}:{old_operation}:irp-reused-before-completion"] += 1
            ambiguous_irps.add(irp)
        if irp in ambiguous_irps:
            count_compression(operation, "ambiguous-irp")
            if operation and operation != "query" and relevant(actor, operation, source, None):
                unresolved[f"{actor}:{operation}:irp-ambiguous"] += 1
        elif operation:
            pending[irp] = (operation, actor, identity, handle, source, None, ticks, kind,
                            info_class, write_name_context)
    for operation, actor, _, _, source, destination, _, event_id, info_class, _ in pending.values():
        count_compression(operation, "missing-completion")
        if operation != "query" and relevant(actor, operation, source, destination):
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


def preopened_report(capture, events, rundown=None, *, file_keys=None, file_objects=None):
    """Compare ETW path evidence to independently checked fixture handles."""
    control = capture["preopened"]
    devices = {capture["device"].casefold(): capture["protected_root"][:2].casefold()}
    events = sorted(events, key=lambda event: event["ticks"])
    rundown_names = {}
    if rundown is not None:
        for entry in rundown:
            key = number(entry["key"])
            path = canonical_file_path(entry["path"], devices)
            rundown_names.setdefault(key, set()).add(path)
    outcomes = {}
    for label in ("protected", "outside"):
        write = control["writes"][label]
        candidates = [
            event for event in events if not event["lifecycle"] and event["id"] == 16
            and event["pid"] == control["pid"]
            and write["start"] - 100_000 <= event["ticks"] <= write["end"] + 100_000
            and number(event["data"].get("IOSize")) == write["size"]
            and number(event["data"].get("ByteOffset")) == 0
        ]
        outcome = {"request_candidates": len(candidates), "completion": "unverified",
                   "issuing_thread": "unverified", "name_evidence": "unavailable"}
        if rundown is not None:
            outcome["rundown_name"] = "unavailable"
        outcomes[label] = outcome
        if len(candidates) != 1:
            continue
        request = candidates[0]
        data = request["data"]
        if number(data.get("IssuingThreadId", data.get("ThreadId"))) == control["tid"]:
            outcome["issuing_thread"] = "matches"
        irp, key = (number(data.get(field)) for field in ("Irp", "FileKey"))
        if file_keys is not None and type(key) is int and key > 0:
            file_keys[label] = key
        file_object = number(data.get("FileObject"))
        if file_objects is not None and type(file_object) is int and file_object > 0:
            file_objects[label] = file_object
        expected = canonical_file_path(write["path"], devices)
        if expected is None:
            raise ValueError("Invalid generated control path.")
        if rundown is not None:
            names_for_key = rundown_names.get(key)
            if key and names_for_key:
                outcome["rundown_name"] = (
                    "matches-target" if names_for_key == {expected} else "conflicting-or-different"
                )
        if irp:
            for event in events:
                if (event["ticks"] <= request["ticks"] or event["lifecycle"]
                        or number(event["data"].get("Irp")) != irp):
                    continue
                status = number(event["data"].get("Status"))
                if event["id"] == 24 and status is not None:
                    outcome["completion"] = "success" if status == 0 else "nonzero-status"
                break
        names = set()
        if key:
            for event in events:
                if event["ticks"] > request["ticks"]:
                    break
                if event["lifecycle"] or number(event["data"].get("FileKey")) != key:
                    continue
                if event["id"] == 10:
                    names.add(canonical_file_path(event["data"]["FileName"], devices))
                elif event["id"] in (11, 18, 19, 23, 29):
                    names.clear()
        if names:
            outcome["name_evidence"] = (
                "matches-target" if names == {expected} else "conflicting-or-different"
            )
    result = {"scope": "generated writes through pre-opened handles", "targets": outcomes}
    if rundown is not None:
        result["rundown_keys"] = len(rundown_names)
    if "file_lifetime" in capture:
        result["file_lifetime"] = file_lifetime_report(capture["file_lifetime"], events, devices)
    return result


def file_lifetime_report(control, events, devices):
    """Verify the generated in-trace open/write/cleanup/close on one file object."""
    expected = canonical_file_path(control["path"], devices)
    if expected is None:
        raise ValueError("Invalid file lifetime control path.")
    file_events = sorted((event for event in events if not event["lifecycle"]),
                         key=lambda event: event["ticks"])
    opened = [
        event for event in file_events if event["id"] == 12 and event["pid"] == control["pid"]
        and control["start"] <= event["ticks"] <= control["end"]
        and canonical_file_path(event["data"].get("FileName") or "", devices) == expected
    ]
    outcome = {"status": "BLOCKED", "reason": "open-missing-or-ambiguous"}
    if len(opened) != 1:
        return outcome
    opened = opened[0]
    object_id = number(opened["data"].get("FileObject"))
    if not object_id:
        return {"status": "BLOCKED", "reason": "open-file-object-missing"}
    lifetime = []
    for event in file_events:
        if event["ticks"] <= opened["ticks"] or number(event["data"].get("FileObject")) != object_id:
            continue
        if event["id"] == 12:
            break
        lifetime.append(event)
        if event["id"] == 14:
            break
    writes = [
        event for event in lifetime if event["id"] == 16 and event["pid"] == control["pid"]
        and event["ticks"] <= control["end"]
        and number(event["data"].get("IOSize")) == control["size"]
        and number(event["data"].get("ByteOffset")) == 0
    ]
    if len(writes) != 1:
        return {"status": "BLOCKED", "reason": "write-missing-or-ambiguous"}
    write = writes[0]
    ends = [event for event in lifetime if event["id"] in {13, 14}]
    for request, limit, label in ((opened, write["ticks"], "open"),
                                  (write, control["end"], "write")):
        irp = number(request["data"].get("Irp"))
        matches = [event for event in file_events if irp and event is not request
                   and request["ticks"] <= event["ticks"] <= limit
                   and number(event["data"].get("Irp")) == irp]
        next_event = matches[0] if matches else None
        if (next_event is None or next_event["id"] != 24 or
                next_event["ticks"] <= request["ticks"] or
                (len(matches) > 1 and matches[1]["ticks"] == next_event["ticks"]) or
                number(next_event["data"].get("Status")) != 0 or
                (label == "open" and next_event["ticks"] == limit)):
            return {"status": "BLOCKED", "reason": f"{label}-completion-unverified"}
        if label == "write":
            write_completed = next_event["ticks"]
    if ([event["id"] for event in ends] != [13, 14] or
            not write_completed < ends[0]["ticks"] < ends[1]["ticks"]):
        return {"status": "BLOCKED", "reason": "cleanup-close-order-unverified"}
    key = number(write["data"].get("FileKey"))
    name_events = [
        event for event in file_events if key and event["id"] == 10
        and name_transition_key(10, event["data"]) == key
        and control["start"] <= event["ticks"] <= ends[-1]["ticks"]
        and canonical_file_path(event["data"].get("FileName") or "", devices) == expected
    ]
    return {"status": "PASS", "ordered_events": [12, 24, 16, 24, 13, 14],
            "cleanup_key_matches_write": bool(key and name_transition_key(13, ends[0]["data"]) == key),
            "close_key_matches_write": bool(key and name_transition_key(14, ends[1]["data"]) == key),
            "matching_name_before_write": any(event["ticks"] < write["ticks"] for event in name_events),
            "matching_name_at_or_after_write": any(event["ticks"] >= write["ticks"] for event in name_events)}


def decode_rundown_report(source, target):
    namespace = "{http://schemas.microsoft.com/win/2004/08/events/event}"
    provider_guid = "90cbdc39-4a3e-11d1-84f4-0000f80464e3"
    counts = Counter(opcode_36=0, decoded_names=0)
    parser = ET.iterparse(source, events=("start", "end"))
    _, root = next(parser)
    with target.open("w", encoding="utf-8") as output:
        for phase, event in parser:
            if phase != "end" or event.tag.rsplit("}", 1)[-1] != "Event":
                continue
            system = event.find(f"{namespace}System")
            if system is not None:
                provider = system.find(f"{namespace}Provider")
                opcode = system.findtext(f"{namespace}Opcode")
                guid = "" if provider is None else provider.get("Guid", "").strip("{}").casefold()
                if guid == provider_guid and opcode == "36":
                    counts["opcode_36"] += 1
                    fields = {node.get("Name"): node.text for node in event.findall(
                        f"{namespace}EventData/{namespace}Data")}
                    key, name = fields.get("FileObject"), fields.get("FileName")
                    if key and name:
                        output.write(json.dumps({"key": number(key), "path": name}) + "\n")
                        counts["decoded_names"] += 1
            root.remove(event)
    print("Windows trace-report rundown counts: " + json.dumps(counts))


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--decode-rundown":
        decode_rundown_report(*map(Path, sys.argv[2:]))
        return 0
    capture_path, events_path = map(Path, sys.argv[1:3])
    options = sys.argv[3:]
    if options and (options[0] != "--preopened-control" or len(options) > 2):
        raise ValueError("Unexpected correlation options.")
    capture = json.loads(capture_path.read_text(encoding="utf-8-sig"))
    rundown = None
    if len(options) == 2:
        with Path(options[1]).open(encoding="utf-8-sig") as stream:
            rundown = [json.loads(line) for line in stream]
    with events_path.open(encoding="utf-8-sig") as stream:
        events = (json.loads(line) for line in stream)
        report = preopened_report(capture, events, rundown) if options else correlate(capture, events)
    print(json.dumps(report))
    if options and any(target["completion"] != "success" for target in report["targets"].values()):
        return 2
    if "file_lifetime" in report and report["file_lifetime"]["status"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError, StopIteration):
        sys.exit("Kernel File correlation could not decode the captured fields.")
