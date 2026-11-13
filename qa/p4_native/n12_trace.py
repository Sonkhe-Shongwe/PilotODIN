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


def require(condition, message):
    if not condition:
        raise ValueError(message)


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


def calibration_window(root, process, processes, connections, file_events, issues):
    children = [p for p in processes.values() if p.parent == process.guid]
    if len(children) != 1:
        issues.add("calibration-child-lifecycle-missing")
        return None
    child = children[0]
    if not process.sha256 or child.sha256 != process.sha256 or child.image != process.image:
        issues.add("calibration-image-identity-missing-or-mismatched")
    marker = windows_path(root["fixture"])
    renamed = windows_path(root["renamed_fixture"])
    require(marker != renamed and ntpath.dirname(marker) == ntpath.dirname(renamed),
            "calibration markers must be distinct siblings")
    expected = {(child.guid, "create", marker), (child.guid, "write", marker),
                (child.guid, "resize", marker), (child.guid, "rename", marker, renamed),
                (child.guid, "delete", renamed)}
    if not expected <= file_events:
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


def inspect_etw_files(manifest, path, start, end, processes, roles, protected, permitted, issues):
    if __package__:
        from .n12_etw_correlate import canonical_file_path, correlate_requests
    else:
        from n12_etw_correlate import canonical_file_path, correlate_requests

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

    start_ticks, end_ticks = utc_ticks(start), utc_ticks(end)
    capture_bounds = utc_ticks(capture_start), utc_ticks(capture_end)
    lifetimes = {}
    for process in processes.values():
        lifetimes.setdefault(process.pid, []).append(process)
    # Sysmon records millisecond UTC timestamps. Match the same PID and a
    # unique ETW birth within 10 ms, then require the request in its lifetime.
    tolerance = 100_000

    def classify_process(pid, birth, ticks):
        candidates = [process for process in lifetimes.get(pid, ()) if birth is not None and
                      abs(utc_ticks(process.start) - birth) <= tolerance and
                      (process.end is None or ticks <= utc_ticks(process.end) + tolerance)]
        if len(candidates) == 1:
            process = candidates[0]
            return roles.get(process.guid, "other"), process.guid
        # A Sysmon-scoped PID with an absent ETW birth is still a coverage gap.
        if any(process.guid in roles and utc_ticks(process.start) - tolerance <= ticks and
               (process.end is None or ticks <= utc_ticks(process.end) + tolerance)
               for process in lifetimes.get(pid, ())):
            return "unattributed", None
        return "other", None

    counts, violations, file_events = Counter(), Counter(), set()

    def record(role, identity, operation, source, destination, requested, completed, success):
        if not success or completed < start_ticks:
            return
        if requested < start_ticks or completed > end_ticks:
            issues.add("etw-completion-outside-audit-window")
        if role == "unattributed":
            issues.add("etw-process-identity-unresolved")
        targets = tuple(path for path in (source, destination) if path)
        if any(inside(target, root) for target in targets for root in protected):
            violations[f"protected:{role}:{operation}"] += 1
        if role in {"other", "unattributed"}:
            return
        counts[f"{role}:{operation}"] += 1
        if not all(any(inside(target, root) for root in permitted.get(role, ()))
                   for target in targets):
            violations[f"outside-scope:{role}:{operation}"] += 1
        if role == "calibration" and start_ticks <= requested <= completed <= end_ticks:
            file_events.add((identity, operation, *targets))

    def read_events(stream):
        digest = hashlib.sha256()
        for line in stream:
            digest.update(line)
            event = json.loads(line)
            require(type(event["ticks"]) is int and capture_bounds[0] <= event["ticks"] <= capture_bounds[1],
                    "ETW event timestamp outside capture")
            if event["ticks"] <= end_ticks:
                yield event
        require(digest.hexdigest() == capture["events_sha256"], "ETW export digest mismatch")

    with path.open("rb") as stream:
        unresolved = correlate_requests(
            read_events(stream), lambda value: canonical_file_path(value, devices),
            classify_process, lambda value: value is not None and
            any(inside(value, root) for root in protected), record, strict=True,
        )
    if unresolved:
        issues.add("etw-mutation-coverage-unresolved")
    return counts, violations, file_events, dict(unresolved)


def audit(manifest, sysmon, procmon, before, after, *, private_endpoints=None, etw=False):
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
            manifest, procmon, start, end, processes, roles, protected + immutable, permitted, issues)
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
        **({"file_evidence_source": "etw", "etw_unresolved_mutations": etw_diagnostics} if etw else {}),
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
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    subcommands = cli.add_subparsers(dest="mode", required=True)
    snapshot = subcommands.add_parser("snapshot")
    snapshot.add_argument("manifest", type=Path)
    snapshot.add_argument("output", type=Path)
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
    args = cli.parse_args()
    try:
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
            result = audit(read_json(args.manifest), args.sysmon, args.etw_events if etw else args.procmon,
                           read_json(args.before), read_json(args.after), private_endpoints=endpoints, etw=etw)
            if private:
                with private.open("x", encoding="utf-8") as stream:
                    json.dump(endpoints, stream, indent=2)
                    stream.write("\n")
        with output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except (ValueError, KeyError, OSError, TypeError, AttributeError, StopIteration, ET.ParseError, csv.Error):
        print("N12 BLOCKED: missing, invalid or inaccessible evidence; no result emitted.", file=sys.stderr)
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
