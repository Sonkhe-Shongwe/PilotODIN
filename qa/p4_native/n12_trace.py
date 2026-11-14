"""Offline reduction of one disposable N12 Windows trace. Stdlib only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import ntpath
import os
import re
import stat
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
EVENT_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"
ROLES = {"app", "backend", "driver", "calibration"}
MINIMUM_MARKERS = ("idle", "launch", "quality", "close", "reopen", "exit")
MUTATIONS = {
    "WriteFile": "write", "SetEndOfFileInformationFile": "resize",
    "SetAllocationInformationFile": "resize", "SetBasicInformationFile": "metadata",
    "SetSecurityFile": "metadata", "DeleteFile": "delete",
}
EVIDENCE_ERRORS = (ValueError, KeyError, OSError, TypeError, AttributeError,
                   StopIteration, ET.ParseError, csv.Error)


class EvidenceValidationError(ValueError):
    """An evidence failure whose message is safe to print."""


def require(condition, message):
    if not condition:
        raise EvidenceValidationError(message)


@contextmanager
def evidence_stage(label):
    try:
        yield
    except EvidenceValidationError as exc:
        raise EvidenceValidationError(f"{label}: {exc}") from exc
    except EVIDENCE_ERRORS as exc:
        # Parser messages can contain raw event fields or private paths.
        raise EvidenceValidationError(f"{label}: {type(exc).__name__}") from exc


def windows_path(value):
    drive, tail = ntpath.splitdrive(value)
    require(re.fullmatch(r"[A-Za-z]:", drive) and tail.startswith(("\\", "/")),
            "expected a drive-absolute Windows path")
    return ntpath.normpath(value).casefold()


def inside(path, root):
    return path == root or path.startswith(root.rstrip("\\") + "\\")


def utc_time(value):
    parsed = datetime.fromisoformat(value.strip())
    require(parsed.utcoffset() == timedelta(0), "expected an explicit UTC timestamp")
    return parsed


def capture_time(value, window_start):
    """Procmon's seven-digit Time of Day column, with Windows set to UTC."""
    require(re.fullmatch(r"\d\d:\d\d:\d\d(?:\.\d{1,7})?", value.strip()),
            "expected Procmon 24-hour Time of Day with the host in UTC")
    return utc_time(f"{window_start.date()}T{value.strip()}+00:00")


@dataclass
class Process:
    guid: str
    parent: str
    pid: int
    image: str
    sha256: str | None
    start: datetime
    command: str
    end: datetime | None = None


@dataclass(frozen=True)
class Connection:
    guid: str
    timestamp: datetime
    protocol: str
    initiated: bool
    source_port: int
    address: ipaddress.IPv4Address | ipaddress.IPv6Address
    port: int


def sysmon_sha256(hashes):
    match = re.search(r"(?:^|,)\s*SHA256=([0-9a-f]{64})(?=,|$)", hashes, re.I)
    return match[1].lower() if match else None


def sysmon_events(path, start, end):
    processes = {}
    connections = []
    issues = set()
    first_record = last_record = None
    events = ET.iterparse(path, events=("start", "end"))
    _, container = next(events)
    for phase, event in events:
        if phase != "end" or event.tag != EVENT_NS + "Event":
            continue
        system = event.find(EVENT_NS + "System")
        stamp = utc_time(system.find(EVENT_NS + "TimeCreated").attrib["SystemTime"])
        record = int(system.findtext(EVENT_NS + "EventRecordID"))
        if last_record is not None:
            require(record > last_record, "Sysmon export must be in ascending record order")
            if record != last_record + 1:
                issues.add("sysmon-record-gap")
        first_record = record if first_record is None else first_record
        last_record = record
        kind = int(system.findtext(EVENT_NS + "EventID"))
        fields = {item.get("Name"): item.text or "" for item in
                  event.findall(f"{EVENT_NS}EventData/{EVENT_NS}Data")}
        if kind in {1, 3, 5}:
            # UtcTime is when the process/network event happened. SystemTime
            # can be later if Windows wrote the event to the channel afterward.
            stamp = utc_time(fields["UtcTime"] + "+00:00")
        if start <= stamp <= end:
            if kind in {4, 16, 255}:
                issues.add("sysmon-restart-config-change-or-error")
            if kind == 1:
                guid = fields["ProcessGuid"].casefold()
                require(guid not in processes, "duplicate process birth")
                processes[guid] = Process(guid, fields["ParentProcessGuid"].casefold(),
                                          int(fields["ProcessId"]), windows_path(fields["Image"]),
                                          sysmon_sha256(fields.get("Hashes", "")), stamp,
                                          fields.get("CommandLine", ""))
            elif kind == 5 and (guid := fields["ProcessGuid"].casefold()) in processes:
                require(processes[guid].end is None, "duplicate process exit")
                processes[guid].end = stamp
            elif kind == 3:
                address = ipaddress.ip_address(fields["DestinationIp"])
                if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                    address = address.ipv4_mapped
                protocol, initiated = fields["Protocol"].lower(), fields["Initiated"].lower()
                port, source_port = (int(fields[key]) for key in ("DestinationPort", "SourcePort"))
                require(protocol in {"tcp", "udp"} and initiated in {"true", "false"}
                        and 0 <= port <= 65535 and 0 <= source_port <= 65535,
                        "invalid Sysmon connection fields")
                connections.append(Connection(fields["ProcessGuid"].casefold(), stamp, protocol,
                                              initiated == "true", source_port, address, port))
        container.remove(event)
    return processes, connections, issues, first_record, last_record


def bind_processes(declared_processes, processes, issues):
    roles = {}
    bindings = []
    for root in declared_processes:
        role = root["role"]
        require(role in ROLES, "unknown declared process role")
        image = windows_path(root["image"])
        matches = [p for p in processes.values() if p.pid == root["pid"] and p.image == image]
        if len(matches) != 1 or matches[0].guid in roles:
            issues.add("process-root-missing-or-ambiguous")
            continue
        process = matches[0]
        roles[process.guid] = role
        bindings.append((root, process))
    # Sysmon process births are read in record order. Resolve by GUID and time,
    # so an unrelated process that reuses a PID never inherits the old role.
    for process in sorted(processes.values(), key=lambda p: p.start):
        if process.guid in roles or process.parent not in roles:
            continue
        parent = processes[process.parent]
        if parent.start > process.start or (parent.end and parent.end < process.start):
            issues.add("inconsistent-parent-lifetime")
            continue
        role = roles[parent.guid]
        if role in {"app", "webview", "webview-network", "helper"}:
            if ntpath.basename(process.image) == "msedgewebview2.exe":
                role = "webview-network" if re.search(
                    r'(?i)(?:^|\s)--utility-sub-type=network\.mojom\.NetworkService(?:\s|$)',
                    process.command,
                ) else "webview"
            else:
                role = "helper"
        roles[process.guid] = role
    if any(processes[guid].end is None for guid in roles):
        issues.add("process-exit-missing")
    return roles, bindings


def verify_app_lifecycles(manifest, processes, markers, roles, bindings, issues):
    for root, app in bindings:
        if root["role"] != "app":
            continue
        if app.sha256 != manifest["executable_sha256"]:
            issues.add("app-sha256-missing-or-mismatched")
        descendants = {app.guid}
        for child in sorted(processes.values(), key=lambda p: p.start):
            if child.parent in descendants:
                descendants.add(child.guid)
        if not {"webview", "webview-network"} <= {roles.get(guid) for guid in descendants}:
            issues.add("webview-or-network-service-lifecycle-missing")
    for root, process in bindings:
        if root["role"] == "backend" and not (
                markers["idle"] <= process.start <= markers["quality"]
                and process.end and markers["exit"] <= process.end):
            issues.add("backend-lifecycle-does-not-cover-journey")


def file_mutation(row):
    op = row["Operation"]
    detail = row["Detail"]
    if row["Result"].strip() != "SUCCESS":
        return None
    if op == "CreateFile":
        if re.search(r"\bOptions: [^,]*Delete On Close", detail, re.I):
            return "delete"
        if re.search(r"\bOpenResult: (Created|Overwritten|Superseded)\b", detail):
            return "create" if "OpenResult: Created" in detail else "overwrite"
        if not re.search(r"\bOpenResult: (Opened|Exists)\b", detail):
            return "ambiguous-create"
    if op.startswith("SetDispositionInformation"):
        if re.search(r"\bDelete: False\b", detail, re.I):
            return None
        return "delete"
    if op.startswith("SetRenameInformation"):
        return "rename"
    if op.startswith("SetLinkInformation"):
        return "link"
    return MUTATIONS.get(op)


def unresolved_path_kind(value):
    if value is None:
        return "destination-field-missing"
    path = value.strip().replace("/", "\\").casefold()
    if not path:
        return "empty"
    if path.startswith(("\\device\\namedpipe\\", "\\\\.\\pipe\\", "\\\\?\\pipe\\")):
        return "named-pipe"
    if path.startswith(("\\\\?\\", "\\\\.\\", "\\??\\", "\\device\\")):
        return "device-or-extended"
    if path.startswith("\\\\"):
        return "unc"
    if path.startswith("\\"):
        return "rooted-without-drive"
    if re.match(r"^[a-z]:", path):
        return "drive-relative"
    return "relative-or-unrecognized"


def inspect_files(path, start, end, processes, roles, protected, permitted, issues):
    lifetimes = {}
    for process in processes.values():
        lifetimes.setdefault(process.pid, []).append(process)
    counts = Counter()
    calibration = set()
    violations = Counter()
    unresolved = Counter()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        require({"Time of Day", "PID", "Operation", "Path", "Result", "Detail",
                 "Process Name"} <= set(rows.fieldnames or ()), "Procmon export columns missing")
        for row in rows:
            require(None not in row and all(value is not None for value in row.values()),
                    "malformed Procmon CSV row")
            operation = file_mutation(row)
            if operation is None:
                continue
            time = capture_time(row["Time of Day"], start)
            if not start <= time <= end:
                continue
            processes_at_time = [
                p for p in lifetimes.get(int(row["PID"]), ())
                if p.start <= time and (p.end is None or time <= p.end)
                and ntpath.basename(p.image) == row["Process Name"].casefold()
            ]
            if len(processes_at_time) > 1:
                issues.add("file-event-process-ambiguous")
            process = processes_at_time[0] if len(processes_at_time) == 1 else None
            role = roles.get(process.guid, "other") if process else "other"
            try:
                targets = [windows_path(row["Path"])]
            except ValueError:
                # Procmon also emits named pipes and device paths. Keep the
                # audit incomplete if an owned event cannot be placed.
                if role != "other" or operation in {"rename", "link"}:
                    issues.add("file-mutation-path-unresolved")
                    unresolved[role, operation, "source", unresolved_path_kind(row["Path"])] += 1
                continue
            if operation in {"rename", "link"}:
                match = re.search(r"(?:^|,\s*)FileName: (.*)$", row["Detail"])
                try:
                    targets.append(windows_path(match[1] if match else ""))
                except ValueError:
                    # Any process could move into a protected root.
                    issues.add("file-mutation-path-unresolved")
                    unresolved[role, operation, "destination",
                               unresolved_path_kind(match[1] if match else None)] += 1
            if any(inside(target, root) for target in targets for root in protected):
                if operation == "ambiguous-create":
                    issues.add("protected-create-result-unresolved")
                else:
                    violations[f"protected:{role}:{operation}"] += 1
            if role == "other":
                continue
            if operation == "ambiguous-create":
                issues.add("scoped-create-result-unresolved")
                continue
            counts[f"{role}:{operation}"] += 1
            if not all(any(inside(target, root) for root in permitted.get(role, ()))
                       for target in targets):
                violations[f"outside-scope:{role}:{operation}"] += 1
            if role == "calibration":
                calibration.add((process.guid, operation, *targets))
    diagnostics = [
        {"role": role, "operation": operation, "field": field, "kind": kind, "count": count}
        for (role, operation, field, kind), count in sorted(unresolved.items())
    ]
    return counts, violations, calibration, diagnostics


def scoped_network(connections, roles, ports):
    counts = Counter()
    external = []
    endpoints = []
    for connection in connections:
        role = roles.get(connection.guid)
        if role is None:
            continue
        if not connection.initiated:
            counts[f"{role}:{connection.protocol}:inbound"] += 1
            continue
        if connection.address.is_loopback:
            verdict = "loopback" if connection.port in ports else "unexpected-loopback"
        else:
            verdict = "non-loopback"
        counts[f"{role}:{connection.protocol}:{verdict}"] += 1
        if verdict == "loopback":
            continue
        summary = {"role": role, "utc": connection.timestamp.isoformat(),
                   "protocol": connection.protocol, "port": connection.port,
                   "kind": verdict, "purpose": "unattributed"}
        external.append(summary)
        endpoints.append({**summary, "address": str(connection.address),
                          "source_port": connection.source_port, "process_guid": connection.guid})
    return counts, external, endpoints


def verify_connection_lifetimes(connections, processes, roles, issues):
    for connection in connections:
        if connection.guid not in roles:
            continue
        process = processes[connection.guid]
        if connection.timestamp < process.start or (
                process.end is not None and connection.timestamp > process.end):
            issues.add("connection-outside-process-lifetime")


def calibration_file_events(root, child_guid):
    marker = windows_path(root["fixture"])
    renamed = windows_path(root["renamed_fixture"])
    require(marker != renamed and ntpath.dirname(marker) == ntpath.dirname(renamed),
            "calibration markers must be distinct siblings")
    return {(child_guid, "create", marker), (child_guid, "write", marker),
            (child_guid, "resize", marker), (child_guid, "rename", marker, renamed),
            (child_guid, "delete", renamed)}


def calibration_window(root, process, processes, connections, file_events, issues):
    children = [p for p in processes.values() if p.parent == process.guid]
    if len(children) != 1:
        issues.add("calibration-child-lifecycle-missing")
        return None
    child = children[0]
    if not process.sha256 or child.sha256 != process.sha256 or child.image != process.image:
        issues.add("calibration-image-identity-missing-or-mismatched")
    if not calibration_file_events(root, child.guid) <= file_events:
        issues.add("calibration-file-events-missing")
    if not (process.end and child.end and process.start <= child.start <= child.end <= process.end):
        issues.add("calibration-child-lifecycle-missing")
        return None
    network = {e.protocol for e in connections if e.guid == child.guid and
               child.start <= e.timestamp <= child.end and e.initiated
               and e.address.is_loopback and e.port == root["port"]}
    if network != {"tcp", "udp"}:
        issues.add("calibration-tcp-or-udp-missing")
    return process.start, process.end


def verify_calibrations(bindings, processes, connections, file_events, markers, issues):
    windows = []
    for root, process in bindings:
        if root["role"] == "calibration":
            window = calibration_window(root, process, processes, connections, file_events, issues)
            if window:
                windows.append(window)
    windows.sort()
    if len(windows) != 2 or not (windows[0][1] < markers["idle"] and markers["exit"] < windows[1][0]):
        issues.add("calibration-does-not-bracket-journey")


def scope(manifest):
    for roots in (manifest["protected_roots"], manifest["observed_roots"]):
        require(all(re.fullmatch(r"[a-z][a-z0-9-]{0,29}", label) for label in roots),
                "use short neutral snapshot labels")
    require(manifest["observed_roots"] and manifest["immutable_observed"] and
            set(manifest["immutable_observed"]) <= set(manifest["observed_roots"]),
            "at least one observed fixture must be immutable")
    protected = [windows_path(value) for value in manifest["protected_roots"].values()]
    observed = [windows_path(value) for value in manifest["observed_roots"].values()]
    require(not any(inside(root, protected_root) or inside(protected_root, root)
                    for root in observed for protected_root in protected), "observed and protected roots overlap")
    permitted = {role: [windows_path(path) for path in paths]
                 for role, paths in manifest["permitted_writes"].items()}
    require(protected and set(permitted) <= (ROLES | {"webview", "webview-network", "helper"}),
            "missing protected roots or unknown write role")
    require(not any(inside(root, protected_root) or inside(protected_root, root)
                    for roots in permitted.values() for root in roots for protected_root in protected),
            "permitted and protected roots overlap")
    return protected, permitted


def verify_snapshots(before, after, manifest, issues):
    changed = []
    fingerprints = {}
    for label, roots in (("protected", manifest["protected_roots"]),
                         ("observed", manifest["observed_roots"])):
        left, right = before[label], after[label]
        require(set(left) == set(right) == set(roots), "snapshot labels differ from the manifest")
        for name in roots:
            root_id = hashlib.sha256(windows_path(roots[name]).encode()).hexdigest()
            for entry in (left[name], right[name]):
                require(entry["root_id"] == root_id and entry["state"] in
                        {"absent", "file", "directory"} and
                        re.fullmatch(r"[0-9a-f]{64}", entry["digest"]), "invalid snapshot entry")
            fingerprints[f"{label}:{name}"] = left[name] != right[name]
            if left[name] != right[name] and (label == "protected" or
                                              name in manifest["immutable_observed"]):
                changed.append(f"{label}:{name}")
            if name in manifest["immutable_observed"] and left[name]["state"] == "absent":
                issues.add("immutable-fixture-missing-at-baseline")
    return fingerprints, changed


def load_capture(manifest, sysmon, *, etw=False):
    require(manifest["schema_version"] == 1 and manifest["disposable"] is True,
            "expected a disposable N12 manifest")
    start, end = (utc_time(manifest[key]) for key in ("start_utc", "end_utc"))
    require(start < end and start.date() == end.date(), "capture must be ordered and inside one UTC day")
    with evidence_stage("Sysmon XML"):
        processes, connections, issues, first, last = sysmon_events(sysmon, start, end)
    if (first, last) != (manifest["sysmon_first_record"], manifest["sysmon_last_record"]) or first is None:
        issues.add("sysmon-bookend-record-mismatch")
    if not etw and (manifest["procmon_all_events"] is not True or
                    manifest["procmon_loss_reviewed"] is not True or
                    manifest["procmon_clock_utc"] is not True):
        issues.add("procmon-coverage-not-confirmed")
    return start, end, processes, connections, issues


def check_calibration(manifest, sysmon, file_trace, *, etw=False):
    """Check real collector exports from a standalone generated fixture."""
    start, end, processes, connections, issues = load_capture(manifest, sysmon, etw=etw)
    root = manifest["calibration"]
    require(root["role"] == "calibration" and type(root["port"]) is int
            and 1 <= root["port"] <= 65535, "invalid calibration fixture")
    roles, bindings = bind_processes([root], processes, issues)
    permitted = {"calibration": [ntpath.dirname(windows_path(root["fixture"]))]}
    if etw:
        protected = [windows_path(path) for path in manifest["protected_roots"].values()]
        require(protected, "missing ETW calibration protected roots")
        counts, violations, file_events, diagnostics = inspect_etw_files(
            manifest, file_trace, start, end, processes, roles, protected, permitted, issues)
        file_report = {"file_evidence_source": "etw", "etw_unresolved_mutations": diagnostics,
                       "file_violations": violations}
    else:
        counts, violations, file_events, path_diagnostics = inspect_files(
            file_trace, start, end, processes, roles, (), permitted, issues)
        file_report = {"unresolved_file_paths": path_diagnostics}
    if bindings:
        calibration_window(root, bindings[0][1], processes, connections, file_events, issues)
    if any(key.startswith("outside-scope:calibration:") for key in violations):
        issues.add("calibration-writes-outside-fixture")
    if any(key.startswith("protected:") for key in violations):
        issues.add("calibration-protected-mutation")
    verify_connection_lifetimes(connections, processes, roles, issues)
    _, unexpected, _ = scoped_network(connections, roles, {root["port"]})
    if unexpected:
        issues.add("calibration-unexpected-connection")
    return {"schema_version": 1, "scope": "collector calibration only",
            "coverage": "BLOCKED" if issues else "CALIBRATED",
            "coverage_issues": sorted(issues), "file_events": counts,
            **file_report,
            "native_n12_accepted": False}


def utc_ticks(timestamp):
    day = timestamp.toordinal() - 1
    seconds = (day * 24 + timestamp.hour) * 3600 + timestamp.minute * 60 + timestamp.second
    return seconds * 10_000_000 + timestamp.microsecond * 10


def etw_capture_contract(manifest, start, end, issues):
    capture = manifest["etw"]
    require(capture["schema_version"] == 1, "unsupported ETW evidence schema")
    capture_start, capture_end = (utc_time(capture[k]) for k in ("start_utc", "end_utc"))
    require(capture_start <= start < end <= capture_end, "ETW capture does not bracket the audit")
    require(re.fullmatch(r"[0-9a-f]{64}", capture["events_sha256"]), "invalid ETW export digest")
    counters = capture["counters"]
    losses = [counters[k] for k in ("events_lost", "log_buffers_lost", "realtime_buffers_lost")]
    require(all(type(n) is int and n >= 0 for n in losses) and
            type(counters["buffers_written"]) is int and counters["buffers_written"] > 0,
            "invalid ETW counters")
    if any(losses):
        issues.add("etw-event-or-buffer-loss")
    devices = {}
    for drive, device in capture["volume_devices"].items():
        drive, device = drive.casefold(), device.casefold()
        require(re.fullmatch(r"[a-z]:", drive) and re.fullmatch(r"\\device\\[^\\]+", device)
                and device not in devices, "invalid or ambiguous ETW volume mapping")
        devices[device] = drive
    require(devices, "ETW volume mappings are missing")

    return (utc_ticks(capture_start), utc_ticks(capture_end)), devices


def etw_events(path, capture_bounds, expected_digest):
    digest = hashlib.sha256()
    has_events = False
    with path.open("rb") as stream:
        for line in stream:
            has_events = True
            digest.update(line)
            event = json.loads(line)
            require(type(event["ticks"]) is int and capture_bounds[0] <= event["ticks"] <= capture_bounds[1],
                    "ETW event timestamp outside capture")
            require(type(event["id"]) is int and (event["pid"] is None or type(event["pid"]) is int)
                    and type(event["lifecycle"]) is bool and isinstance(event["data"], dict),
                    "invalid ETW event envelope")
            yield event
        require(digest.hexdigest() == expected_digest, "ETW export digest mismatch")
        require(has_events, "ETW event export is empty")


def inspect_etw_files(manifest, path, start, end, processes, roles, protected, permitted, issues, *,
                      details=None, process_bookends=None, thread_bookends=None, rundown=None,
                      synthetic_process_roles=None, synthetic_process_births=None,
                      process_bookend_births=None, process_bookend_names=None,
                      process_event_images=None,
                      rundown_recovered_keys=None, rundown_invalidations=None,
                      preopened_control_file_keys=None, preopened_control_file_objects=None):
    if __package__:
        from .n12_etw_correlate import canonical_file_path, correlate_requests
    else:
        from n12_etw_correlate import canonical_file_path, correlate_requests

    with evidence_stage("ETW capture metadata"):
        capture_bounds, devices = etw_capture_contract(manifest, start, end, issues)
    start_ticks, end_ticks = utc_ticks(start), utc_ticks(end)
    lifetimes = {}
    for process in processes.values():
        lifetimes.setdefault(process.pid, []).append(process)
    # Sysmon records millisecond UTC timestamps. Match the same PID and a
    # unique ETW birth within 10 ms, then require the request in its lifetime.
    tolerance = 100_000

    def classify_process(pid, birth, ticks):
        synthetic_birth = (synthetic_process_births or {}).get(pid)
        synthetic_role = (synthetic_process_roles or {}).get(pid)
        if synthetic_role is not None and birth == synthetic_birth:
            return synthetic_role, f"synthetic:{pid}"
        candidates = [process for process in lifetimes.get(pid, ()) if birth is not None and
                      abs(utc_ticks(process.start) - birth) <= tolerance and
                      (process.end is None or ticks <= utc_ticks(process.end) + tolerance)]
        if len(candidates) == 1:
            process = candidates[0]
            role = roles.get(process.guid, "other")
            identity = process.guid if role != "other" else (
                (process_event_images or {}).get((pid, birth)) or
                (process_bookend_names or {}).get(pid) or ntpath.basename(process.image).casefold()
            )
            return role, identity
        # A Sysmon-scoped PID with an absent ETW birth is still a coverage gap.
        if any(process.guid in roles and utc_ticks(process.start) - tolerance <= ticks and
               (process.end is None or ticks <= utc_ticks(process.end) + tolerance)
               for process in lifetimes.get(pid, ())):
            return "unattributed", None
        return "other", (
            (process_event_images or {}).get((pid, birth)) or (process_bookend_names or {}).get(pid)
        )

    initial_process_births = dict(process_bookend_births or {})
    initial_process_births.update(synthetic_process_births or {})
    counts, violations, file_events = Counter(), Counter(), set()

    def record(role, identity, operation, source, destination, requested, completed, success):
        if not success or completed < start_ticks:
            return
        if requested < start_ticks or completed > end_ticks:
            issues.add("etw-completion-outside-audit-window")
        if role == "unattributed":
            issues.add("etw-process-identity-unresolved")
        targets = tuple(path for path in (source, destination) if path)
        protected_targets = [target for target in targets
                             if any(inside(target, root) for root in protected)]
        if protected_targets:
            violations[f"protected:{role}:{operation}"] += 1
            if details is not None and role in {"other", "unattributed"}:
                label = identity if role == "other" and identity else "scoped-unattributed"
                details[f"protected-writer:{label}:{operation}"] += 1
                for target in protected_targets:
                    basename = ntpath.basename(target).casefold() or "unknown"
                    details[f"protected-writer-target:{label}:{operation}:{basename}"] += 1
        if role in {"other", "unattributed"}:
            return
        counts[f"{role}:{operation}"] += 1
        if not all(any(inside(target, root) for root in permitted.get(role, ()))
                   for target in targets):
            violations[f"outside-scope:{role}:{operation}"] += 1
        if role == "calibration" and start_ticks <= requested <= completed <= end_ticks:
            file_events.add((identity, operation, *targets))

    with evidence_stage("ETW event stream"):
        event_records = list(etw_events(path, capture_bounds, manifest["etw"]["events_sha256"]))
        # Keep post-audit ETW events for rundown lifetime checks. A rename, close,
        # or key reuse after the Sysmon audit boundary still invalidates a stop-time
        # name for an earlier write.
        guard_events = [event for event in event_records if event["ticks"] >= start_ticks]
        unresolved = correlate_requests(
            (event for event in event_records if event["ticks"] <= end_ticks),
            lambda value: canonical_file_path(value, devices),
            classify_process, lambda value: value is not None and
            any(inside(value, root) for root in protected), record, strict=True,
            details=details, process_bookends=process_bookends, thread_bookends=thread_bookends,
            rundown=rundown, rundown_guard_events=guard_events,
            rundown_recovered_keys=rundown_recovered_keys,
            rundown_invalidations=rundown_invalidations,
            initial_process_births=initial_process_births,
            preopened_control_file_keys=preopened_control_file_keys,
            preopened_control_file_objects=preopened_control_file_objects,
        )
    if unresolved:
        issues.add("etw-mutation-coverage-unresolved")
    return counts, violations, file_events, dict(unresolved)


def audit(manifest, sysmon, procmon, before, after, *, private_endpoints=None, etw=False,
          rundown=None):
    require(rundown is None or etw, "FileIO rundown requires ETW audit")
    start, end, processes, connections, issues = load_capture(manifest, sysmon, etw=etw)
    require(re.fullmatch(r"[0-9a-f]{40}", manifest["source_sha"]) and
            re.fullmatch(r"[0-9a-f]{64}", manifest["executable_sha256"]),
            "source and executable identities are required")
    markers = {key: utc_time(manifest["markers"][key]) for key in MINIMUM_MARKERS}
    moments = [start, *markers.values(), end]
    require(all(a < b for a, b in zip(moments, moments[1:])), "missing or unordered journey markers")
    protected, permitted = scope(manifest)
    declared = Counter(root["role"] for root in manifest["processes"])
    require(declared["app"] == 2 and declared["backend"] == 1 and declared["calibration"] == 2
            and declared["driver"] >= 1, "expected two app launches, one backend, two calibrations and a driver")
    roles, bindings = bind_processes(manifest["processes"], processes, issues)
    verify_app_lifecycles(manifest, processes, markers, roles, bindings, issues)
    apps = sorted((p for _, p in bindings if roles[p.guid] == "app"), key=lambda p: p.start)
    if len(apps) != 2 or not (markers["launch"] <= apps[0].start < markers["quality"] and
                             apps[0].end and markers["close"] <= apps[0].end < markers["reopen"] and
                             markers["reopen"] <= apps[1].start < markers["exit"] and
                             apps[1].end and markers["exit"] <= apps[1].end):
        issues.add("app-lifecycle-does-not-match-journey")
    etw_diagnostics = {}
    if etw:
        immutable = [windows_path(manifest["observed_roots"][label])
                     for label in manifest["immutable_observed"]]
        file_counts, violations, file_events, etw_diagnostics = inspect_etw_files(
            manifest, procmon, start, end, processes, roles, protected + immutable, permitted, issues,
            rundown=rundown)
        path_diagnostics = []
    else:
        file_counts, violations, file_events, path_diagnostics = inspect_files(
            procmon, start, end, processes, roles, protected, permitted, issues)
    verify_calibrations(bindings, processes, connections, file_events, markers, issues)
    ports = manifest["loopback_ports"]
    require(ports and all(type(port) is int and 1 <= port <= 65535 for port in ports),
            "invalid loopback port allowlist")
    require(all(p["port"] in ports for p, _ in bindings if p["role"] == "calibration"),
            "calibration ports must be recorded in the loopback allowlist")
    verify_connection_lifetimes(connections, processes, roles, issues)
    net_counts, external, endpoints = scoped_network(connections, roles, set(ports))
    if private_endpoints is not None:
        private_endpoints.extend(endpoints)
    snapshots, changed = verify_snapshots(before, after, manifest, issues)
    network = "PASS_SCOPED"
    if any(e["kind"] == "non-loopback" for e in external):
        network = "PARTIAL"
    if any(e["kind"] == "unexpected-loopback" for e in external):
        network = "FAIL"
    filesystem = "FAIL" if violations or changed else "PASS_SCOPED"
    if issues:
        if network == "PASS_SCOPED":
            network = "BLOCKED"
        if filesystem == "PASS_SCOPED":
            filesystem = "BLOCKED"
    return {
        "schema_version": 1, "source_sha": manifest["source_sha"],
        "executable_sha256": manifest["executable_sha256"],
        "coverage": "BLOCKED" if issues else "CALIBRATED",
        "coverage_issues": sorted(issues), "process_roles": dict(Counter(roles.values())),
        "network": network, "connections": net_counts, "unexpected_connections": external,
        "network_scope": "Sysmon-observed TCP/UDP connections, excluding blocked attempts",
        "native_n12_accepted": False,
        "filesystem": filesystem, "file_events": file_counts, "file_violations": violations,
        "unresolved_file_paths": path_diagnostics,
        **({"file_evidence_source": "etw", "etw_unresolved_mutations": etw_diagnostics,
             **({"file_key_rundown_records": len(rundown)} if rundown is not None else {})}
           if etw else {}),
        "snapshot_changes": snapshots, "unexpected_snapshot_changes": changed,
        "historical_port_443_disposition": "UNATTRIBUTED",
    }


def local_disposable_path(path, *, runner_temp_only=False):
    # Snapshot and calibration must both use a disposable hosted Windows root.
    require(os.name == "nt" and os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            os.environ.get("RUNNER_OS") == "Windows", "snapshot requires disposable hosted Windows")
    candidate = Path(path).absolute()
    allowed = (Path(os.environ["RUNNER_TEMP"]).absolute(), *(
        Path(os.environ[name]).absolute() for name in ("LOCALAPPDATA", "APPDATA")))
    protected_ids = {"com.pilotodin.studio", "com.pilotodin.p4nativeqa", "com.pilotodin.p4isolatednativedev"}
    require(".." not in candidate.parts and (allowed[0] in candidate.parents or (not runner_temp_only and any(
        base in candidate.parents and candidate.relative_to(base).parts[0].casefold() in protected_ids
        for base in allowed[1:]))), "path is outside reviewed hosted roots")
    for item in (candidate, *candidate.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        require(not (info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                "snapshot path traverses a reparse point")
    return candidate


def fingerprint(path):
    root_id = hashlib.sha256(windows_path(str(path)).encode()).hexdigest()
    digest = hashlib.sha256()
    try:
        root = path.lstat()
    except FileNotFoundError:
        return {"root_id": root_id, "state": "absent", "digest": digest.hexdigest()}
    state = "directory" if stat.S_ISDIR(root.st_mode) else "file"
    entries = [path]
    while entries:
        entry = entries.pop()
        info = entry.lstat()
        require(not (stat.S_ISLNK(info.st_mode) or
                    getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                "snapshot contains a reparse point")
        name = entry.relative_to(path).as_posix()
        if stat.S_ISDIR(info.st_mode):
            digest.update(json.dumps(["directory", name]).encode() + b"\n")
            entries.extend(sorted(entry.iterdir(), reverse=True))
        else:
            require(stat.S_ISREG(info.st_mode), "snapshot contains an unsupported file type")
            with entry.open("rb") as stream:
                file_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            digest.update(json.dumps(["file", name, file_hash]).encode() + b"\n")
    return {"root_id": root_id, "state": state, "digest": digest.hexdigest()}


def read_json(path):
    with evidence_stage("JSON input"):
        return json.loads(path.read_text(encoding="utf-8-sig"))


def read_rundown_file(path, manifest):
    """Read native ProcessTrace FileIO names with a manifest-pinned digest."""
    with evidence_stage("FileIO rundown input"):
        etw = manifest.get("etw")
        require(isinstance(etw, dict), "ETW capture metadata is required for FileIO rundown")
        expected = etw.get("rundown_sha256")
        require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
                "FileIO rundown SHA-256 is required in the ETW manifest")
        timestamps = (etw.get("start_utc"), etw.get("rundown_stop_utc"), etw.get("end_utc"))
        require(all(isinstance(value, str) for value in timestamps),
                "ETW start, rundown stop and end timestamps are required")
        capture_start, rundown_stop, capture_end = (utc_time(value) for value in timestamps)
        require(capture_start <= rundown_stop <= capture_end,
                "FileIO rundown stop must be within the ETW capture window")
        digest = hashlib.sha256()
        entries = []
        with path.open("rb") as stream:
            for raw_line in stream:
                digest.update(raw_line)
                require(bool(raw_line.strip()), "FileIO rundown contains an empty record")
                entry = json.loads(raw_line)
                require(isinstance(entry, dict), "invalid FileIO rundown record")
                raw_key = entry.get("key")
                if isinstance(raw_key, str):
                    try:
                        key = int(raw_key, 16 if raw_key.lower().startswith("0x") else 10)
                    except ValueError:
                        key = None
                else:
                    key = raw_key
                require(type(key) is int and key > 0, "invalid FileIO rundown key")
                value = entry.get("path")
                require(isinstance(value, str) and 0 < len(value) <= 32768
                        and not any(ord(char) < 0x20 for char in value),
                        "invalid FileIO rundown path")
                require(entry.get("decoder") in {"tdh+raw-schema", "tdh", "raw-schema-v2"},
                        "FileIO rundown requires a recognised native decoder")
                entries.append({"key": key, "path": value})
        require(digest.hexdigest() == expected, "FileIO rundown SHA-256 mismatch")
        require(entries, "FileIO rundown is empty")
        return entries


def check_etw_export(manifest, path):
    issues = set()
    with evidence_stage("ETW capture metadata"):
        start, end = (utc_time(manifest[key]) for key in ("start_utc", "end_utc"))
        capture_bounds, _ = etw_capture_contract(manifest, start, end, issues)
    with evidence_stage("ETW event stream"):
        count = sum(1 for _ in etw_events(path, capture_bounds, manifest["etw"]["events_sha256"]))
    require(not issues, "ETW reported event or buffer loss")
    return count


def stable_process_bookend_records(bookends, capture_start, lifecycle_pids):
    snapshots = []
    for side in ("before", "after"):
        entries = {}
        for entry in bookends[side]:
            pid, birth = entry["pid"], entry["birth_ticks"]
            name = entry.get("name")
            require(type(pid) is int and type(birth) is int and pid >= 0 and birth > 0
                    and pid not in entries and (name is None or isinstance(name, str)),
                    "invalid or duplicate process bookend identity")
            image = ntpath.basename(name.strip()).casefold() if name else None
            entries[pid] = (birth, image or None)
        snapshots.append(entries)
    before, after = snapshots
    return {
        pid: {"birth_ticks": birth, "name": name}
        for pid, (birth, name) in before.items()
        if birth < capture_start and after.get(pid) == (birth, name) and pid not in lifecycle_pids
    }


def stable_process_bookends(bookends, capture_start, lifecycle_pids):
    return set(stable_process_bookend_records(bookends, capture_start, lifecycle_pids))


def stable_thread_bookends(bookends, capture_start, stable_pids, lifecycle_tids):
    snapshots = []
    for side in ("threads_before", "threads_after"):
        entries = {}
        duplicates = set()
        for entry in bookends.get(side, ()):
            tid, pid, birth = entry["tid"], entry["pid"], entry["birth_ticks"]
            require(all(type(value) is int for value in (tid, pid, birth))
                    and tid > 0 and pid >= 0 and birth > 0,
                    "invalid thread bookend identity")
            if tid in entries:
                duplicates.add(tid)
            entries[tid] = (pid, birth)
        snapshots.append({tid: identity for tid, identity in entries.items() if tid not in duplicates})
    before, after = snapshots
    return {tid: pid for tid, (pid, birth) in before.items() if pid in stable_pids
            and birth < capture_start and after.get(tid) == (pid, birth) and tid not in lifecycle_tids}


def check_etw_preflight(manifest, fixture, path, *, bookends=None, rundown=None):
    """Exercise strict ETW correlation using fixture PIDs and ETW lifetimes."""
    if __package__:
        from .n12_etw_correlate import number
    else:
        from n12_etw_correlate import number

    issues = set()
    with evidence_stage("ETW capture metadata"):
        start, end = (utc_time(manifest[key]) for key in ("start_utc", "end_utc"))
        bounds, _ = etw_capture_contract(manifest, start, end, issues)
    root = manifest["calibration"]
    parent_pid, child_pid = root["pid"], fixture["child_pid"]
    require(type(parent_pid) is int and type(child_pid) is int and
            parent_pid > 0 and child_pid > 0 and parent_pid != child_pid
            and child_pid == root["child_pid"], "invalid calibration fixture PIDs")
    first, last = fixture["start_window"]
    require(bounds[0] <= first < last <= bounds[1], "fixture lifetime window outside ETW capture")
    lifecycles = {(pid, kind): [] for pid in (parent_pid, child_pid) for kind in (1, 2)}
    lifecycle_pids = set()
    lifecycle_tids = set()
    with evidence_stage("ETW fixture lifetimes"):
        for event in etw_events(path, bounds, manifest["etw"]["events_sha256"]):
            if event["lifecycle"] and event["id"] in (1, 2):
                pid = number(event["data"]["ProcessID"])
                lifecycle_pids.add(pid)
                key = (pid, event["id"])
                if key in lifecycles and first <= event["ticks"] <= last:
                    lifecycles[key].append(event["ticks"])
            elif event["lifecycle"] and event["id"] in (3, 4):
                lifecycle_tids.add(number(event["data"]["ThreadID"]))
    require(all(len(stamps) == 1 for stamps in lifecycles.values()),
            "fixture ETW lifetimes missing or ambiguous")
    parent_start, parent_stop, child_start, child_stop = (
        stamps[0] for stamps in lifecycles.values()
    )
    require(parent_start <= child_start < child_stop <= parent_stop,
            "fixture ETW lifetimes are inconsistent")

    image = windows_path(root["image"])
    anchor = utc_time(manifest["etw"]["start_utc"])
    processes = {}
    for guid, parent, pid, birth, stop in (
        ("parent", "", parent_pid, parent_start, parent_stop),
        ("child", "parent", child_pid, child_start, child_stop),
    ):
        processes[guid] = Process(guid, parent, pid, image, None,
                                  anchor + timedelta(microseconds=(birth - bounds[0]) // 10),
                                  "", anchor + timedelta(microseconds=(stop - bounds[0]) // 10))
    details = Counter()
    roles = dict.fromkeys(processes, "calibration")
    protected = [windows_path(path) for path in manifest["protected_roots"].values()]
    require(protected, "missing ETW calibration protected roots")
    permitted = {"calibration": [ntpath.dirname(windows_path(root["fixture"]))]}
    bookend_pids = None if bookends is None else stable_process_bookends(bookends, bounds[0], lifecycle_pids)
    bookend_threads = None if bookends is None else stable_thread_bookends(
        bookends, bounds[0], bookend_pids, lifecycle_tids)
    counts, violations, file_events, unresolved = inspect_etw_files(
        manifest, path, start, end, processes, roles, protected, permitted, issues,
        details=details, process_bookends=bookend_pids, thread_bookends=bookend_threads,
        rundown=rundown)
    matched = calibration_file_events(root, "child") <= file_events
    return {"scope": "strict ETW diagnostic preflight with generated process evidence",
            "etw_coverage": "BLOCKED" if issues or violations or not matched else "CLEAN",
            "coverage_issues": sorted(issues), "expected_fixture_operations_matched": matched,
            "file_events": counts, "file_violations": violations,
            "etw_unresolved_mutations": unresolved, "etw_unresolved_event_types": details,
            "native_n12_accepted": False,
            **({"file_key_rundown_records": len(rundown)} if rundown is not None else {})}



def check_etw_preopened_rundown(manifest, capture, path, rundown, bookends=None):
    """Exercise strict reducer classification against the generated pre-opened controls."""
    if __package__:
        from .n12_etw_correlate import number, preopened_report
    else:
        from n12_etw_correlate import number, preopened_report

    require(isinstance(capture, dict), "invalid pre-opened control capture")
    control = capture.get("preopened")
    require(isinstance(control, dict), "pre-opened control metadata is missing")
    pid, tid = control.get("pid"), control.get("tid")
    require(type(pid) is int and pid > 0 and type(tid) is int and tid > 0,
            "invalid pre-opened control process or thread identity")
    writes = control.get("writes")
    require(isinstance(writes, dict) and {"protected", "outside"} <= set(writes),
            "both pre-opened control writes are required")
    require(isinstance(capture.get("device"), str) and capture["device"],
            "pre-opened control volume identity is missing")
    require(isinstance(capture.get("protected_root"), str),
            "pre-opened control protected root is missing")
    protected_root = windows_path(capture["protected_root"])
    protected_values = manifest.get("protected_roots")
    require(isinstance(protected_values, dict) and protected_values,
            "strict reducer protected roots are missing")
    protected = [windows_path(value) for value in protected_values.values()]
    require(protected_root in protected,
            "pre-opened control root does not match the reducer manifest")
    require(all(isinstance(writes[label], dict) and isinstance(writes[label].get("path"), str)
                for label in ("protected", "outside")),
            "pre-opened control target paths are missing")
    protected_path = windows_path(writes["protected"]["path"])
    outside_path = windows_path(writes["outside"]["path"])
    require(inside(protected_path, protected_root) and not inside(outside_path, protected_root),
            "pre-opened control targets do not distinguish protected and outside paths")

    start, end = (utc_time(manifest[key]) for key in ("start_utc", "end_utc"))
    require(start < end, "ETW audit window is invalid")
    issues = set()
    with evidence_stage("ETW capture metadata"):
        bounds, _ = etw_capture_contract(manifest, start, end, issues)
    with evidence_stage("ETW event stream"):
        event_records = list(etw_events(path, bounds, manifest["etw"]["events_sha256"]))
    lifecycle_pids, lifecycle_tids = set(), set()
    for event in event_records:
        if not event["lifecycle"]:
            continue
        data = event["data"]
        if event["id"] in (1, 2):
            process_id = number(data.get("ProcessID", data.get("ProcessId")))
            lifecycle_pids.add(process_id)
            if process_id == pid:
                raise EvidenceValidationError("pre-opened control process has an in-capture lifecycle transition")
        if event["id"] in (3, 4):
            thread_id = number(data.get("ThreadID", data.get("TThreadId")))
            lifecycle_tids.add(thread_id)
            if thread_id == tid:
                raise EvidenceValidationError("pre-opened control thread has an in-capture lifecycle transition")

    stable_processes = (stable_process_bookend_records(bookends, bounds[0], lifecycle_pids)
                        if bookends is not None else {})
    stable_process_pids = set(stable_processes) if bookends is not None else None
    stable_threads = (stable_thread_bookends(bookends, bounds[0], stable_process_pids, lifecycle_tids)
                      if bookends is not None else None)
    bookend_births = {process_id: item["birth_ticks"]
                      for process_id, item in stable_processes.items() if process_id != pid}
    bookend_names = {process_id: item["name"]
                     for process_id, item in stable_processes.items()
                     if process_id != pid and item["name"]}
    process_event_images = {}
    for event in event_records:
        if not event["lifecycle"] or event["id"] != 1:
            continue
        data = event["data"]
        process_id = number(data.get("ProcessID", data.get("ProcessId")))
        image = data.get("ImageFileName") or data.get("ImageName")
        if type(process_id) is int and process_id >= 0 and isinstance(image, str) and image.strip():
            basename = ntpath.basename(image.strip()).casefold()
            if basename:
                process_event_images[(process_id, event["ticks"])] = basename

    control_keys = {}
    control_file_objects = {}
    target_report = preopened_report(
        capture, event_records, rundown, file_keys=control_keys, file_objects=control_file_objects
    )
    for label in ("protected", "outside"):
        target = target_report["targets"].get(label, {})
        require(target.get("request_candidates") == 1 and target.get("completion") == "success"
                and target.get("issuing_thread") == "matches"
                and target.get("rundown_name") == "matches-target",
                f"pre-opened {label} control lacks exact request, completion, thread or rundown evidence")
    require(set(control_keys) == {"protected", "outside"} and
            len(set(control_keys.values())) == 2,
            "pre-opened control file keys are missing or ambiguous")
    require(set(control_file_objects) == {"protected", "outside"} and
            all(type(value) is int and value > 0 for value in control_file_objects.values()),
            "pre-opened control FileObjects are missing or invalid")

    synthetic_birth = utc_ticks(start) - 1
    recovered_keys = set()
    invalidations = {}
    details = Counter()
    permitted = {"preopened-control": [ntpath.dirname(protected_root)]}
    counts, violations, _, unresolved = inspect_etw_files(
        manifest, path, start, end, {}, {}, protected, permitted, issues,
        details=details,
        rundown=rundown,
        synthetic_process_roles={pid: "preopened-control"},
        synthetic_process_births={pid: synthetic_birth},
        process_bookends=stable_process_pids,
        thread_bookends=stable_threads,
        process_bookend_births=bookend_births,
        process_bookend_names=bookend_names,
        process_event_images=process_event_images,
        rundown_recovered_keys=recovered_keys,
        rundown_invalidations=invalidations,
        preopened_control_file_keys={control_keys["protected"]},
        preopened_control_file_objects={control_file_objects["protected"]},
    )
    recovered_control_keys = {label for label, key in control_keys.items() if key in recovered_keys}
    unresolved_controls = {key: value for key, value in unresolved.items()
                           if key.startswith("preopened-control:")}
    unrelated_unresolved = {key: value for key, value in unresolved.items()
                            if not key.startswith("preopened-control:")}
    unrelated_unresolved_event_types = {
        key: value for key, value in details.items()
        if not key.startswith("preopened-control:") and
        not key.startswith("compression-request:") and
        not key.startswith("write-path-gap:") and
        not key.startswith("write-name-invalidation:") and
        not key.startswith("write-gap-open-evidence:") and
        not key.startswith("write-gap-name-change-event:") and
        not key.endswith(":rundown-path-recovered")
    }
    expected_control_violations = {"protected:preopened-control:write": 1}
    control_violations = {
        key: value for key, value in violations.items()
        if key.startswith("protected:preopened-control:") or
        key.startswith("outside-scope:preopened-control:")
    }
    unrelated_file_violations = {
        key: value for key, value in violations.items()
        if key not in expected_control_violations
    }
    non_mutation_issues = set(issues) - {"etw-mutation-coverage-unresolved"}
    control_failures = []
    if recovered_control_keys != {"protected", "outside"}:
        control_failures.append("strict-rundown-key-not-recovered")
    if unresolved_controls:
        control_failures.append("preopened-control-unresolved")
    if control_violations != expected_control_violations:
        control_failures.append("protected-outside-control-classification-mismatch")
    if counts.get("preopened-control:write") != 2:
        control_failures.append("preopened-write-count-mismatch")
    if non_mutation_issues:
        control_failures.append("etw-capture-loss-or-invalid-metadata")
    control_invalidations = {
        label: dict(invalidations.get(key, {}))
        for label, key in control_keys.items()
    }
    strict_coverage = "BLOCKED" if issues or violations or unresolved else "UNEXPECTEDLY_CLEAN"

    return {
        "scope": "strict ETW reducer integration with generated pre-opened handles",
        "control_status": "PASS" if not control_failures else "FAIL",
        "control_failures": control_failures,
        "strict_coverage": strict_coverage,
        "coverage_issues": sorted(issues),
        "file_events": dict(counts),
        "file_violations": dict(violations),
        "unrelated_file_violations": unrelated_file_violations,
        "unresolved_controls": unresolved_controls,
        "unrelated_unresolved_mutations": unrelated_unresolved,
        "unrelated_unresolved_event_types": unrelated_unresolved_event_types,
        "compression_request_outcomes": {
            key.removeprefix("compression-request:"): value for key, value in details.items()
            if key.startswith("compression-request:")
        },
        "successful_write_path_gaps": {
            key.removeprefix("write-path-gap:"): value for key, value in details.items()
            if key.startswith("write-path-gap:")
        },
        "successful_write_name_invalidations": {
            key.removeprefix("write-name-invalidation:"): value for key, value in details.items()
            if key.startswith("write-name-invalidation:")
        },
        "unresolved_write_open_evidence": {
            key.removeprefix("write-gap-open-evidence:"): value for key, value in details.items()
            if key.startswith("write-gap-open-evidence:")
        },
        "unresolved_write_name_change_events": {
            key.removeprefix("write-gap-name-change-event:"): value for key, value in details.items()
            if key.startswith("write-gap-name-change-event:")
        },
        "protected_writer_processes": {
            key: value for key, value in details.items()
            if key.startswith("protected-writer:") and not key.startswith("protected-writer-target:")
        },
        "protected_writer_targets": {
            key: value for key, value in details.items() if key.startswith("protected-writer-target:")
        },
        "protected_writer_control_correlations": {
            key: value for key, value in details.items() if ":preopened-control-file" in key
        },
        "other_process_image_events": {
            key: value for key, value in details.items()
            if key.startswith("other:") and ":process-image-" in key
        },
        "issuing_thread_owner_images": {
            key: value for key, value in details.items() if ":issuing-thread-owner-" in key
        },
        "rundown_invalidation_events": {
            key: value for key, value in details.items() if ":rundown-invalidated-by-" in key
        },
        "rundown_name_candidate_events": {
            key: value for key, value in details.items() if ":name-candidate" in key
        },
        "name_event_path_forms": {
            key: value for key, value in details.items()
            if key.startswith("n12:name-event-10:path-form-")
        },
        "unmapped_name_event_devices": {
            key: value for key, value in details.items()
            if key.startswith("n12:name-event-10:unmapped-device-")
        },
        "volume_device_mapping_drives": sorted(manifest["etw"]["volume_devices"].keys()),
        "stable_process_bookends": len(stable_process_pids or ()),
        "stable_thread_bookends": len(stable_threads or {}),
        "rundown_control_keys_recovered": len(recovered_control_keys),
        "rundown_control_key_invalidations": control_invalidations,
        "protected_control_classification": (
            "PROTECTED_WRITE_DETECTED"
            if violations.get("protected:preopened-control:write") == 1
            else "NOT_CONFIRMED"
        ),
        "outside_control_classification": (
            "OUTSIDE_PROTECTED_ROOTS"
            if "outside" in recovered_control_keys and
            violations.get("protected:preopened-control:write") == 1
            else "NOT_CONFIRMED"
        ),
        "targets": target_report["targets"],
        "native_n12_accepted": False,
    }

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    subcommands = cli.add_subparsers(dest="mode", required=True)
    snapshot = subcommands.add_parser("snapshot")
    snapshot.add_argument("manifest", type=Path)
    snapshot.add_argument("output", type=Path)
    etw_export = subcommands.add_parser("check-etw-export")
    etw_export.add_argument("manifest", type=Path)
    etw_export.add_argument("etw_events", type=Path)
    etw_preflight = subcommands.add_parser("check-etw-preflight")
    for argument in ("manifest", "fixture", "etw_events"):
        etw_preflight.add_argument(argument, type=Path)
    etw_preflight.add_argument("--process-bookends", type=Path)
    etw_preflight.add_argument("--rundown", type=Path,
                               help="Native FileIO rundown JSONL, SHA-256 pinned in the ETW manifest.")
    preopened_rundown = subcommands.add_parser("check-etw-preopened-rundown")
    for argument in ("manifest", "capture", "etw_events"):
        preopened_rundown.add_argument(argument, type=Path)
    preopened_rundown.add_argument("--rundown", type=Path, required=True,
                                   help="Native FileIO rundown JSONL, SHA-256 pinned in the ETW manifest.")
    preopened_rundown.add_argument("--process-bookends", type=Path,
                                   help="Redacted process/thread identity snapshots from the disposable runner.")
    for mode in ("check-calibration", "check-calibration-etw"):
        calibration = subcommands.add_parser(mode)
        for argument in ("manifest", "sysmon", "file_trace", "output"):
            calibration.add_argument(argument, type=Path)
    for mode in ("audit", "audit-etw"):
        report = subcommands.add_parser(mode)
        for argument in ("manifest", "sysmon", "etw_events" if mode == "audit-etw" else "procmon",
                         "before", "after", "output"):
            report.add_argument(argument, type=Path)
        report.add_argument("--private-endpoints", type=Path,
                            help="Optional raw endpoint report, confined to disposable Windows runner temp.")
        if mode == "audit-etw":
            report.add_argument("--rundown", type=Path,
                                help="Native FileIO rundown JSONL, SHA-256 pinned in the ETW manifest.")
    args = cli.parse_args()
    try:
        if args.mode == "check-etw-export":
            count = check_etw_export(read_json(args.manifest), args.etw_events)
            print(f"N12 ETW export passed validation: {count} events.")
            return 0
        if args.mode == "check-etw-preflight":
            manifest = read_json(args.manifest)
            bookends = read_json(args.process_bookends) if args.process_bookends else None
            rundown = read_rundown_file(args.rundown, manifest) if args.rundown else None
            result = check_etw_preflight(manifest, read_json(args.fixture)["fixture"],
                                         args.etw_events, bookends=bookends, rundown=rundown)
            print(json.dumps(result, indent=2, sort_keys=True))
            expected_issues = {"etw-mutation-coverage-unresolved"}
            ready = result["expected_fixture_operations_matched"] and not result["file_violations"]
            return 0 if ready and set(result["coverage_issues"]) <= expected_issues else 2
        if args.mode == "check-etw-preopened-rundown":
            manifest = read_json(args.manifest)
            capture = read_json(args.capture)
            rundown = read_rundown_file(args.rundown, manifest)
            bookends = read_json(args.process_bookends) if args.process_bookends else None
            result = check_etw_preopened_rundown(manifest, capture, args.etw_events, rundown,
                                                 bookends=bookends)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["control_status"] == "PASS" else 2
        if args.mode == "snapshot":
            manifest = read_json(local_disposable_path(args.manifest, runner_temp_only=True))
            require(manifest["disposable"] is True, "snapshot requires a disposable manifest")
            output = local_disposable_path(args.output, runner_temp_only=True)
            scope(manifest)
            result = {label: {name: fingerprint(local_disposable_path(path))
                              for name, path in manifest[key].items()}
                      for label, key in (("protected", "protected_roots"), ("observed", "observed_roots"))}
        elif args.mode in {"check-calibration", "check-calibration-etw"}:
            output = args.output
            result = check_calibration(read_json(args.manifest), args.sysmon, args.file_trace,
                                       etw=args.mode == "check-calibration-etw")
        else:
            output = args.output
            endpoints = [] if args.private_endpoints else None
            private = None
            if endpoints is not None:
                private = local_disposable_path(args.private_endpoints, runner_temp_only=True)
                require(private != output.absolute(), "public and private report paths must differ")
            etw = args.mode == "audit-etw"
            manifest = read_json(args.manifest)
            rundown_path = getattr(args, "rundown", None)
            rundown = read_rundown_file(rundown_path, manifest) if rundown_path else None
            result = audit(manifest, args.sysmon, args.etw_events if etw else args.procmon,
                           read_json(args.before), read_json(args.after), private_endpoints=endpoints,
                           etw=etw, rundown=rundown)
            if private:
                with private.open("x", encoding="utf-8") as stream:
                    json.dump(endpoints, stream, indent=2)
                    stream.write("\n")
        with evidence_stage("summary output"), output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except EvidenceValidationError as exc:
        print(f"N12 BLOCKED: {exc}.", file=sys.stderr)
        return 2
    except EVIDENCE_ERRORS as exc:
        print(f"N12 BLOCKED: missing, invalid or inaccessible evidence ({type(exc).__name__}).",
              file=sys.stderr)
        return 2
    if args.mode == "snapshot":
        return 0
    if args.mode in {"check-calibration", "check-calibration-etw"}:
        print(f"N12 collector calibration: {result['coverage']}")
        return 0 if result["coverage"] == "CALIBRATED" else 2
    print(f"N12 coverage={result['coverage']} network={result['network']} filesystem={result['filesystem']}")
    if result["coverage"] == "BLOCKED":
        return 2
    return 0 if result["network"] == result["filesystem"] == "PASS_SCOPED" else 1


if __name__ == "__main__":
    sys.exit(main())
