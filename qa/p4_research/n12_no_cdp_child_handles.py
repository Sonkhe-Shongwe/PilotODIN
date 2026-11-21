"""Default-off, hosted-QA-only WebView child handle capture and shadow join.

No current native workflow imports or activates this observer. Even an entirely
reviewable result is diagnostic, NEVER full Stage 1 or N12 acceptance.
"""
from collections import Counter, defaultdict
from contextlib import ExitStack
import ntpath
import os
from pathlib import Path
import re
from threading import Event, Thread

from qa.p4_native import n12_trace as trace
from qa.p4_native.n12_exit_corroboration import (
    BIRTH_TOLERANCE_TICKS, SOURCE_COVERAGE_ISSUES, compare_image_path,
)
from qa.p4_research.n12_driver_handles import ProcessSnapshots, descendants


CHILD_HANDLE_CONSENT = "I_APPROVE_ONE_N12_QA_CHILD_HANDLES"
WEBVIEW = "msedgewebview2.exe"
MAX_HANDLES = 96
POLL_SECONDS = 0.01
SAFE_FAULTS = frozenset({
    "snapshot-unavailable", "snapshot-duplicate-or-reused-pid",
    "child-query-unavailable", "child-image-unverified",
    "child-image-changed", "child-root-chronology-unverified",
    "unexpected-descendant", "handle-limit-reached",
    "handle-exit-unavailable", "root-identity-unverified",
    "observer-internal-failure",
})


def _hosted_scope(env, profile, expected_app):
    """Fail before any process enumeration, without consulting owner files."""
    trace.require(os.name == "nt" and env.get("GITHUB_ACTIONS") == "true"
                  and env.get("RUNNER_ENVIRONMENT") == "github-hosted"
                  and env.get("RUNNER_OS") == "Windows"
                  and env.get("GITHUB_EVENT_NAME") == "push"
                  and env.get("GITHUB_RUN_ATTEMPT") == "1"
                  and re.fullmatch(r"[0-9a-f]{40}", env.get("PILOTODIN_N12_APPROVED_SOURCE", ""))
                  and env.get("PILOTODIN_N12_CHILD_HANDLE_CONSENT") == CHILD_HANDLE_CONSENT
                  and env.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == "I_APPROVE_ONE_N12_NO_CDP_STORAGE",
                  "no-cdp-child-handle-hosted-consent-or-source-unverified")
    root = trace.local_disposable_path(profile, runner_temp_only=True)
    binary = trace.local_disposable_path(expected_app, runner_temp_only=True)
    trace.require(root.is_dir() and not root.is_symlink()
                  and binary.is_file() and not binary.is_symlink(),
                  "no-cdp-child-handle-disposable-scope-unverified")


class ScopedQaChildHandleObserver:
    """Capture original WebView2 process query handles, never child verdicts.

    The root is the actual retained Popen handle, NOT a PID looked up again.
    Snapshot rows are restricted to its descendant PID tree before OpenProcess.
    Subsequent Sysmon/ETW GUID and parent-sequence review must establish
    completeness, because this 10-ms sampler can miss short-lived children.
    """

    def __init__(self, *, root_process, expected_app_image, snapshots=None,
                 open_handle=None, process_times=None, process_images=None,
                 max_handles=MAX_HANDLES, poll_seconds=POLL_SECONDS):
        trace.require(type(max_handles) is int and 1 <= max_handles <= MAX_HANDLES
                      and type(poll_seconds) in (float, int) and 0 < poll_seconds <= 0.01
                      and type(root_process.pid) is int and root_process.pid > 0,
                      "no-cdp-child-observer-options-invalid")
        self.root = root_process
        self.expected_app_image = trace.windows_path(expected_app_image)
        self.snapshots = snapshots
        # Synthetic sampling must not initialize Win32, even on CI Linux.
        self._injected = (open_handle is not None and process_times is not None
                          and process_images is not None)
        self._live_armed = False
        self.open_handle = open_handle
        self.process_times = process_times
        self.process_images = process_images
        self.max_handles = max_handles
        self.poll_seconds = poll_seconds
        self._stop = Event()
        self._thread = None
        self._resources = ExitStack()
        self._root_birth = None
        self._retained = {}  # (pid, exact birth) -> (original handle, images, parent PID)
        self._pid_birth = {}
        self._witnesses = []
        self.faults = Counter()
        self.samples = 0
        self._finished = False

    def _backend(self, *, need_snapshot=False):
        if need_snapshot and self.snapshots is None:
            self.snapshots = ProcessSnapshots()
        if self.open_handle is None or self.process_times is None or self.process_images is None:
            from qa.p4_native.n12_lifetime_control import (
                open_process_query_handle, process_images, process_times,
            )
            self.open_handle = self.open_handle or open_process_query_handle
            self.process_times = self.process_times or process_times
            self.process_images = self.process_images or process_images

    def _verify_root(self):
        times = self.process_times(self.root, allow_running=True)
        images = self.process_images(self.root)
        trace.require(times["pid"] == self.root.pid and type(times["birth"]) is int
                      and times["birth"] > 0
                      and trace.windows_path(images["image_dos"]) == self.expected_app_image,
                      "no-cdp-child-root-identity-unverified")
        if self._root_birth is None:
            self._root_birth = times["birth"]
        trace.require(times["birth"] == self._root_birth,
                      "no-cdp-child-root-birth-changed")
        return times

    def sample_once(self, rows=None):
        """One bounded, test-injectable sample; no broad handle enumeration."""
        trace.require(not self._finished, "no-cdp-child-observer-already-finished")
        trace.require(self._live_armed or (rows is not None and self._injected),
                      "no-cdp-child-live-sampling-not-authorized")
        self._backend(need_snapshot=rows is None)
        try:
            root_times = self._verify_root()
        except (OSError, KeyError, TypeError, ValueError, trace.EvidenceValidationError):
            self.faults["root-identity-unverified"] += 1
            return
        if root_times["exit"] is not None:
            return
        try:
            if rows is None:
                rows = self.snapshots.collect()
            trace.require(type(rows) is list and all(
                type(row) is tuple and len(row) == 3
                and type(row[0]) is int and type(row[1]) is int
                and isinstance(row[2], str) for row in rows),
                "no-cdp-child-snapshot-invalid")
        except (OSError, TypeError, ValueError, trace.EvidenceValidationError):
            self.faults["snapshot-unavailable"] += 1
            return
        self.samples += 1
        # The shared descendants() iterator intentionally deduplicates PIDs.
        # Inspect the ORIGINAL snapshot too: two rows for one scoped PID
        # cannot be silently collapsed into an authoritative process.
        occurrence = Counter(pid for pid, _, _ in rows)
        for pid, parent, name in descendants(rows, {self.root.pid}):
            if occurrence[pid] != 1:
                self.faults["snapshot-duplicate-or-reused-pid"] += 1
                continue
            if name != WEBVIEW:
                # Do not query unrelated executables even inside PID ancestry.
                # Any extra descendant must be explicitly reviewed later.
                self.faults["unexpected-descendant"] += 1
                continue
            if len(self._retained) >= self.max_handles and pid not in self._pid_birth:
                self.faults["handle-limit-reached"] += 1
                continue
            try:
                with ExitStack() as pending:
                    handle = pending.enter_context(self.open_handle(pid))
                    times = self.process_times(handle, allow_running=True)
                    images = self.process_images(handle)
                    trace.require(type(times["birth"]) is int and times["pid"] == pid
                                  and times["birth"] >= self._root_birth,
                                  "no-cdp-child-root-chronology-unverified")
                    dos = trace.windows_path(images["image_dos"])
                    trace.require(ntpath.basename(dos) == WEBVIEW
                                  and isinstance(images["image_native"], str)
                                  and images["image_native"].casefold().startswith("\\device\\"),
                                  "no-cdp-child-image-unverified")
                    birth = times["birth"]
                    previous = self._pid_birth.get(pid)
                    if previous is not None:
                        if previous != birth:
                            self.faults["snapshot-duplicate-or-reused-pid"] += 1
                        elif self._retained[pid, birth][2] != parent:
                            self.faults["snapshot-duplicate-or-reused-pid"] += 1
                        continue
                    self._pid_birth[pid] = birth
                    self._retained[pid, birth] = (
                        handle, images, parent)
                    self._resources.enter_context(pending.pop_all())
            except (OSError, KeyError, TypeError, ValueError, trace.EvidenceValidationError):
                self.faults["child-query-unavailable"] += 1

    def _observe(self):
        try:
            while not self._stop.is_set():
                self.sample_once()
                self._stop.wait(self.poll_seconds)
        except Exception:
            self.faults["observer-internal-failure"] += 1

    def start_live(self, *, profile, env=None):
        """Never start on owner PC, without distinct one-use source consent."""
        env = dict(os.environ) if env is None else env
        _hosted_scope(env, Path(profile), Path(self.expected_app_image))
        trace.require(self._thread is None and not self._finished, "no-cdp-child-observer-already-started")
        self._backend(need_snapshot=True)
        self._verify_root()
        self._live_armed = True
        self._thread = Thread(target=self._observe, name="n12-isolated-qa-webview-handles",
                              daemon=True)
        self._thread.start()
        return self

    def finish(self):
        """Query retained ORIGINAL handles after normal exit, then close them."""
        trace.require(not self._finished, "no-cdp-child-observer-already-finished")
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self._finished = True
        try:
            for (pid, birth), (handle, images, parent) in sorted(self._retained.items()):
                try:
                    times = self.process_times(handle)
                    trace.require(times["pid"] == pid and times["birth"] == birth
                                  and type(times["exit"]) is int and times["exit"] >= birth,
                                  "no-cdp-child-original-handle-exit-unverified")
                    self._witnesses.append({
                        "pid": pid, "birth": birth, "exit": times["exit"],
                        "image_dos": images["image_dos"],
                        "image_native": images["image_native"],
                        "parent_pid": parent,
                    })
                except (OSError, KeyError, TypeError, ValueError, trace.EvidenceValidationError):
                    self.faults["handle-exit-unavailable"] += 1
        finally:
            self._resources.close()
        return tuple(self._witnesses)

    def redacted_receipt(self):
        return {
            "scope": "isolated-qa-webview-original-handle-sampler",
            "status": "SAMPLING_FINISHED_UNVERIFIED" if self._finished and self.samples > 0
                      and not self.faults else "BLOCKED",
            "sample_count": self.samples,
            "retained_original_handle_count": len(self._witnesses),
            "faults": dict(sorted(self.faults.items())),
            "native_N12_acceptance": "NOT_EVALUATED",
        }


def review_scoped_children(*, processes, roles, app_guid, witnesses, lifetimes,
                           collector_receipt, source_issues):
    """Diagnostic-only complete GUID-child to original-handle join.

    No PID-only joins: each child must uniquely match a retained original
    handle's birth, exit, both full image representations and its Sysmon
    parent PID, then pass the independent ETW/parent-sequence shadow review.
    """
    failures = Counter()
    found = Counter()
    covered = Counter()
    receipt = {"scope": "isolated-qa-child-handle-sysmon-etw-shadow-join",
               "status": "BLOCKED", "native_N12_acceptance": "NOT_EVALUATED",
               "child_role_counts": {}, "verified_handle_counts": {},
               "failed_checks": {}}
    if (not isinstance(processes, dict) or not isinstance(roles, dict)
            or type(app_guid) is not str or app_guid not in processes
            or not isinstance(witnesses, (list, tuple))
            or not isinstance(source_issues, set)
            or not isinstance(collector_receipt, dict)
            or not hasattr(lifetimes, "shadow_handle_exit_review")):
        receipt["failed_checks"] = {"invalid-capture-input": 1}
        return receipt
    if source_issues:
        # Any pre-existing Sysmon/ETW identity or capture issue blocks this
        # proposed whole-subtree review, not only the familiar loss labels.
        failures["source-coverage-or-identity-unverified"] += 1
    if collector_receipt.get("status") != "SAMPLING_FINISHED_UNVERIFIED" or (
            collector_receipt.get("faults")):
        failures["child-handle-sampling-incomplete"] += 1
    if not witnesses:
        failures["child-original-handles-unavailable"] += 1
    app = processes[app_guid]
    if roles.get(app_guid) != "app":
        failures["app-scope-unverified"] += 1

    def within_app(process):
        seen = {process.guid}
        while process.parent in processes:
            if process.parent in seen:
                return False
            if process.parent == app_guid:
                return True
            seen.add(process.parent)
            process = processes[process.parent]
        return False

    expected = [p for p in processes.values() if p.guid != app_guid and within_app(p)]
    if any(ntpath.basename(p.image) != WEBVIEW
           or roles.get(p.guid) not in {"webview", "webview-network"} for p in expected):
        failures["unexpected-app-descendant"] += 1
    children = [p for p in expected if ntpath.basename(p.image) == WEBVIEW
                and roles.get(p.guid) in {"webview", "webview-network"}]
    for p in children:
        found[roles[p.guid]] += 1
    if not found["webview"] or not found["webview-network"]:
        failures["browser-role-coverage-missing"] += 1
    if any(role in {"webview", "webview-network"} and not within_app(process)
           for guid, process in processes.items() if (role := roles.get(guid))):
        failures["out-of-app-scoped-role"] += 1

    by_pid = defaultdict(list)
    for w in witnesses:
        if not isinstance(w, dict) or type(w.get("pid")) is not int:
            failures["invalid-original-handle-witness"] += 1
            continue
        by_pid[w["pid"]].append(w)
    used = set()
    for child in children:
        parent = processes.get(child.parent)
        matches = []
        for w in by_pid[child.pid]:
            if (type(w.get("birth")) is not int or type(w.get("exit")) is not int
                    or w.get("parent_pid") != getattr(parent, "pid", None)
                    or abs(w["birth"] - trace.utc_ticks(child.start)) > BIRTH_TOLERANCE_TICKS):
                continue
            try:
                if (trace.windows_path(w["image_dos"]) != child.image or
                        compare_image_path(w["image_native"], child.image,
                                           lifetimes.devices) != "exact-path-match"):
                    continue
            except (KeyError, TypeError, ValueError, trace.EvidenceValidationError):
                continue
            matches.append(w)
        if len(matches) != 1:
            failures["original-child-handle-missing-or-ambiguous"] += 1
            continue
        if id(matches[0]) in used:
            failures["original-child-handle-reused"] += 1
            continue
        used.add(id(matches[0]))
        review = lifetimes.shadow_handle_exit_review(
            child, witness=matches[0], parent=parent, require_parent=True)
        if review["status"] == "REVIEWABLE_ONLY":
            covered[roles[child.guid]] += 1
        else:
            for label in review["failed_checks"]:
                failures[label] += 1
    if len(used) != len(witnesses):
        failures["unmatched-or-duplicate-retained-handle"] += 1
    receipt["child_role_counts"] = dict(sorted(found.items()))
    receipt["verified_handle_counts"] = dict(sorted(covered.items()))
    receipt["failed_checks"] = dict(sorted(failures.items()))
    if not failures and found == covered:
        receipt["status"] = "REVIEWABLE_ONLY"
    return receipt
