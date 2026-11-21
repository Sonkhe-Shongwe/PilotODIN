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
OBSERVED_STOP_BASENAME_PREFIX_LENGTH = 14
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


def compare_stop_image(image, expected_path, devices):
    """Describe the stop field with fixed labels and no raw image values."""
    kind = compare_image_path(image, expected_path, devices)
    if kind != "basename-only":
        return kind
    basename = ntpath.basename(expected_path)
    spelling = image.casefold()
    if spelling == basename:
        return "exact-basename-match"
    if basename.startswith(spelling):
        return "short-basename-prefix"
    return "different-basename"


class EtwLifetimes:
    def __init__(self, events, devices, window, *, no_cdp_sysmon_corroboration=False):
        # Opt-in only for the distinct no-CDP hosted lifetime/profile
        # diagnostic; ordinary N12 retains its existing strict behavior.
        self.no_cdp_sysmon_corroboration = no_cdp_sysmon_corroboration
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

    def stop_image_comparison(self, process):
        try:
            _, stop = self._candidate_pair(process)
        except trace.EvidenceValidationError as exc:
            return str(exc)
        return compare_stop_image(stop.image, process.image, self.devices)

    def parent_sequence_comparison(self, process, parent):
        """Compare the ETW births without exposing a process identifier or sequence."""
        if parent is None or parent.pid == process.pid:
            return "sysmon-parent-unverified"
        births = []
        for label, candidate in (("child", process), ("parent", parent)):
            starts = self._start_candidates(candidate)
            if len(starts) != 1:
                return f"etw-{label}-birth-missing-or-ambiguous"
            start = starts[0]
            if compare_image_path(start.image, candidate.image, self.devices) != "exact-path-match":
                return f"etw-{label}-birth-image-unverified"
            births.append(start)
        child_start, parent_start = births
        if child_start.parent != parent_start.pid:
            return "etw-parent-pid-conflict"
        if child_start.parent_sequence is None or parent_start.sequence is None:
            return "etw-parent-sequence-unavailable"
        if child_start.parent_sequence != parent_start.sequence:
            return "etw-parent-sequence-conflict"
        return "etw-parent-sequence-agrees"

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

    def _no_cdp_sysmon_checks(self, process, start, stop):
        """The EXACT existing fail-closed corroboration predicate, item by item.

        These labels are static and privacy-safe. The return value is also
        consumed by the original verifier, so the diagnostic cannot diverge
        from the actual approval decision.
        """
        return {
            "no-cdp-scope-enabled": self.no_cdp_sysmon_corroboration is True,
            "sysmon-exit-present": process.end is not None,
            "sysmon-exit-not-disputed": process.disputed_exit is None,
            "etw-sequence-present-and-equal": start.sequence is not None and start.sequence == stop.sequence,
            "etw-lifetime-payload-within-window": self.window[0] <= start.creation <= stop.exit <= self.window[1],
            "etw-birth-within-original-sysmon-bound":
                abs(start.creation - trace.utc_ticks(process.start)) <= BIRTH_TOLERANCE_TICKS,
            "etw-exit-exactly-matches-sysmon":
                process.end is not None and stop.exit == trace.utc_ticks(process.end),
            "etw-start-exact-image":
                compare_image_path(start.image, process.image, self.devices) == "exact-path-match",
        }

    def _no_cdp_sysmon_confirmed(self, process, start, stop):
        """No-CDP only: retain all original checks, with NO time relaxation."""
        return all(self._no_cdp_sysmon_checks(process, start, stop).values())

    def no_cdp_sysmon_diagnostic(self, process, *, handle_witness=None):
        """Private-data-safe reason receipt; never authorizes a process lifetime.

        Only named check outcomes and relative FILETIME deltas may be emitted.
        Missing ETW pairs fail closed without guessing which PID/image was seen.
        """
        if not self.no_cdp_sysmon_corroboration:
            return {"status": "NOT_EVALUATED", "failed_checks": []}
        try:
            start, stop = self._candidate_pair(process)
        except trace.EvidenceValidationError as exc:
            # Whitelist ONLY fixed internal labels, never propagate arbitrary
            # error text into the redacted diagnostic receipt.
            label = str(exc)
            if label not in {"etw-start-missing-or-ambiguous",
                             "etw-stop-missing-or-ambiguous",
                             "etw-sequence-conflict"}:
                label = "etw-pair-unverified"
            return {"status": "BLOCKED", "failed_checks": [label]}
        checks = self._no_cdp_sysmon_checks(process, start, stop)
        receipt = {
            "status": "CHECKS_MATCH" if all(checks.values()) else "BLOCKED",
            "failed_checks": sorted(label for label, value in checks.items() if not value),
            "etw_birth_minus_sysmon_birth_ticks": start.creation - trace.utc_ticks(process.start),
            "etw_exit_minus_sysmon_exit_ticks":
                stop.exit - trace.utc_ticks(process.end) if process.end is not None else None,
        }
        if handle_witness is not None:
            receipt.update({
                "sysmon_birth_minus_handle_ticks":
                    trace.utc_ticks(process.start) - handle_witness["birth"],
                "sysmon_exit_minus_handle_ticks":
                    trace.utc_ticks(process.end) - handle_witness["exit"]
                    if process.end is not None else None,
            })
        return receipt

    def _order_issues(self, start, stop, deltas, *, exact_handle, independent_sysmon=False):
        # Keep event-header ordering strict. Header-versus-provider-FILETIME
        # comparisons may be bypassed ONLY with independent Sysmon evidence.
        early_stop_supported = ((exact_handle or independent_sysmon)
                                and start.sequence is not None and stop.exit <= self.window[1])
        return [label for failed, label in (
            (deltas["creation_minus_window_start_ticks"] < 0, "creation-before-window"),
            (deltas["start_emission_minus_creation_ticks"] < 0 and not independent_sysmon,
             "start-header-before-creation"),
            (deltas["stop_emission_minus_start_emission_ticks"] <= 0, "stop-header-at-or-before-start-header"),
            (deltas["window_end_minus_stop_emission_ticks"] < 0, "stop-header-after-window"),
            (deltas["exit_minus_creation_ticks"] < 0, "exit-before-creation"),
            (deltas["stop_emission_minus_exit_ticks"] < 0 and not early_stop_supported,
             "stop-header-before-unconfirmed-exit"),
        ) if failed]

    def order_comparison(self, process, witness=None):
        """Report relative times for the unique ETW pair and available original handle."""
        try:
            start, stop = self._candidate_pair(process)
        except trace.EvidenceValidationError as exc:
            return {"issue": str(exc)}
        deltas = self._order_deltas(start, stop)
        if witness is not None:
            deltas.update(etw_payload_creation_minus_handle_ticks=start.creation - witness["birth"],
                          etw_payload_exit_minus_handle_ticks=stop.exit - witness["exit"])
        exact_handle = witness is not None and (start.pid, start.creation, stop.exit) == (
            witness["pid"], witness["birth"], witness["exit"])
        deltas["ordering_issues"] = self._order_issues(start, stop, deltas, exact_handle=exact_handle)
        return deltas

    def find(self, process, *, handle_witness=None):
        start, stop = self._candidate_pair(process)
        if handle_witness is not None:
            trace.require((start.pid, start.creation, stop.exit) ==
                          (handle_witness["pid"], handle_witness["birth"], handle_witness["exit"]),
                          "etw-and-windows-handle-timestamps-differ")
        sysmon_confirmed = self._no_cdp_sysmon_confirmed(process, start, stop)
        if self.no_cdp_sysmon_corroboration:
            trace.require(sysmon_confirmed, "no-cdp-sysmon-lifetime-unverified")
        trace.require(not self._order_issues(
            start, stop, self._order_deltas(start, stop),
            exact_handle=handle_witness is not None,
            independent_sysmon=sysmon_confirmed,
        ), "etw-lifetime-order-unverified")
        trace.require(not any(event is not start and start.creation <= event.creation <= stop.exit
                              for event in self.starts[start.pid]), "overlapping-etw-pid-lifetimes")
        trace.require(not any(event is not stop and event.creation < start.creation <= event.exit
                              for event in self.stops[start.pid]), "overlapping-etw-pid-lifetimes")
        trace.require(compare_image_path(start.image, process.image, self.devices) == "exact-path-match",
                      "etw-start-image-unverified")
        if isinstance(stop.image, str):
            stop_form = compare_stop_image(stop.image, process.image, self.devices)
            # A prefix cannot identify an executable without both full paths
            # from the original handle, whose PID and exact clocks matched above.
            handle_confirms_short_name = (
                stop_form == "short-basename-prefix" and stop.image.isascii()
                and len(stop.image) == OBSERVED_STOP_BASENAME_PREFIX_LENGTH
                and handle_witness is not None and start.sequence is not None
                and all(compare_image_path(handle_witness.get(key), process.image, self.devices) == "exact-path-match"
                        for key in ("image_dos", "image_native"))
            )
            # A WebView stop can contain a fixed ANSI prefix. It is never
            # sufficient alone: require the full ETW start path, unique ETW
            # sequence, and separately verified full-image Sysmon GUID exit.
            sysmon_confirms_short_name = (
                self.no_cdp_sysmon_corroboration and sysmon_confirmed
                and stop_form == "short-basename-prefix" and stop.image.isascii()
                and len(stop.image) == OBSERVED_STOP_BASENAME_PREFIX_LENGTH
            )
            trace.require(stop_form in {"exact-path-match", "exact-basename-match"}
                          or handle_confirms_short_name or sysmon_confirms_short_name,
                          "etw-stop-image-conflict")
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


def journey_lifetime_evidence(events, devices, window, observed, witnesses, executable_sha256, issues):
    """Report handle-backed app evidence while the combined audit keeps its own verdict."""
    report = {"scope": "diagnostic-only-before-file-correlation", "launches": {}}
    source_gaps = sorted(issues & SOURCE_COVERAGE_ISSUES)
    if not source_gaps:
        try:
            lifetimes = EtwLifetimes(events, devices, window)
        except (KeyError, TypeError, ValueError):
            source_gaps = ["etw-process-payload-unverified"]
    roots = [process for root, process in observed.bindings if root["role"] == "app"]
    processes = sorted(observed.processes.values(), key=lambda process: process.start)
    for label in ("first", "relaunch"):
        row = {"handle": "BLOCKED", "issues": [], "children": {}}
        report["launches"][label] = row
        if source_gaps:
            row["issues"] = source_gaps
            continue
        witness = witnesses.get(label)
        if witness is None:
            row["issues"] = ["original-app-handle-unavailable"]
            continue
        candidates = [root for root in roots if root.pid == witness["pid"] and root.sha256 == executable_sha256]
        if len(candidates) != 1:
            row["issues"] = ["app-sysmon-root-unverified"]
            continue
        root = candidates[0]
        row["start_image"] = lifetimes.start_image_comparison(root)
        row["stop_image"] = lifetimes.stop_image_comparison(root)
        row["order"] = lifetimes.order_comparison(root, witness)
        matched = {}
        try:
            start, stop = lifetimes.find(root, handle_witness=witness)
            trace.require(start.sequence is not None, "etw-app-sequence-unverified")
            trace.require(all(compare_image_path(witness.get(key), root.image, devices) == "exact-path-match"
                              for key in ("image_dos", "image_native")), "app-handle-image-unverified")
            matched[root.guid] = start, stop
            row["handle"] = "MATCH"
        except trace.EvidenceValidationError as exc:
            row["issues"].append(str(exc))
        tree = {root.guid}
        for process in processes:
            if process.parent not in tree:
                continue
            tree.add(process.guid)
            role = observed.roles.get(process.guid, "unattributed")
            child = row["children"].setdefault(role, {"start_images": {}, "stop_images": {}, "lifetime": {}})
            for key, category in (("start_images", lifetimes.start_image_comparison(process)),
                                  ("stop_images", lifetimes.stop_image_comparison(process))):
                counts = child[key]
                counts[category] = counts.get(category, 0) + 1
            try:
                child_witness = witness.get("children", {}).get(process.pid) if role in {
                    "webview", "webview-network",
                } else None
                if child_witness is not None:
                    trace.require(all(compare_image_path(child_witness.get(key), process.image, devices)
                                      == "exact-path-match" for key in ("image_dos", "image_native")),
                                  "webview-handle-image-unverified")
                start, stop = lifetimes.find(process, handle_witness=child_witness)
                parent = matched.get(process.parent)
                trace.require(parent is not None and start.sequence is not None
                              and start.parent == parent[0].pid and start.parent_sequence == parent[0].sequence
                              and parent[0].creation <= start.creation <= parent[1].exit,
                              "app-tree-etw-parent-lifetime-unverified")
                matched[process.guid] = start, stop
                category = "MATCH"
            except trace.EvidenceValidationError as exc:
                category = str(exc)
            counts = child["lifetime"]
            counts[category] = counts.get(category, 0) + 1
    return report
