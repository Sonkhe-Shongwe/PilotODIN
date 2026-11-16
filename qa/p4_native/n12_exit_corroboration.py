"""Diagnostic ETW corroboration of disputed Sysmon exits in the N12 journey."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import ntpath

if __package__:
    from . import n12_trace as trace
    from .n12_etw_correlate import canonical_file_path
else:
    import n12_trace as trace
    from n12_etw_correlate import canonical_file_path


BIRTH_TOLERANCE_TICKS = 10_000  # 1 ms, to identify matches for this diagnostic.
SOURCE_COVERAGE_ISSUES = {
    "sysmon-record-gap", "sysmon-bookend-record-mismatch",
    "sysmon-restart-config-change-or-error", "etw-event-or-buffer-loss", "etw-no-buffers-written",
}


@dataclass(frozen=True)
class Lifecycle:
    pid: int
    sequence: int | None
    creation: int
    emission: int
    image: str | None
    parent: int | None = None
    parent_sequence: int | None = None
    exit: int | None = None


def read_lifecycle(row):
    data = row["data"]
    kind, version = row["id"], row["version"]
    trace.require(type(version) is int and version >= 0 and not row.get("lifecycle_fields_ambiguous"),
                  "unverified ETW process event schema")
    pid = trace.etw_unsigned(data["ProcessID"])
    creation = trace.etw_payload_ticks(data["CreateTime"])
    sequence = trace.etw_unsigned(data["ProcessSequenceNumber"]) if "ProcessSequenceNumber" in data else None
    trace.require(version < (3 if kind == 1 else 2) or sequence is not None,
                  "missing ETW process sequence")
    common = (pid, sequence, creation, row["ticks"], data.get("ImageName"))
    if kind == 2:
        return Lifecycle(*common, exit=trace.etw_payload_ticks(data["ExitTime"]))
    parent = trace.etw_unsigned(data["ParentProcessID"])
    parent_sequence = (trace.etw_unsigned(data["ParentProcessSequenceNumber"])
                       if "ParentProcessSequenceNumber" in data else None)
    trace.require(version < 3 or parent_sequence is not None, "missing ETW parent sequence")
    return Lifecycle(*common, parent=parent, parent_sequence=parent_sequence)


def compare_image_path(image, expected_path, devices):
    """Return a fixed label for an ETW process-start executable comparison."""
    if image is None or image == "":
        return "missing-image"
    if not isinstance(image, str):
        return "invalid-image-type"
    path = canonical_file_path(image, devices)
    if path is not None:
        if path == expected_path:
            return "exact-path-match"
        if ntpath.basename(path) == ntpath.basename(expected_path):
            return "different-path-same-basename"
        return "different-executable-name"

    spelling = image.replace("/", "\\").casefold()
    if spelling.startswith(("\\device\\", "\\\\?\\globalroot\\device\\")):
        return "unmapped-device-path"
    if spelling and ntpath.basename(spelling) == spelling:
        return "basename-only"
    return "unsupported-path-form"


class EtwLifetimes:
    def __init__(self, events, devices, window):
        self.starts = defaultdict(list)
        self.stops = defaultdict(list)
        self.by_sequence = defaultdict(list)
        self.devices = devices
        self.window = window
        for row in events:
            if row["lifecycle"] and row["id"] in (1, 2):
                event = read_lifecycle(row)
                index = self.starts if row["id"] == 1 else self.stops
                index[event.pid].append(event)
                if event.sequence is not None:
                    self.by_sequence[event.sequence].append(event)

    def _start_candidates(self, process):
        birth = trace.utc_ticks(process.start)
        return [event for event in self.starts[process.pid]
                if abs(event.creation - birth) <= BIRTH_TOLERANCE_TICKS]

    def start_image_comparison(self, process):
        candidates = self._start_candidates(process)
        if len(candidates) != 1:
            return "start-missing-or-ambiguous"
        return compare_image_path(candidates[0].image, process.image, self.devices)

    def _candidate_pair(self, process):
        candidates = self._start_candidates(process)
        trace.require(len(candidates) == 1, "etw-start-missing-or-ambiguous")
        start = candidates[0]
        stops = [event for event in self.stops[start.pid] if event.creation == start.creation]
        trace.require(len(stops) == 1, "etw-stop-missing-or-ambiguous")
        stop = stops[0]
        trace.require(start.sequence == stop.sequence and (start.sequence is None or
                      len(self.by_sequence[start.sequence]) == 2), "etw-sequence-conflict")
        return start, stop

    def _order_deltas(self, start, stop):
        first, last = self.window
        return {
            "creation_minus_window_start_ticks": start.creation - first,
            "start_emission_minus_creation_ticks": start.emission - start.creation,
            "stop_emission_minus_start_emission_ticks": stop.emission - start.emission,
            "window_end_minus_stop_emission_ticks": last - stop.emission,
            "exit_minus_creation_ticks": stop.exit - start.creation,
            "stop_emission_minus_exit_ticks": stop.emission - stop.exit,
        }

    def handle_order_comparison(self, process, witness):
        """Report only relative times for the unique ETW pair and original handle."""
        try:
            start, stop = self._candidate_pair(process)
        except trace.EvidenceValidationError as exc:
            return {"issue": str(exc)}
        return {**self._order_deltas(start, stop),
                "etw_payload_creation_minus_handle_ticks": start.creation - witness["birth"],
                "etw_payload_exit_minus_handle_ticks": stop.exit - witness["exit"]}

    def find(self, process):
        start, stop = self._candidate_pair(process)
        deltas = self._order_deltas(start, stop)
        trace.require(all(delta >= 0 for delta in deltas.values()) and
                      deltas["stop_emission_minus_start_emission_ticks"] > 0,
                      "etw-lifetime-order-unverified")
        trace.require(not any(event is not start and start.creation <= event.creation <= stop.exit
                              for event in self.starts[start.pid]), "overlapping-etw-pid-lifetimes")
        trace.require(not any(event is not stop and event.creation < start.creation <= event.exit
                              for event in self.stops[start.pid]), "overlapping-etw-pid-lifetimes")
        trace.require(compare_image_path(start.image, process.image, self.devices) == "exact-path-match",
                      "etw-start-image-unverified")
        if isinstance(stop.image, str):
            exit_path = canonical_file_path(stop.image, self.devices)
            expected = process.image if exit_path is not None else ntpath.basename(process.image)
            trace.require((exit_path or stop.image.casefold()) == expected, "etw-stop-image-conflict")
        return start, stop


def corroborate_exits(events, processes, roles, devices, window, issues):
    disputed = sorted((p for p in processes.values() if p.disputed_exit),
                      key=lambda p: p.disputed_exit.record)
    source_gaps = sorted(issues & SOURCE_COVERAGE_ISSUES)
    try:
        lifetime = None if source_gaps else EtwLifetimes(events, devices, window)
    except (KeyError, TypeError, ValueError):
        lifetime = None
        source_gaps = ["etw-process-payload-unverified"]

    by_pid = defaultdict(list)
    for process in processes.values():
        by_pid[process.pid].append(process)
    rows = []
    for process in disputed:
        original = process.disputed_exit
        row = {
            "record": original.record, "role": roles.get(process.guid, "unattributed"),
            "sysmon_exit_minus_birth_ticks": trace.utc_ticks(original.stamp) - trace.utc_ticks(process.start),
            "sysmon_image_unverified": original.image_unverified, "sysmon_time_conflict": original.time_conflict,
            "status": "BLOCKED",
        }
        rows.append(row)
        if source_gaps:
            row["issues"] = source_gaps
            continue
        try:
            start, stop = lifetime.find(process)
            trace.require(sum(abs(trace.utc_ticks(p.start) - start.creation) <= BIRTH_TOLERANCE_TICKS
                              for p in by_pid[process.pid]) == 1, "competing-sysmon-process-births")
            parent = processes.get(process.parent)
            trace.require(parent is not None and parent.pid == start.parent and parent.pid != process.pid,
                          "etw-parent-identity-unverified")
            parent_start, parent_stop = lifetime.find(parent)
            trace.require(sum(abs(trace.utc_ticks(p.start) - parent_start.creation) <= BIRTH_TOLERANCE_TICKS
                              for p in by_pid[parent.pid]) == 1, "competing-sysmon-parent-births")
            trace.require(start.parent_sequence == parent_start.sequence
                          and parent_start.creation <= start.creation <= parent_stop.exit
                          and parent_start.emission < start.emission < parent_stop.emission,
                          "etw-parent-lifetime-unverified")
        except trace.EvidenceValidationError as exc:
            row["issues"] = [str(exc)]
        else:
            row.update(status="CORROBORATED_DIAGNOSTIC",
                       etw_birth_minus_sysmon_birth_ticks=start.creation - trace.utc_ticks(process.start),
                       etw_exit_minus_sysmon_exit_ticks=stop.exit - trace.utc_ticks(original.stamp),
                       etw_duration_ticks=stop.exit - start.creation)
    return rows
