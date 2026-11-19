"""Correlate successful Windows Kernel File requests for generated N12 markers."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import json
import ntpath
from operator import itemgetter
import re
import sys
from xml.etree import ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


# Microsoft FSCTL codes observed in the Kernel-File Event 23 InfoClass field.
FILE_BASIC_INFORMATION = 4
FSCTL_GET_REPARSE_POINT = 0x000900A8  # Retrieves reparse-point data; read-only.
FSCTL_GET_OBJECT_ID = 0x0009009C  # Retrieves an existing object identifier; read-only.
FSCTL_READ_USN_JOURNAL = 0x000900BB  # Reads USN change-journal records; read-only.
FSCTL_SET_COMPRESSION = 0x0009C040  # Changes a file/directory compression state.
# IRP flags from the Windows Driver Kit (wdm.h). Event 16 reports IOFlags.
IRP_PAGING_IO = 0x00000002
WEBVIEW_SAMPLE_PAIRS = 64
WEBVIEW_SAMPLE_WRITES_PER_PAIR = 16
WEBVIEW_DOMINANT_PAIR_LIMIT = 4096
WEBVIEW_DOMINANT_WRITE_LIMIT = 250_000
WEBVIEW_DOMINANT_ROLE = "webview-network:write"
WEBVIEW_CLEANUP_NAME_GAP = "invalidated-name:event-13:different-object"

WRITE_CONTEXT_IMAGES = {
    "logman.exe", "msbuild.exe", "msmpeng.exe", "powershell.exe", "pwsh.exe",
    "python.exe", "runner.listener.exe", "runner.worker.exe", "svchost.exe",
    "system", "wpr.exe",
}


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


class DominantWebViewWrites:
    """Retain bounded evidence for the dominant pairs and comparison remainder."""

    def __init__(self):
        self.counts = Counter()
        self.requests = defaultdict(list)
        self.retained = 0
        self.pair_limit_reached = False

    def observe(self, pair, request, completed, issue, credit_identity):
        if self.pair_limit_reached:
            return
        if pair not in self.counts and len(self.counts) >= WEBVIEW_DOMINANT_PAIR_LIMIT:
            self.pair_limit_reached = True
            self.counts.clear()
            self.requests.clear()
            return
        self.counts[pair] += 1
        if self.retained < WEBVIEW_DOMINANT_WRITE_LIMIT:
            self.requests[pair].append((request, completed, issue, credit_identity))
            self.retained += 1

    def report(self, eligible, events, resolve_path, tracked, classify_path, credit_path=None):
        if self.pair_limit_reached:
            return {"status": "pair-limit-reached", "eligible": eligible, "pairs": [],
                    "eligible_outside_selected_pairs": None}

        gaps, evidence = [], []
        evidence_by_request = {}
        smaller_outcomes = Counter()
        smaller_total = smaller_retained = smaller_credited = 0
        pairs_to_check = self.counts.most_common(2 if credit_path is None else None)
        for index, (pair, total) in enumerate(pairs_to_check):
            requests = self.requests.get(pair, ())
            if index < 2:
                outcomes = Counter()
                evidence.append((total, len(requests), outcomes))
            else:
                outcomes = smaller_outcomes
                smaller_total += total
                smaller_retained += len(requests)
            for request, completed, issue, credit_identity in requests:
                if issue:
                    outcomes[f"{WEBVIEW_DOMINANT_ROLE}:completion-check:{issue}"] += 1
                else:
                    gaps.append(("webview-network", "write", request, completed))
                    evidence_by_request[id(request)] = outcomes, credit_identity

        def count_outcome(request, label):
            evidence_by_request[id(request)][0][label] += 1

        def credit_verified_path(request, completed, path):
            nonlocal smaller_credited
            outcomes, identity = evidence_by_request[id(request)]
            if identity is not None and credit_path(identity, path, request["ticks"], completed):
                if outcomes is smaller_outcomes:
                    smaller_credited += 1

        summarize_calibration_path_gaps(
            events, gaps, resolve_path, tracked, {}, set(), None, classify_path=classify_path,
            record_request_outcome=count_outcome, index_request_paths=True,
            record_indexed_path=credit_verified_path if credit_path is not None else None,
        )
        def pair_summary(total, retained, outcomes):
            unchecked_by_reason = {"retention-limit": total - retained} if retained < total else {}
            checked = sum(outcomes.values())
            supported = sum(count for label, count in outcomes.items() if ":request-time:candidate-" in label)
            return {"eligible": total, "checked": checked, "supported": supported,
                    "blocked": checked - supported, "unchecked": total - checked,
                    "unchecked_by_reason": unchecked_by_reason, "outcomes": dict(outcomes)}

        pairs = [pair_summary(*group) for group in evidence]
        report = {"status": "partial" if any(pair["unchecked"] for pair in pairs) else "complete",
                  "eligible": eligible, "pairs": pairs,
                  "eligible_outside_selected_pairs": eligible - sum(pair["eligible"] for pair in pairs)}
        if smaller_total:
            report["smaller_pairs"] = pair_summary(smaller_total, smaller_retained, smaller_outcomes)
            report["smaller_pairs"]["credited"] = smaller_credited
        return report


def correlate_requests(events, resolve_path, classify_process, tracked, record, *,
                       strict=False, details=None, process_bookends=None, thread_bookends=None,
                       rundown=None, rundown_guard_events=None, rundown_recovered_keys=None,
                       rundown_invalidations=None, initial_process_births=None,
                       preopened_control_file_keys=None, preopened_control_file_objects=None,
                       rundown_window=None, record_path_gap=None, record_write_name_gap=None,
                       webview_write_candidates=None, classify_webview_path=None, webview_dominant_writes=False,
                       credit_webview_path=None, webview_cleanup_window=None,
                       calibration_diagnostics=None,
                       calibration_end=None, diagnostic_rundown_stop=None,
                       rundown_verification_start=None, rundown_credit=None):
    """Keep file paths and identities private until the report callback reduces them."""
    active = dict(initial_process_births or {})
    thread_owners = {}
    opened, pending = {}, {}
    write_gaps = []
    calibration_gaps = []
    completion_checks = {}
    credit_identities = {}
    webview_gaps = []
    webview_gap_outcomes = Counter()
    webview_pairs = {}
    webview_requests = {}
    webview_gaps_seen = 0
    cleanup_open_gaps = []
    cleanup_open_outcomes = Counter()
    dominant_writes = DominantWebViewWrites() if webview_dominant_writes else None
    calibration_rundown = diagnostic_rundown_stop is not None
    path_gap_context = {}
    opens_with_process_lifetime = set()
    file_names = {}
    invalidated_names = {}
    ambiguous_irps = set()
    unresolved = Counter()
    invalidation_reasons = {}
    ordered_events = sorted(events, key=lambda record: record["ticks"])
    name_transition_ticks = set()
    process_transition_ticks = set()
    thread_transition_ticks = set()
    track_write_names = strict and (details is not None or record_write_name_gap is not None
                                    or webview_write_candidates is not None)
    if track_write_names:
        # ETW records at the same timestamp have no proven order here.
        name_transition_ticks = {
            (key, event["ticks"])
            for event in ordered_events if not event.get("lifecycle")
            if (key := name_transition_key(event["id"], event["data"]))
        }
    if strict and (details is not None or rundown_verification_start is not None
                   or webview_write_candidates is not None):
        for event in ordered_events:
            if not event.get("lifecycle"):
                continue
            kind, data, ticks = event["id"], event["data"], event["ticks"]
            if kind in (1, 2):
                pid = number(data.get("ProcessID", data.get("ProcessId")))
                process_transition_ticks.add((pid, ticks))
            elif kind in (3, 4):
                tid = number(data.get("ThreadID", data.get("TThreadId")))
                thread_transition_ticks.add((tid, ticks))
    rundown_names = {}
    name_events = {}
    rundown_unsafe_keys = set()
    rundown_object_keys = defaultdict(set)
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
        if calibration_rundown:
            invalidating_kinds.update({13, 26, 28})
        for guarded in guard_events:
            if guarded.get("lifecycle"):
                continue
            kind = guarded.get("id")
            data = guarded.get("data", {})
            if rundown_verification_start is not None and kind not in {10, 11, 24}:
                obj, key = (number(data.get(field)) for field in ("FileObject", "FileKey"))
                if type(obj) is int and obj > 0 and type(key) is int and key > 0:
                    rundown_object_keys[obj].add(key)
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

    def completion_identity_issue(request, completion, handle, actor):
        owner_pid, owner_birth, _ = handle
        requested, completed = request["ticks"], completion["ticks"]
        if (owner_birth is None or not owner_birth < requested < completed
                or active.get(owner_pid) != owner_birth or actor == "unattributed"
                or (owner_pid, requested) in process_transition_ticks
                or (owner_pid, completed) in process_transition_ticks):
            return "process-lifetime-unverified-at-completion"
        if any(number(completion["data"].get(field)) not in {None, 0, number(request["data"].get(field))}
               for field in ("FileObject", "FileKey")):
            return "completion-file-identity-conflict"
        return None

    def verified_webview_write_identity(request, completed, handle, actor, identity):
        if identity is None:
            return None
        data = request["data"]
        tid = number(data.get("IssuingThreadId", data.get("ThreadId")))
        pid, birth, obj = handle
        irp = number(data.get("Irp"))
        if (type(obj) is not int or obj <= 0 or type(irp) is not int or irp <= 0
                or (tid, request["ticks"]) in thread_transition_ticks
                or classify_process(pid, birth, completed) != (actor, identity)):
            return None
        return identity

    def record_webview_outcome(request, label):
        pair, first = webview_requests[id(request)]
        pair["outcomes"][label] += 1
        if first:
            webview_gap_outcomes[label] += 1

    def count_compression(operation, outcome):
        if details is not None and operation == "compression":
            details[f"compression-request:{outcome}"] += 1

    def process_label(pid, birth, ticks, actor, identity):
        if birth is None or birth >= ticks or (pid, ticks) in process_transition_ticks:
            return "unverified"
        if actor == "preopened-control":
            return actor
        if actor == "other" and identity:
            return identity if identity in WRITE_CONTEXT_IMAGES else "other-verified-image"
        return "unverified"

    def capture_phase(ticks):
        if rundown_window is None:
            return "unavailable"
        start, stop = rundown_window
        return "before-wpr-stop" if ticks < start else (
            "during-wpr-stop" if ticks <= stop else "after-wpr-stop"
        )

    def write_capture_context(ticks, header_label, tid):
        issuer_label = "unverified"
        if tid and (tid, ticks) not in thread_transition_ticks:
            owner = thread_owners.get(tid)
            if owner is None and thread_bookends is not None and tid in thread_bookends:
                owner_pid = thread_bookends[tid]
                owner = (owner_pid, active.get(owner_pid))
            if owner is not None:
                owner_pid, owner_birth = owner
                if owner_birth is not None and active.get(owner_pid) == owner_birth:
                    actor, identity = classify_process(owner_pid, owner_birth, ticks)
                    issuer_label = process_label(owner_pid, owner_birth, ticks, actor, identity)
        return f"{capture_phase(ticks)}:header-{header_label}:issuer-{issuer_label}"

    for event in ordered_events:
        kind, pid, data = event["id"], event["pid"], event["data"]
        ticks = event["ticks"]
        if event.get("lifecycle"):
            process_id = number(data.get("ProcessID", data.get("ProcessId")))
            if kind == 1:
                active[process_id] = ticks
            elif kind == 2:
                active.pop(process_id, None)
            elif kind in (3, 4) and (details is not None or record_path_gap is not None or track_write_names):
                tid = number(data.get("ThreadID", data.get("TThreadId")))
                if kind == 3:
                    thread_owners[tid] = (process_id, active.get(process_id))
                else:
                    thread_owners.pop(tid, None)
            continue
        if track_write_names and (key := name_transition_key(kind, data)):
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
        if (strict and (details is not None or webview_cleanup_window is not None) and kind == 12
                and birth is not None and birth < ticks):
            opens_with_process_lifetime.add(id(event))
        actor, identity = classify_process(pid, birth, ticks)
        handle = (pid, birth, object_id)
        path = resolve_path(data.get("FileName") or data.get("FilePath") or "")
        if kind == 24:
            if irp in ambiguous_irps:
                continue
            if not irp or irp not in pending:
                continue
            (operation, actor, identity, handle, source, destination, requested,
             event_id, info_class, write_gap, protected_system_write, request) = pending.pop(irp)
            gap = path_gap_context.pop(irp, None)
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
            if write_gap is not None:
                write_request, write_name_context, capture_context = write_gap
                context, _, invalidation = write_name_context.partition(":")
                details[f"write-path-gap:{context}"] += 1
                if invalidation:
                    details[f"write-name-invalidation:{invalidation}"] += 1
                write_gaps.append((write_request, ticks, capture_context))
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
                    if gap is not None:
                        file_key, lifetime, thread, name_context = gap
                        if record_path_gap is not None:
                            record_path_gap(actor, event_id, operation, file_key, lifetime, thread)
                        if record_write_name_gap is not None and name_context is not None:
                            record_write_name_gap(actor, thread, name_context)
                        if (webview_cleanup_window is not None and actor == "webview-network"
                                and operation == "write" and name_context == WEBVIEW_CLEANUP_NAME_GAP):
                            issue = completion_identity_issue(request, event, handle, actor)
                            start, end = webview_cleanup_window
                            if not issue and not start <= requested < ticks <= end:
                                issue = "write-outside-audit-window"
                            if not issue:
                                verified = (thread == "thread-header-agrees" and
                                            verified_webview_write_identity(request, ticks, handle, actor, identity)
                                            is not None)
                                if not verified:
                                    issue = "write-identity-unverified"
                            if issue:
                                cleanup_open_outcomes[issue] += 1
                            else:
                                cleanup_open_gaps.append((request, ticks, None))
                        if (webview_write_candidates is not None and actor == "webview-network"
                                and operation == "write" and thread == "thread-header-agrees"
                                and name_context in {"tracked", "outside-tracked-paths"}):
                            webview_gaps_seen += 1
                            key = number(request["data"].get("FileKey"))
                            obj = number(request["data"].get("FileObject"))
                            pair = (key, obj)
                            if dominant_writes is not None:
                                issue = completion_identity_issue(request, event, handle, actor)
                                credit_identity = None
                                if credit_webview_path is not None and not issue:
                                    credit_identity = verified_webview_write_identity(request, ticks, handle, actor, identity)
                                dominant_writes.observe(pair, request, ticks, issue, credit_identity)
                            if pair in webview_pairs or len(webview_pairs) < WEBVIEW_SAMPLE_PAIRS:
                                evidence = webview_pairs.get(pair)
                                if evidence is None:
                                    evidence = webview_pairs[pair] = {"eligible": 0, "outcomes": Counter()}
                                evidence["eligible"] += 1
                                if evidence["eligible"] <= WEBVIEW_SAMPLE_WRITES_PER_PAIR:
                                    webview_requests[id(request)] = (evidence, evidence["eligible"] == 1)
                                    if dominant_writes is None:
                                        issue = completion_identity_issue(request, event, handle, actor)
                                    if issue:
                                        record_webview_outcome(request, f"{actor}:{operation}:completion-check:{issue}")
                                    else:
                                        webview_gaps.append((actor, operation, request, ticks))
                    if calibration_diagnostics is not None and operation in {"write", "resize"}:
                        calibration_gaps.append((actor, operation, request, ticks))
                        if rundown_verification_start is not None:
                            if rundown_credit is not None and actor == "other":
                                credit_identities[id(request)] = identity
                            issue = completion_identity_issue(request, event, handle, actor)
                            if issue:
                                completion_checks[id(request)] = issue
                if source or destination:
                    record(actor, identity, operation, source, destination, requested, ticks, True)
                    if protected_system_write is not None:
                        details[f"protected-system-write-paging:{protected_system_write}"] += 1
            continue
        if kind == 27 and irp in pending:
            (operation, owner, identity, obj, source, previous, requested,
             event_id, info_class, write_gap, protected_system_write, request) = pending[irp]
            if operation == "rename" and obj == handle and path:
                if previous and previous != path:
                    unresolved[f"{owner}:rename:destination-ambiguous"] += 1
                pending[irp] = (operation, owner, identity, obj, source, path, requested,
                                event_id, info_class, write_gap, protected_system_write, request)
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
        if strict and source is None and kind in {16, 17, 23} and not calibration_rundown:
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
        if track_write_names and kind == 16 and source is None:
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
                    if details is not None:
                        details[f"{actor}:event-16:write-request:issuing-thread-handle-path"] += 1
            elif thread_bookends is not None and tid in thread_bookends:
                attribution = "bookend-header-agrees" if pid == thread_bookends[tid] else "bookend-header-differs"
            candidate = file_names.get(file_key)
            context = "missing-key" if not file_key else "unseen-key"
            if file_key in file_names:
                context = "ambiguous-name"
            if file_key in invalidated_names:
                context = "invalidated-name"
            elif candidate is not None:
                context = "tracked" if tracked(candidate) else "outside-tracked-paths"
            if details is not None:
                details[f"{actor}:event-16:write-request:{attribution}"] += 1
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
            if details is not None and birth is None and process_bookends is not None:
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
            path_gap_context.pop(irp, None)
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
            write_gap = None
            if details is not None and write_name_context is not None:
                header_label = process_label(pid, birth, ticks, actor, identity)
                if header_label == "unverified" and pid in (0, 4):
                    header_label = "system-context"
                capture_context = write_capture_context(ticks, header_label, tid)
                write_gap = (event, write_name_context, capture_context)
            protected_system_write = None
            if (strict and details is not None and preopened_control_file_keys
                    and preopened_control_file_objects and kind == 16 and pid == 4 and tracked(source)):
                key_matches = number(data.get("FileKey")) in preopened_control_file_keys
                object_matches = object_id in preopened_control_file_objects
                target = "control-key-and-object" if key_matches and object_matches else "other-protected-identity"
                protected_system_write = f"{target}:{capture_phase(ticks)}:{write_paging_flag(data)}"
            pending[irp] = (operation, actor, identity, handle, source, None, ticks, kind,
                            info_class, write_gap, protected_system_write, event)
            if ((record_path_gap is not None or record_write_name_gap is not None
                 or webview_write_candidates is not None)
                    and source is None and operation != "query" and kind in {16, 17, 23}):
                try:
                    file_key = number(data.get("FileKey"))
                except ValueError:
                    file_key = None
                try:
                    tid = number(data.get("IssuingThreadId", data.get("ThreadId")))
                except ValueError:
                    tid = None
                owner = thread_owners.get(tid)
                if owner is None or owner[1] is None or active.get(owner[0]) != owner[1]:
                    thread = "unverified-thread" if tid else "no-thread-id"
                    if actor == "other" and thread_bookends is not None and tid in thread_bookends:
                        owner_pid = thread_bookends[tid]
                        if active.get(owner_pid) is not None:
                            thread = "bookend-header-agrees" if owner_pid == pid else "bookend-header-differs"
                else:
                    # Header comparison is descriptive, never used for attribution.
                    thread = "thread-header-agrees" if owner[0] == pid else "thread-header-differs"
                path_gap_context[irp] = ("file-key" if type(file_key) is int and file_key > 0 else "no-file-key",
                                         "header-lifetime" if birth is not None else "no-header-lifetime",
                                         thread, write_name_context)
    unmatched_writes = Counter()
    for operation, actor, _, _, source, destination, requested, event_id, info_class, *_ in pending.values():
        count_compression(operation, "missing-completion")
        if operation != "query" and relevant(actor, operation, source, destination):
            flag(actor, f"{operation}:completion-missing", event_id, info_class)
            if calibration_diagnostics is not None and operation == "write":
                remaining = calibration_end - requested
                bucket = ("last-10ms" if remaining <= 100_000 else
                          "10-to-100ms-before-end" if remaining <= 1_000_000 else
                          "over-100ms-before-end")
                unmatched_writes[f"{actor}:{bucket}"] += 1
    if webview_write_candidates is not None:
        summarize_calibration_path_gaps(
            ordered_events, webview_gaps, resolve_path, tracked, {}, set(), None,
            classify_path=classify_webview_path, record_request_outcome=record_webview_outcome,
        )
        pairs = []
        for evidence in webview_pairs.values():
            outcomes = evidence["outcomes"]
            checked = sum(outcomes.values())
            supported = sum(count for label, count in outcomes.items()
                            if ":request-time:candidate-" in label)
            pairs.append({
                "eligible": evidence["eligible"], "checked": checked, "supported": supported,
                "blocked": checked - supported, "unchecked": evidence["eligible"] - checked,
                "outcomes": dict(outcomes),
            })
        webview_write_candidates.update(
            eligible=webview_gaps_seen, sampled=len(pairs),
            outcomes=dict(webview_gap_outcomes), pairs=pairs,
            eligible_outside_sample=webview_gaps_seen - sum(pair["eligible"] for pair in pairs),
        )
        if dominant_writes is not None:
            def credit_compared_path(identity, path, requested, completed):
                if not credit_webview_path(identity, path, requested, completed):
                    return False
                reason = "webview-network:write:path-missing"
                unresolved[reason] -= 1
                if unresolved[reason] == 0:
                    del unresolved[reason]
                return True

            webview_write_candidates["dominant"] = dominant_writes.report(
                webview_gaps_seen, ordered_events, resolve_path, tracked, classify_webview_path,
                credit_compared_path if credit_webview_path is not None else None,
            )
    if calibration_diagnostics is not None:
        credited_paths = Counter()
        remaining_paths = Counter() if rundown_credit is not None else None

        def credit_path(actor, operation, request, completed, source):
            if id(request) not in credit_identities:
                return False
            record(actor, credit_identities[id(request)], operation, source, None,
                   request["ticks"], completed, True)
            reason = f"{actor}:{operation}:path-missing"
            unresolved[reason] -= 1
            if unresolved[reason] == 0:
                del unresolved[reason]
            scope = "protected" if tracked(source) else "outside-protected"
            credited_paths[f"{actor}:{operation}:{scope}"] += 1
            return True

        calibration_diagnostics.update(
            path_candidates=summarize_calibration_path_gaps(
                ordered_events, calibration_gaps, resolve_path, tracked,
                rundown_names, rundown_unsafe_keys, diagnostic_rundown_stop,
                rundown_verification_start=rundown_verification_start,
                completion_checks=completion_checks,
                rundown_object_keys=rundown_object_keys,
                credit_path=credit_path if rundown_credit is not None else None,
                remaining_paths=remaining_paths,
            ),
            unmatched_write_timing=dict(unmatched_writes),
        )
        if rundown_credit is not None:
            for label, count in unresolved.items():
                if label.endswith(":path-missing"):
                    actor, operation, _ = label.split(":")
                    if operation not in {"write", "resize"}:
                        remaining_paths[f"{actor}:{operation}:outside-rundown-credit-scope"] = count
            rundown_credit["credited_paths"] = dict(credited_paths)
            rundown_credit["remaining_paths_by_reason"] = dict(remaining_paths)
    if webview_cleanup_window is not None:
        if cleanup_open_gaps:
            cleanup_open_outcomes.update(summarize_write_gap_open_evidence(
                ordered_events, cleanup_open_gaps, opens_with_process_lifetime, resolve_path, tracked,
                Counter(), Counter(), Counter(), Counter(), classify_path=classify_webview_path,
                verify_file_identity=True,
            ))
        webview_write_candidates["cleanup_open_evidence"] = {
            "status": "evaluated", "eligible": sum(cleanup_open_outcomes.values()),
            "outcomes": dict(cleanup_open_outcomes),
        }
    if write_gaps:
        name_change_events = Counter()
        class_4_outcomes = Counter()
        no_open_contexts = Counter()
        no_open_paths = Counter()
        evidence = summarize_write_gap_open_evidence(
            ordered_events, write_gaps, opens_with_process_lifetime, resolve_path, tracked,
            name_change_events, class_4_outcomes, no_open_contexts, no_open_paths,
        )
        for outcome, count in evidence.items():
            details[f"write-gap-open-evidence:{outcome}"] += count
        for context, count in no_open_contexts.items():
            details[f"write-gap-no-open-context:{context}"] += count
        for (context, outcome), count in no_open_paths.items():
            details[f"write-gap-no-open-path:{context}:{outcome}"] += count
        for event_label, count in name_change_events.items():
            details[f"write-gap-name-change-event:{event_label}"] += count
        for outcome, count in class_4_outcomes.items():
            details[f"write-gap-class-4-trial:{outcome}"] += count
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
    outcomes, identities, control_requests = {}, {}, {}
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
        control_requests[label] = request
        data = request["data"]
        if number(data.get("IssuingThreadId", data.get("ThreadId"))) == control["tid"]:
            outcome["issuing_thread"] = "matches"
        irp, key = (number(data.get(field)) for field in ("Irp", "FileKey"))
        if file_keys is not None and type(key) is int and key > 0:
            file_keys[label] = key
        file_object = number(data.get("FileObject"))
        identities[label] = (key, file_object)
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
    result = {
        "scope": "generated writes through pre-opened handles", "targets": outcomes,
        "preopened_path_validation": preopened_path_validation(
            events, devices, control_requests, outcomes, control["writes"],
        ),
    }
    if rundown is not None:
        result["rundown_keys"] = len(rundown_names)
    if rundown is not None and "untouched" in control:
        result["control_write_timing"] = control_write_timing(
            capture, events, devices, rundown_names, identities, outcomes,
        )
    if "file_lifetime" in capture:
        result["file_lifetime"] = file_lifetime_report(capture["file_lifetime"], events, devices)
    if "in_capture_name_control" in capture:
        result["in_capture_name_control"] = file_lifetime_report(capture["in_capture_name_control"], events, devices)
    if "basic_info_control" in capture:
        result["basic_info_control"] = file_lifetime_report(capture["basic_info_control"], events, devices)
    if "known_write" in capture:
        control = capture["known_write"]
        validate_known_target(capture, control, devices, "known-write.bin")
        observed = file_lifetime_report(control, events, devices, verify_write_path=True)
        path_result = observed.get("write_object_path", observed)
        known_write = known_file_result("write", "known-write.bin", path_result["reason"],
                                       "completed-open-and-write")
        if "observed_end_events" in observed:
            known_write["cleanup_close"] = {
                "status": observed["status"], "reason": observed["reason"],
                "observed_events": observed["observed_end_events"],
            }
        result["known_write"] = known_write
    if "known_resize" in capture:
        control = capture["known_resize"]
        filename = "known-resize.bin"
        expected = validate_known_target(capture, control, devices, filename)
        before, after = control["before_bytes"], control["after_bytes"]
        if type(before) is not int or type(after) is not int or not 0 <= after < before:
            raise ValueError("Invalid generated resize sizes.")
        reason = resize_path_reason(control, events, expected, devices)
        result["known_resize"] = known_file_result("resize", filename, reason, "completed-open-and-resize")
        result["known_resize"].update(before_bytes=before, after_bytes=after)
    return result


def validate_known_target(capture, control, devices, filename):
    fixture = ntpath.dirname(canonical_file_path(capture["protected_root"], devices))
    expected = canonical_file_path(control["path"], devices)
    if expected != ntpath.join(fixture, filename):
        raise ValueError("Unexpected known-file control target.")
    return expected


def known_file_result(operation, filename, blocked_reason, evidence):
    """Expose only the verified fixture-relative name."""
    return {"operation": operation, "expected_file": filename,
            "matched_file": filename if blocked_reason is None else None,
            "status": "PASS" if blocked_reason is None else "BLOCKED",
            "reason": evidence if blocked_reason is None else blocked_reason}


def preopened_resize_report(capture, events, rundown, devices, process_birth, capture_bounds, rundown_window):
    """Compare the same known resize with and without the collector's rundown credit."""
    filename = "known-resize.bin"
    control = capture["known_preopened_resize"]
    expected = validate_known_target(capture, control, devices, filename)
    start, end = capture_bounds
    before, after = control["before_bytes"], control["after_bytes"]
    if type(before) is not int or type(after) is not int or not 0 <= after < before:
        raise ValueError("Invalid generated pre-opened resize sizes.")

    def report(reason, baseline="unverified"):
        return {**known_file_result("resize", filename, reason, "completed-resize-credited-by-rundown"),
                "before_bytes": before, "after_bytes": after, "without_rundown": baseline}

    if process_birth is None or process_birth >= start:
        return report("resize-process-lifetime-unverified")
    if rundown_window is None or not start <= control["start"] <= control["end"] <= rundown_window[0]:
        return report("resize-window-unverified")
    pid = capture["preopened"]["pid"]
    events = sorted(events, key=lambda event: event["ticks"])
    file_events = [event for event in events if not event["lifecycle"]]
    requests = [
        event for event in file_events
        if event["pid"] == pid and event["id"] == 17
        and number(event["data"].get("InfoClass")) == 20  # FileEndOfFileInformation
        and control["start"] - 100_000 <= event["ticks"] <= control["end"] + 100_000
    ]
    if len(requests) != 1:
        return report("resize-missing-or-ambiguous")
    request = requests[0]
    completed = successful_completion(file_events, request, rundown_window[0])
    if completed is None:
        return report("resize-completion-unverified-before-rundown")
    def compare(rundown=None):
        matches = []
        diagnostics = {}

        def record(_actor, identity, operation, source, _destination, request_ticks, completion_ticks, success):
            if (identity == pid and operation == "resize" and success
                    and request_ticks == request["ticks"] and completion_ticks == completed):
                matches.append(source)

        def classify_process(owner, birth, ticks):
            if owner == pid and birth is not None and ticks == request["ticks"]:
                return "other", owner
            return "fixture-context", None

        rundown_start, rundown_stop = rundown_window
        correlate_requests(
            events, lambda value: canonical_file_path(value, devices),
            classify_process, lambda path: path == expected,
            record, strict=True, initial_process_births={pid: process_birth},
            rundown=rundown, calibration_diagnostics=diagnostics, calibration_end=end,
            diagnostic_rundown_stop=rundown_stop if rundown is not None else None,
            rundown_verification_start=rundown_start if rundown is not None else None,
            rundown_credit={} if rundown is not None else None,
        )
        return matches, diagnostics["path_candidates"]

    baseline, _ = compare()
    if baseline:
        return report("resize-already-has-path", "path-present")
    matches, diagnostics = compare(rundown)
    result = report(None if matches == [expected] else "resize-rundown-path-unverified", "path-unresolved")
    prefix = "other:resize:"
    result["path_evidence"] = {}
    for key, count in diagnostics.items():
        if key.startswith(prefix):
            stage, outcome = key.removeprefix(prefix).split(":", 1)
            outcome = outcome.replace("outside-protected", "other-file").replace("protected", "fixture-target")
            result["path_evidence"][f"{stage}:{outcome}"] = count
    return result


def completion_evidence(file_events, request, before):
    """Return the uniquely ordered successful completion or a fixed blocker."""
    irp = number(request["data"].get("Irp"))
    if not irp:
        return None, "request-id-missing"
    matches = [event for event in file_events if event is not request
               and request["ticks"] <= event["ticks"] < before
               and number(event["data"].get("Irp")) == irp]
    if not matches:
        return None, "missing-before-boundary"
    first = matches[0]
    if first["ticks"] == request["ticks"] or (len(matches) > 1 and matches[1]["ticks"] == first["ticks"]):
        return None, "ambiguous-order"
    if first["id"] != 24:
        return None, "intervening-request-event"
    status = number(first["data"].get("Status"))
    if status is None:
        return None, "status-missing"
    if status != 0:
        return None, "failed" if type(status) is int and status & 0x80000000 else "status-nonzero"
    return first, None


def successful_completion(file_events, request, before):
    completion, _ = completion_evidence(file_events, request, before)
    return completion["ticks"] if completion is not None else None


def write_paging_flag(data):
    try:
        flags = number(data.get("IOFlags"))
    except ValueError:
        return "unavailable"
    if type(flags) is not int or not 0 <= flags <= 0xFFFFFFFF:
        return "unavailable"
    return "set" if flags & IRP_PAGING_IO else "clear"


def control_write_timing(capture, events, devices, rundown_names, identities, outcomes):
    """Measure successful System-context requests on independently located fixtures."""
    control = capture["preopened"]
    stop_start, stop_end = (capture[key] for key in ("rundown_start_ticks", "rundown_stop_ticks"))
    capture_end = capture["end_ticks"]
    if not capture["start_ticks"] <= stop_start <= stop_end <= capture_end:
        raise ValueError("Invalid WPR stop window.")
    flush_start, flush_end = control["writes"]["protected"]["flush_window"]
    if not (control["writes"]["protected"]["end"] < flush_start <= flush_end < stop_start):
        raise ValueError("Invalid protected-control flush window.")

    def phase(ticks, label):
        if ticks > stop_end:
            return "after-wpr-stop"
        if ticks >= stop_start:
            return "during-wpr-stop"
        write = control["writes"]["outside" if label == "outside" else "protected"]
        if ticks < write["start"]:
            return "before-write"
        if ticks <= write["end"]:
            return "application-write"
        if label == "outside":
            return "after-write-before-wpr-stop"
        if ticks < flush_start:
            return "after-write-before-flush"
        if ticks <= flush_end:
            return "explicit-flush"
        return "after-flush-before-wpr-stop"

    by_irp = defaultdict(list)
    for event in events:
        if not event["lifecycle"] and (irp := number(event["data"].get("Irp"))):
            by_irp[irp].append(event)

    def completion(event):
        return successful_completion(by_irp[number(event["data"].get("Irp"))],
                                     event, capture_end + 1)

    comparison_identity, comparison_evidence = timing_comparison_identity(
        capture, events, devices, rundown_names, identities, by_irp,
    )
    if comparison_identity is not None:
        identities["untouched"] = comparison_identity
    results = {}
    for label in ("protected", "outside", "untouched"):
        key, file_object = identities.get(label, (None, None))
        established = (key is not None if label == "untouched" else bool(
            key and file_object and outcomes[label]["issuing_thread"] == "matches"
            and outcomes[label]["completion"] == "success"
            and outcomes[label]["rundown_name"] == "matches-target"
        ))
        observed = Counter()
        paging_flags = Counter()
        unverified_completions = 0
        flushes = 0
        if established:
            for event in events:
                kind, data, ticks = event["id"], event["data"], event["ticks"]
                if (event["lifecycle"] or kind not in {16, 17, 21}
                        or number(data.get("FileKey")) != key
                        or number(data.get("FileObject")) != file_object):
                    continue
                if kind == 21:
                    thread = number(data.get("IssuingThreadId", data.get("ThreadId")))
                    if (label == "protected" and event["pid"] == control["pid"]
                            and thread == control["tid"] and flush_start <= ticks <= flush_end
                            and (completed := completion(event)) is not None and completed <= flush_end):
                        flushes += 1
                    continue
                if event["pid"] != 4 or (kind == 17 and number(data.get("InfoClass")) != 20):
                    continue
                completed = completion(event)
                if completed is None:
                    unverified_completions += 1
                    continue
                operation = "write" if kind == 16 else "resize"
                request_phase = phase(ticks, label)
                observed[f"{operation}:{request_phase}:{phase(completed, label)}"] += 1
                if kind == 16:
                    paging_flags[f"{request_phase}:{write_paging_flag(data)}"] += 1
        result = {"identity": "file-key-and-object" if established else "unverified",
                  "system_successful_operations": dict(observed),
                  "system_successful_write_paging_flags": dict(paging_flags),
                  "system_requests_without_verified_success": unverified_completions}
        if label == "protected":
            result["explicit_flush_trace"] = "confirmed" if flushes == 1 else "unverified"
        if label == "untouched":
            result["identity_evidence"] = comparison_evidence
        results[label] = result
    return results


def timing_comparison_identity(capture, events, devices, rundown_names, identities, by_irp):
    control = capture["preopened"]
    comparison = control["untouched"]
    if not isinstance(comparison, dict):
        return None, "in-trace-open-unavailable"
    open_start, open_end = comparison["open_window"]
    read_start, read_end = comparison["read_window"]
    if not (capture["start_ticks"] <= open_start <= open_end <= read_start <= read_end
            <= min(write["start"] for write in control["writes"].values())):
        return None, "invalid-open-read-windows"

    def resolve_path(value):
        return canonical_file_path(value, devices)

    def requests(kind, start, end):
        return [
            event for event in events if not event["lifecycle"] and event["id"] == kind
            and event["pid"] == control["pid"] and start <= event["ticks"] <= end
            and number(event["data"].get("IssuingThreadId", event["data"].get("ThreadId"))) == control["tid"]
        ]

    expected = resolve_path(comparison["path"])
    opens = [event for event in requests(12, open_start, open_end)
             if resolve_path(event["data"].get("FileName") or "") == expected]
    if expected is None or len(opens) != 1:
        return None, "open-unverified"
    opened = opens[0]
    open_irp = number(opened["data"].get("Irp"))
    open_completed = successful_completion(by_irp[open_irp], opened, open_end + 1)
    if open_completed is None or not any(
        event["id"] == 24 and event["ticks"] == open_completed
        and number(event["data"].get("ExtraInformation")) == 1 for event in by_irp[open_irp]
    ):
        return None, "existing-file-open-completion-unverified"
    file_object = number(opened["data"].get("FileObject"))
    reads = [event for event in requests(15, read_start, read_end)
             if number(event["data"].get("FileObject")) == file_object
             and number(event["data"].get("ByteOffset")) == 0
             and number(event["data"].get("IOSize")) == comparison["size"]]
    if not file_object or len(reads) != 1 or open_completed >= reads[0]["ticks"]:
        return None, "read-unverified"
    read = reads[0]
    read_completed = successful_completion(by_irp[number(read["data"].get("Irp"))], read, read_end + 1)
    key = number(read["data"].get("FileKey"))
    if read_completed is None or not key or any(
        key == other_key or file_object == other_object for other_key, other_object in identities.values()
    ):
        return None, "read-completion-or-file-identity-unverified"
    if rundown_names.get(key, {expected}) != {expected}:
        return None, "conflicting-rundown-name"
    if any(
        not event["lifecycle"] and opened["ticks"] <= event["ticks"] <= capture["end_ticks"]
        and number(event["data"].get("FileObject")) == file_object
        and number(event["data"].get("FileKey")) not in {None, 0, key}
        for event in events
    ):
        return None, "conflicting-file-key"
    reason, _ = write_object_path_conflict(
        events, opened, open_completed, read, read_completed, expected, resolve_path,
        observe_until=capture["end_ticks"],
    )
    return (None, reason) if reason else ((key, file_object), "completed-open-and-read")


def check_write_object_path(events, opened, write, write_completed, expected, devices, *, operation="write"):
    """Check path continuity from a completed open to the controlled mutation."""
    object_id = number(write["data"].get("FileObject"))
    key = number(write["data"].get("FileKey"))
    if not object_id or not key or number(opened["data"].get("FileObject")) != object_id:
        return f"{operation}-object-or-key-unverified"
    def resolve_path(value):
        return canonical_file_path(value, devices)

    if resolve_path(opened["data"].get("FileName") or "") != expected:
        return "open-path-mismatch"
    open_completed = successful_completion(events, opened, write["ticks"])
    if open_completed is None:
        return "open-completion-unverified"
    reason, _ = write_object_path_conflict(events, opened, open_completed, write, write_completed,
                                           expected, resolve_path)
    return reason


def write_object_path_conflict(events, anchor, anchor_completed, write, write_completed,
                               expected, resolve_path, *, basic_info_completion=None, observe_until=None):
    object_id = number(write["data"].get("FileObject"))
    key = number(write["data"].get("FileKey"))
    names = set()
    observation_end = write_completed if observe_until is None else observe_until
    for event in events:
        ticks = event["ticks"]
        if ticks > observation_end:
            break
        if event.get("lifecycle") or event is anchor:
            continue
        kind, data = event["id"], event["data"]
        same_key = name_transition_key(kind, data) == key or number(data.get("FileKey")) == key
        file_object = number(data.get("FileObject"))
        same_object = file_object == object_id
        if kind == 10 and same_key:
            names.add(resolve_path(data.get("FileName") or ""))
            if ticks == write["ticks"]:
                return "ambiguous-event-order", event
        if kind == 11 and same_key and ticks < anchor["ticks"]:
            names.clear()
        if ticks < anchor["ticks"] or not (same_object or same_key):
            continue

        reason = path_transition_reason(kind, data, same_object, file_object)
        # FileBasicInformation sets timestamps and attributes. The control
        # accepts only an ordered, successful operation before the write.
        if (kind == 17 and number(data.get("InfoClass")) == FILE_BASIC_INFORMATION
                and basic_info_completion is not None and anchor_completed < ticks < write["ticks"]
                and basic_info_completion(event) is not None):
            reason = None
        if reason:
            if ticks in {anchor["ticks"], anchor_completed, write["ticks"], write_completed}:
                return "ambiguous-event-order", event
            return reason, event
    if names - {expected}:
        return "conflicting-or-unmapped-name", None
    return None, None


def path_transition_reason(kind, data, same_object, file_object):
    if kind == 12 and same_object or kind in {13, 14} and (same_object or not file_object):
        return "file-object-lifetime-changed"
    if (kind in {11, 18, 19, 26, 27, 28, 29}
            or kind == 17 and number(data.get("InfoClass")) not in {19, 20}
            or kind == 23 and number(data.get("InfoClass")) not in {
                FSCTL_GET_REPARSE_POINT, FSCTL_GET_OBJECT_ID, FSCTL_READ_USN_JOURNAL, FSCTL_SET_COMPRESSION,
            }):
        return "possible-name-change"
    return None


def verified_write_completion(irp_events, write, completed):
    # Keep every event at either boundary, where a tie can invalidate the completion.
    get_ticks = itemgetter("ticks")
    first = bisect_left(irp_events, write["ticks"], key=get_ticks)
    last = bisect_right(irp_events, completed, lo=first, key=get_ticks)
    return successful_completion(irp_events[first:last], write, completed + 1) == completed


def name_change_event_label(event):
    kind = event["id"]
    label = f"event-{kind}"
    if kind not in {17, 23}:
        return label
    info = number(event["data"].get("InfoClass"))
    limit = 0xFFFFFFFF if kind == 23 else 255
    if type(info) is not int or not 0 <= info <= limit:
        return label + ("-fsctl-unknown" if kind == 23 else "-info-unknown")
    return label + (f"-fsctl-0x{info:08X}" if kind == 23 else f"-info-{info}")


def request_time_file_key_evidence(write, completed, object_events, key_events, irp_events,
                                   resolve_path, classify_path, *, first_observation=None):
    """Check an observed name lifetime on the request's key without assigning a writer."""
    ticks, data = write["ticks"], write["data"]
    key = number(data.get("FileKey"))
    if type(key) is not int or key <= 0:
        return "missing-file-key"
    if not verified_write_completion(irp_events, write, completed):
        return "write-completion-unverified"

    if first_observation is not None:
        ticks = first_observation
    names = []
    last_delete = None
    tied_name_reset = False
    for event in key_events:
        if event["ticks"] > ticks:
            break
        if event["ticks"] == ticks and event["id"] in {10, 11}:
            return "ambiguous-event-order"
        if event["id"] == 11:
            if event["ticks"] != last_delete:
                tied_name_reset = bool(names and names[-1]["ticks"] == event["ticks"])
            last_delete = event["ticks"]
            names.clear()
        elif event["id"] == 10:
            tied_name_reset |= event["ticks"] == last_delete
            names.append(event)
    if tied_name_reset:
        return "ambiguous-event-order"
    if not names:
        return "no-prior-name-in-lifetime"
    paths = {resolve_path(event["data"].get("FileName") or "") for event in names}
    if None in paths or len(paths) != 1:
        return "conflicting-or-unmapped-name"

    path = next(iter(paths))
    anchor = names[0]
    start = anchor["ticks"]
    for event in object_events:
        if start <= event["ticks"] <= completed:
            observed_key = number(event["data"].get("FileKey"))
            if observed_key not in {None, 0, key}:
                return "conflicting-object-file-key"

    related = {id(event): event for event in (*object_events, *key_events)
               if start <= event["ticks"] <= completed}
    reason, _ = write_object_path_conflict(
        sorted(related.values(), key=lambda event: event["ticks"]), anchor, start,
        write, completed, path, resolve_path,
    )
    return reason or classify_path(path)


class RequestPathHistory:
    """Index the path boundaries once for a file pair with many writes."""

    def __init__(self, key, obj, object_events, key_events, resolve_path):
        self.name_ticks, self.names = [], []
        self.conflict_ticks = [event["ticks"] for event in object_events
                               if number(event["data"].get("FileKey")) not in {None, 0, key}]
        self.transition_ticks, self.transitions = [], []
        related = {id(event): event for event in (*object_events, *key_events)}
        for event in sorted(related.values(), key=itemgetter("ticks")):
            kind, data = event["id"], event["data"]
            file_object = number(data.get("FileObject"))
            reason = path_transition_reason(kind, data, file_object == obj, file_object)
            if reason:
                self.transition_ticks.append(event["ticks"])
                self.transitions.append(reason)

        anchor = path = last_name = last_delete = None
        conflict = tied_reset = False
        for event in key_events:
            kind, tick = event["id"], event["ticks"]
            if kind == 10:
                tied_reset |= tick == last_delete
                observed = resolve_path(event["data"].get("FileName") or "")
                if anchor is None:
                    anchor, path = tick, observed
                conflict |= observed is None or observed != path
                last_name = tick
            elif kind == 11:
                if tick != last_delete:
                    tied_reset = anchor is not None and last_name == tick
                last_delete = tick
                anchor = path = None
                conflict = False
            else:
                continue
            self.name_ticks.append(tick)
            self.names.append((anchor, path, conflict, tied_reset))

    def resolve(self, write, completed, irp_events):
        if not verified_write_completion(irp_events, write, completed):
            return "write-completion-unverified", None
        requested = write["ticks"]
        prior = bisect_left(self.name_ticks, requested)
        if prior < len(self.name_ticks) and self.name_ticks[prior] == requested:
            return "ambiguous-event-order", None
        if not prior:
            return "no-prior-name-in-lifetime", None
        anchor, path, conflict, tied_reset = self.names[prior - 1]
        if tied_reset:
            return "ambiguous-event-order", None
        if anchor is None:
            return "no-prior-name-in-lifetime", None
        if conflict:
            return "conflicting-or-unmapped-name", None

        first_conflict = bisect_left(self.conflict_ticks, anchor)
        if first_conflict < len(self.conflict_ticks) and self.conflict_ticks[first_conflict] <= completed:
            return "conflicting-object-file-key", None
        first_transition = bisect_left(self.transition_ticks, anchor)
        if first_transition < len(self.transition_ticks) and self.transition_ticks[first_transition] <= completed:
            if self.transition_ticks[first_transition] in {anchor, requested, completed}:
                return "ambiguous-event-order", None
            return self.transitions[first_transition], None
        end = bisect_right(self.name_ticks, completed)
        if self.names[end - 1][2]:
            return "conflicting-or-unmapped-name", None
        return None, path


def summarize_calibration_path_gaps(events, gaps, resolve_path, tracked,
                                    rundown_names, rundown_unsafe_keys, rundown_stop, *, classify_path=None,
                                    rundown_verification_start=None, completion_checks=None,
                                    rundown_object_keys=None, credit_path=None, remaining_paths=None,
                                    record_request_outcome=None, index_request_paths=False, record_indexed_path=None):
    if not gaps:
        return {}
    by_object, by_key, by_irp = (defaultdict(list) for _ in range(3))
    keys, irps = set(), set()
    requested_keys = defaultdict(set)
    for _, _, request, _ in gaps:
        data = request["data"]
        key = number(data.get("FileKey"))
        keys.add(key)
        requested_keys[number(data.get("FileObject"))].add(key)
        irps.add(number(data.get("Irp")))
    for event in events:
        if event.get("lifecycle"):
            continue
        kind, data = event["id"], event["data"]
        key = None if kind == 24 else name_transition_key(kind, data) or number(data.get("FileKey"))
        if kind not in {10, 11, 24} and (obj := number(data.get("FileObject"))) in requested_keys:
            # A write changes neither the name nor the lifetime. Keep it in
            # the object history only if it can contradict an observed key.
            observed_keys = requested_keys[obj]
            if kind != 16 or key not in {None, 0} and (len(observed_keys) > 1 or key not in observed_keys):
                by_object[obj].append(event)
        if kind != 16 and key and key in keys:
            by_key[key].append(event)
        irp = number(data.get("Irp"))
        if irp and irp in irps:
            by_irp[irp].append(event)

    def scope(path):
        if classify_path is not None:
            return classify_path(path)
        return "candidate-protected" if tracked(path) else "candidate-outside-protected"

    counts, path_histories = Counter(), {}
    for actor, operation, request, completed in gaps:
        data = request["data"]
        key = number(data.get("FileKey"))
        object_id, irp = number(data.get("FileObject")), number(data.get("Irp"))
        object_history, key_history = by_object[object_id], by_key[key]
        if index_request_paths and type(key) is int and key > 0:
            pair = (key, object_id)
            if pair not in path_histories:
                path_histories[pair] = RequestPathHistory(key, object_id, object_history, key_history, resolve_path)
            issue, path = path_histories[pair].resolve(request, completed, by_irp[irp])
            outcome = issue or scope(path)
            if issue is None and record_indexed_path is not None:
                record_indexed_path(request, completed, path)
        else:
            outcome = request_time_file_key_evidence(
                request, completed, object_history, key_history, by_irp[irp], resolve_path, scope,
            )
        if outcome == "write-completion-unverified":
            outcome = "request-completion-unverified"
        label = f"{actor}:{operation}:request-time:{outcome}"
        counts[label] += 1
        if record_request_outcome is not None:
            record_request_outcome(request, label)
        missing_prior_name = outcome == "no-prior-name-in-lifetime"
        if remaining_paths is not None and not missing_prior_name:
            remaining_paths[f"{actor}:{operation}:request-time:{outcome}"] += 1
        if rundown_stop is None:
            continue
        names = rundown_names.get(key, set())
        if outcome == "request-completion-unverified":
            counts[f"{actor}:{operation}:rundown:{outcome}"] += 1
            continue
        if type(key) is not int or key <= 0:
            outcome = "missing-file-key"
        elif completed >= rundown_stop:
            outcome = "completion-at-or-after-rundown"
        elif not names:
            outcome = "not-in-rundown"
        elif any(number(event["data"].get("FileKey")) not in {None, 0, key}
                 for event in by_object[object_id]):
            outcome = "conflicting-object-file-key"
        elif key in rundown_unsafe_keys or object_id in rundown_unsafe_keys:
            outcome = "lifetime-invalidated"
        elif len(names) != 1 or None in names:
            outcome = "ambiguous-or-unmapped-name"
        else:
            outcome = scope(next(iter(names)))
        counts[f"{actor}:{operation}:rundown:{outcome}"] += 1
        if missing_prior_name:
            counts[f"{actor}:{operation}:no-prior-name-rundown:{outcome}"] += 1
            credited = False
            remaining_reason = "rundown-verification-unavailable"
            if rundown_verification_start is not None:
                if outcome not in {"candidate-protected", "candidate-outside-protected"}:
                    verification = outcome
                elif completed >= rundown_verification_start:
                    verification = "completion-at-or-after-rundown-start"
                elif id(request) in completion_checks:
                    verification = completion_checks[id(request)]
                elif rundown_object_keys.get(object_id, set()) != {key}:
                    verification = "object-key-association-unverified"
                else:
                    verification = ("consistent-protected-path" if outcome == "candidate-protected"
                                    else "consistent-outside-protected-path")
                    if credit_path is not None:
                        credited = credit_path(actor, operation, request, completed, next(iter(names)))
                counts[f"{actor}:{operation}:no-prior-name-completion-check:{verification}"] += 1
                remaining_reason = (
                    "completion-check:role-ineligible" if verification.startswith("consistent-")
                    else f"completion-check:{verification}"
                )
            if remaining_paths is not None and not credited:
                remaining_paths[f"{actor}:{operation}:{remaining_reason}"] += 1
    return dict(counts)


def preopened_path_validation(events, devices, requests, outcomes, writes):
    """Compare request-time candidates with exact fixture paths verified by Windows."""
    file_events = [event for event in events if not event["lifecycle"]]

    def resolve_path(value):
        return canonical_file_path(value, devices)

    report = {}
    for label, outcome in outcomes.items():
        # The fixture's verified handle supplies the reference for this comparison.
        # The stop-time rundown measures a different point in the file's lifetime.
        if (outcome["issuing_thread"], outcome["completion"]) != ("matches", "success"):
            report[label] = "control-request-unverified"
            continue
        request = requests[label]
        data, ticks = request["data"], request["ticks"]
        object_id, key = number(data.get("FileObject")), number(data.get("FileKey"))
        if type(object_id) is not int or object_id <= 0:
            report[label] = "control-object-unverified"
            continue
        object_events = [
            event for event in file_events if event["id"] not in {10, 11}
            and number(event["data"].get("FileObject")) == object_id
        ]
        if any(event["id"] == 12 and event["ticks"] <= ticks for event in object_events):
            report[label] = "same-object-open-observed"
            continue
        irp = number(data.get("Irp"))
        irp_events = [event for event in file_events if number(event["data"].get("Irp")) == irp]
        completed = successful_completion(irp_events, request, file_events[-1]["ticks"] + 1)
        if completed is None:
            report[label] = "write-completion-unverified"
            continue
        key_events = [
            event for event in file_events if event["id"] != 24
            and (name_transition_key(event["id"], event["data"]) or number(event["data"].get("FileKey"))) == key
        ]
        expected = resolve_path(writes[label]["path"])
        report[label] = request_time_file_key_evidence(
            request, completed, object_events, key_events, irp_events, resolve_path,
            lambda path: "matches-handle-path" if path == expected else "different-from-handle-path",
        )
    return report


def summarize_write_gap_open_evidence(events, gaps, opens_with_process_lifetime, resolve_path, tracked,
                                      name_change_events, class_4_outcomes, no_open_contexts,
                                      no_open_paths, *, classify_path=None, verify_file_identity=False):
    """Count evidence for unresolved writes without using it to classify them."""
    by_object, by_key, by_irp, process_transitions = (defaultdict(list) for _ in range(4))
    objects = {number(write["data"].get("FileObject")) for write, _, _ in gaps}
    keys = {number(write["data"].get("FileKey")) for write, _, _ in gaps}
    related_irps = set()
    for event in events:
        kind, data = event["id"], event["data"]
        if event.get("lifecycle"):
            if kind in {1, 2}:
                pid = number(data.get("ProcessID", data.get("ProcessId")))
                process_transitions[pid].append(event["ticks"])
            continue
        obj = number(data.get("FileObject"))
        key = None if kind == 24 else name_transition_key(kind, data) or number(data.get("FileKey"))
        related_object = kind not in {10, 11} and obj in objects
        related_key = key and key in keys
        if related_object:
            by_object[obj].append(event)
        if related_key:
            by_key[key].append(event)
        if related_object or related_key:
            related_irps.add(number(data.get("Irp")))
    # A related IRP may be reused by an unrelated object. Preserve its full history.
    for event in events:
        if event.get("lifecycle"):
            continue
        data = event["data"]
        irp = number(data.get("Irp"))
        if irp and irp in related_irps:
            by_irp[irp].append(event)

    def evaluate(write, completed, capture_context):
        data = write["data"]
        file_object = number(data.get("FileObject"))
        object_events = by_object[file_object]
        prior_opens = [event for event in object_events
                       if event["id"] == 12 and event["ticks"] <= write["ticks"]]
        if not prior_opens:
            no_open_contexts[capture_context] += 1
            outcome = request_time_file_key_evidence(
                write, completed, object_events, by_key[number(data.get("FileKey"))],
                by_irp[number(data.get("Irp"))], resolve_path,
                lambda path: "candidate-protected" if tracked(path) else "candidate-outside-protected",
            )
            no_open_paths[(capture_context, outcome)] += 1
            return "no-observed-open"
        opened = prior_opens[-1]
        if (opened["ticks"] == write["ticks"] or
                (len(prior_opens) > 1 and prior_opens[-2]["ticks"] == opened["ticks"])):
            return "ambiguous-event-order"
        open_completion, open_blocker = completion_evidence(
            by_irp[number(opened["data"].get("Irp"))], opened, write["ticks"],
        )
        if open_completion is None:
            return f"open-completion-{open_blocker}" if verify_file_identity else "open-completion-unverified"
        open_completed = open_completion["ticks"]
        if (id(opened) not in opens_with_process_lifetime or any(
            opened["ticks"] <= tick <= completed for tick in process_transitions[opened["pid"]]
        )):
            return "open-process-lifetime-unverified"
        path = resolve_path(opened["data"].get("FileName") or "")
        if path is None:
            return "open-path-unmapped"
        key = number(data.get("FileKey"))
        if not key or (verify_file_identity and (type(key) is not int or key < 0)):
            return "write-key-unverified"
        if successful_completion(by_irp[number(data.get("Irp"))], write, completed + 1) != completed:
            return "write-completion-unverified"
        if verify_file_identity:
            if number(open_completion["data"].get("FileObject")) not in {None, 0, file_object}:
                return "open-completion-file-identity-conflict"
            if number(open_completion["data"].get("FileKey")) not in {None, 0, key}:
                return "open-completion-file-key-conflict"
            conflicting_event = next((event for event in object_events if
                opened["ticks"] <= event["ticks"] <= completed
                and number(event["data"].get("FileKey")) not in {None, 0, key}
            ), None)
            if conflicting_event is not None:
                return f"same-object-file-key-conflict:event-{conflicting_event['id']}"

        relevant_events = {id(event): event for event in object_events + by_key[key]}
        related = sorted(relevant_events.values(), key=lambda event: event["ticks"])
        if classify_path is not None:
            candidate = classify_path(path)
        else:
            candidate = "candidate-protected" if tracked(path) else "candidate-outside-protected"
        reason, event = write_object_path_conflict(
            related, opened, open_completed, write, completed, path, resolve_path,
        )
        if reason == "possible-name-change":
            name_change_events[name_change_event_label(event)] += 1
            if event["id"] == 17 and number(event["data"].get("InfoClass")) == FILE_BASIC_INFORMATION:
                def completion(request):
                    return successful_completion(
                        by_irp[number(request["data"].get("Irp"))], request, write["ticks"],
                    )

                remaining, blocker = write_object_path_conflict(
                    related, opened, open_completed, write, completed, path, resolve_path,
                    basic_info_completion=completion,
                )
                if remaining == "possible-name-change":
                    remaining = name_change_event_label(blocker)
                class_4_outcomes[remaining or candidate] += 1
        return reason or candidate

    return Counter(evaluate(write, completed, context) for write, completed, context in gaps)


def shared_fixture_write(file_events, writes, before):
    """Return the verified fixture request or a fixed rejection reason."""
    if len(writes) < 2:
        return None, "too-few-candidates"
    if len({event["ticks"] for event in writes}) != len(writes):
        return None, "tied-candidate-timestamps"
    first, last = writes[0], writes[-1]
    request_ids = {number(event["data"].get("Irp")) for event in writes}
    if request_ids & {None, 0}:
        return None, "candidate-request-id-unavailable"
    if len(request_ids) != 1:
        return None, "candidate-request-ids-differ"
    file_keys = {number(event["data"].get("FileKey")) for event in writes}
    if file_keys & {None, 0}:
        return None, "candidate-file-key-unavailable"
    if len(file_keys) != 1:
        return None, "candidate-file-keys-differ"
    irp = next(iter(request_ids))
    completion = successful_completion(file_events, last, before)
    if completion is None:
        return None, "last-candidate-completion-unverified"
    related = [event for event in file_events if first["ticks"] <= event["ticks"] < before
               and number(event["data"].get("Irp")) == irp]
    if len(related) != len(writes) + 1 or any(event is not candidate
                                            for event, candidate in zip(related, writes)):
        return None, "extra-or-intervening-request-events"
    return last, None


def control_opens(control, file_events, expected, devices):
    return [event for event in file_events if event["id"] == 12 and event["pid"] == control["pid"]
            and control["start"] <= event["ticks"] <= control["end"]
            and canonical_file_path(event["data"].get("FileName") or "", devices) == expected]


def resize_path_reason(control, events, expected, devices):
    """Attribute the fixture's sole FileEndOfFileInformation request through completion."""
    file_events = [event for event in events if not event["lifecycle"]]
    opens = control_opens(control, file_events, expected, devices)
    if len(opens) != 1:
        return "open-missing-or-ambiguous"
    opened = opens[0]
    object_id = number(opened["data"].get("FileObject"))
    if not object_id:
        return "open-file-object-missing"
    requests = [
        event for event in file_events if event["id"] == 17 and event["pid"] == control["pid"]
        and opened["ticks"] < event["ticks"] <= control["end"]
        and number(event["data"].get("InfoClass")) == 20  # FileEndOfFileInformation
        and number(event["data"].get("FileObject")) == object_id
    ]
    if len(requests) != 1:
        return "resize-missing-or-ambiguous"
    request = requests[0]
    completed = successful_completion(file_events, request, control["end"] + 1)
    if completed is None:
        return "resize-completion-unverified"
    return check_write_object_path(file_events, opened, request, completed, expected, devices, operation="resize")


def file_lifetime_report(control, events, devices, *, verify_write_path=False):
    """Verify the generated in-trace open, write and handle teardown."""
    expected = canonical_file_path(control["path"], devices)
    if expected is None:
        raise ValueError("Invalid file lifetime control path.")
    file_events = sorted((event for event in events if not event["lifecycle"]),
                         key=lambda event: event["ticks"])
    opened = control_opens(control, file_events, expected, devices)
    outcome = {"status": "BLOCKED", "reason": "open-missing-or-ambiguous"}
    two_handles = control.get("two_handles", False)
    if len(opened) != (2 if two_handles else 1):
        return outcome
    first_open = opened[0] if two_handles else None
    opened = opened[-1]
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
    offset = control.get("offset", 0)
    lifetime_writes = [event for event in lifetime if event["id"] == 16 and event["ticks"] <= control["end"]]
    same_process = [event for event in lifetime_writes if event["pid"] == control["pid"]]
    same_size = [event for event in same_process if number(event["data"].get("IOSize")) == control["size"]]
    same_offset = [event for event in same_size if number(event["data"].get("ByteOffset")) == offset]
    writes = same_offset
    if control.get("prior_name_control"):
        write_start, write_end = control["write_window"]
        writes = [event for event in same_offset if write_start <= event["ticks"] <= write_end
                  and write_paging_flag(event["data"]) != "set"]
    ambiguous = None
    if len(writes) != 1:
        result = {"status": "BLOCKED", "reason": "write-missing-or-ambiguous"}
        if control.get("prior_name_control"):
            result["write_candidates"] = {"same_object": len(lifetime_writes), "same_process": len(same_process),
                                          "same_size": len(same_size), "same_offset": len(same_offset),
                                          "in_write_window_nonpaging": len(writes)}
            request_ids = Counter(number(event["data"].get("Irp")) for event in writes)
            without_id = request_ids.pop(None, 0) + request_ids.pop(0, 0)
            completed = sum(successful_completion(file_events, event, control["end"] + 1) is not None
                            for event in writes)
            result["request_relationships"] = {
                "distinct_request_ids": len(request_ids),
                "request_ids_shared_by_candidates": sum(count > 1 for count in request_ids.values()),
                "candidates_without_request_id": without_id,
                "candidates_with_ordered_successful_completion": completed,
            }
            recovered, rejection = shared_fixture_write(file_events, writes, control["end"] + 1)
            if rejection is not None:
                result["shared_request_rejection"] = rejection
            if recovered is not None:
                ambiguous = result
        if ambiguous is None:
            return result
        write = recovered
    else:
        write = writes[0]
    first_write = writes[0]["ticks"]
    ends = [event for event in lifetime if event["id"] in {13, 14}]
    open_completed = successful_completion(file_events, opened, first_write)
    if open_completed is None:
        if ambiguous is not None:
            ambiguous["shared_request_path_trial"] = "open-completion-unverified"
            return ambiguous
        return {"status": "BLOCKED", "reason": "open-completion-unverified"}
    write_completed = successful_completion(file_events, write, control["end"] + 1)
    if write_completed is None:
        return {"status": "BLOCKED", "reason": "write-completion-unverified"}
    key = number(write["data"].get("FileKey"))
    end_evidence = {
        "observed_end_events": [event["id"] for event in ends],
        "end_order": [
            "before-write-completion" if event["ticks"] < write_completed else
            "at-write-completion" if event["ticks"] == write_completed else "after-write-completion"
            for event in ends
        ],
        "end_timestamps_distinct": len({event["ticks"] for event in ends}) == len(ends),
        "end_key_matches_write": [
            bool(key and name_transition_key(event["id"], event["data"]) == key)
            for event in ends
        ],
    }
    name_events = [
        event for event in file_events if key and event["id"] == 10
        and name_transition_key(10, event["data"]) == key
        and control["start"] <= event["ticks"] <= control["end"]
        and canonical_file_path(event["data"].get("FileName") or "", devices) == expected
    ]
    ordered = (end_evidence["observed_end_events"] == [13, 14] and
               write_completed < ends[0]["ticks"] < ends[1]["ticks"])
    result = {"status": "PASS" if ordered else "BLOCKED",
              "reason": None if ordered else "cleanup-close-order-unverified",
              "open_and_write_completed": True, **end_evidence,
              "matching_name_before_write": any(event["ticks"] < first_write for event in name_events),
              "matching_name_at_or_after_write": any(event["ticks"] >= first_write for event in name_events)}
    if control.get("prior_name_control"):
        object_events = [
            event for event in file_events if event["id"] not in {10, 11, 24}
            and number(event["data"].get("FileObject")) == object_id
        ]
        key_events = [
            event for event in file_events if event["id"] != 24
            and (name_transition_key(event["id"], event["data"]) or number(event["data"].get("FileKey"))) == key
        ]
        verdict = request_time_file_key_evidence(
            write, write_completed, object_events, key_events, file_events,
            lambda value: canonical_file_path(value, devices),
            lambda path: "matches-handle-path" if path == expected else "different-from-handle-path",
            first_observation=first_write if ambiguous is not None else None,
        )
        result["request_time_path"] = verdict
        if ambiguous is not None:
            if not ordered or verdict != "matches-handle-path":
                ambiguous["shared_request_path_trial"] = verdict
                if verdict == "different-from-handle-path":
                    ambiguous["request_time_path"] = verdict
                return ambiguous
            result["write_candidates"] = ambiguous["write_candidates"]
            result["request_relationships"] = ambiguous["request_relationships"]
            result["shared_request_path_trial"] = verdict
    if control.get("basic_info"):
        metadata = [event for event in lifetime if event["id"] == 17
                    and event["pid"] == control["pid"]
                    and open_completed < event["ticks"] < write["ticks"]
                    and number(event["data"].get("InfoClass")) == FILE_BASIC_INFORMATION]
        def completion(request):
            return successful_completion(file_events, request, write["ticks"])

        result["timestamp_trace"] = (
            "PASS" if len(metadata) == 1 and completion(metadata[0]) is not None else "BLOCKED"
        )
        reason, blocker = write_object_path_conflict(
            file_events, opened, open_completed, write, write_completed, expected,
            lambda value: canonical_file_path(value, devices),
        )
        result["first_blocking_operation"] = (
            name_change_event_label(blocker) if reason == "possible-name-change" else reason
        )
        remaining, _ = write_object_path_conflict(
            file_events, opened, open_completed, write, write_completed, expected,
            lambda value: canonical_file_path(value, devices), basic_info_completion=completion,
        )
        result["class_4_path_trial"] = {"status": "BLOCKED" if remaining else "PASS", "reason": remaining}
    if two_handles:
        second_boundary_before_completion = any(
            event["id"] in {12, 13, 14} and opened["ticks"] < event["ticks"] <= write_completed
            and number(event["data"].get("FileObject")) == object_id
            for event in file_events
        )
        result["overlap"] = overlapping_handle_report(
            file_events, first_open, opened, open_completed, write, key,
            second_boundary_before_completion, expected, devices,
        )
    if two_handles or verify_write_path:
        reason = check_write_object_path(file_events, opened, write, write_completed, expected, devices)
        result["write_object_path"] = {"status": "BLOCKED" if reason else "PASS", "reason": reason}
    return result


def overlapping_handle_report(events, first_open, second_open, second_completed, write, key,
                              second_ended_early, expected, devices):
    first_object = number(first_open["data"].get("FileObject"))
    second_object = number(second_open["data"].get("FileObject"))
    if not first_object or first_object == second_object:
        return {"status": "BLOCKED", "reason": "distinct-file-objects-unverified"}
    if successful_completion(events, first_open, second_open["ticks"]) is None:
        return {"status": "BLOCKED", "reason": "first-open-completion-unverified"}
    if second_ended_early:
        return {"status": "BLOCKED", "reason": "second-object-ended-before-write-completion"}
    first_events = [
        event for event in events if first_open["ticks"] < event["ticks"] <= write["ticks"]
        and event["id"] in {12, 13, 14} and number(event["data"].get("FileObject")) == first_object
    ]
    if (not first_events or [event["id"] for event in first_events] not in ([13], [13, 14])
            or not second_completed < first_events[0]["ticks"] < write["ticks"]):
        return {"status": "BLOCKED", "reason": "first-cleanup-between-second-open-and-write-unverified"}
    cleanup = first_events[0]
    if not key or name_transition_key(13, cleanup["data"]) != key:
        return {"status": "BLOCKED", "reason": "cleanup-and-write-shared-key-unverified"}

    # Observe name evidence through the write without attributing the write
    # by FileKey. An observed open already supplies the control's actual path.
    names = set()
    first_invalidation = None
    tied_transition = False
    for event in events:
        if event["ticks"] > write["ticks"]:
            break
        if event["lifecycle"]:
            continue
        data = event["data"]
        if name_transition_key(event["id"], data) != key:
            continue
        if event["ticks"] == write["ticks"]:
            tied_transition = True
            continue
        if event["id"] == 10:
            if first_invalidation is None:
                names.add(canonical_file_path(data.get("FileName") or "", devices))
        elif event["id"] == 11:
            names.clear()
            first_invalidation = None
        elif len(names) == 1 and None not in names and first_invalidation is None:
            first_invalidation = event
    return {"status": "PASS", "first_cleanup_before_second_write": True,
            "matching_name_in_key_lifetime": expected in names,
            "conflicting_name_in_key_lifetime": bool(names - {expected}),
            "name_transition_tied_with_write": tied_transition,
            "first_invalidation_is_first_cleanup": first_invalidation is cleanup and not tied_transition}


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
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError, StopIteration):
        sys.exit("Kernel File correlation could not decode the captured fields.")
