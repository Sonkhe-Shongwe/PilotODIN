"""Collect diagnostic Windows handle witnesses from the actual N12 driver tree."""

from collections import Counter, defaultdict
from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import ntpath
import os
from threading import Event, Lock, Thread

from qa.p4_native import n12_trace as trace
from qa.p4_native.n12_exit_corroboration import (
    BIRTH_TOLERANCE_TICKS, SOURCE_COVERAGE_ISSUES, EtwLifetimes, compare_image_path,
)


FAMILIES = {"node.exe": "node", "powershell.exe": "powershell", "pwsh.exe": "powershell",
            "cmd.exe": "cmd", "conhost.exe": "conhost", "esbuild.exe": "esbuild",
            "python.exe": "python", "msedgewebview2.exe": "webview"}
INTERVAL_SECONDS = 0.01
HANDLE_LIMIT = 96


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                ("name", wintypes.WCHAR * 260)]


class ProcessSnapshots:
    def __init__(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.create = kernel.CreateToolhelp32Snapshot
        self.create.argtypes = (wintypes.DWORD, wintypes.DWORD)
        self.create.restype = wintypes.HANDLE
        self.close = kernel.CloseHandle
        self.close.argtypes = (wintypes.HANDLE,)
        self.close.restype = wintypes.BOOL
        self.first = kernel.Process32FirstW
        self.next = kernel.Process32NextW
        for method in (self.first, self.next):
            method.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
            method.restype = wintypes.BOOL

    def collect(self):
        handle = self.create(2, 0)  # TH32CS_SNAPPROCESS
        if handle is None or handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ProcessEntry()
            entry.size = ctypes.sizeof(entry)
            rows = []
            found = self.first(handle, ctypes.byref(entry))
            while found:
                rows.append((entry.pid, entry.parent, entry.name.casefold()))
                found = self.next(handle, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(ctypes.get_last_error())
            return rows
        finally:
            self.close(handle)


def descendants(rows, active):
    children = defaultdict(list)
    for pid, parent, name in rows:
        children[parent].append((pid, name))
    seen = set(active)
    pending = list(active)
    while pending:
        parent = pending.pop()
        for pid, name in children[parent]:
            if pid > 0 and pid not in seen:
                seen.add(pid)
                yield pid, parent, name
                pending.append(pid)


class DriverHandles:
    def __init__(self):
        self.roots = {}
        self.lock = Lock()
        self.stop = Event()
        self.thread = None
        self.witnesses = []
        self.counts = Counter()

    def __enter__(self):
        if os.name == "nt":
            self.thread = Thread(target=self._observe, daemon=True, name="n12-driver-handles")
            self.thread.start()
        return self

    def __exit__(self, *_):
        if self.thread is not None:
            self.stop.set()
            self.thread.join()

    def watch(self, process, label):
        with self.lock:
            self.roots[process.pid] = process, label

    def inventory(self):
        return {"retained_handles": len(self.witnesses), "retained_by_label": dict(Counter(
                    w["label"] for w in self.witnesses)), "retained_families": dict(Counter(
                    family(w["image_dos"]) for w in self.witnesses)), "monitor_counts": dict(self.counts)}

    def _observe(self):
        from qa.p4_native.n12_lifetime_control import open_process_query_handle, process_images, process_times

        watched = {}
        finished = {}
        root_seen = set()
        try:
            snapshots = ProcessSnapshots()
            with ExitStack() as resources:
                while not self.stop.is_set():
                    with self.lock:
                        roots = list(self.roots.values())
                    for process, label in roots:
                        if process.pid in root_seen:
                            continue
                        root_seen.add(process.pid)
                        try:
                            times = process_times(process, allow_running=True)
                            images = process_images(process)
                            trace.windows_path(images["image_dos"])
                            watched[process.pid, times["birth"]] = process, images, label, None
                        except (OSError, trace.EvidenceValidationError):
                            self.counts["root_query_unavailable"] += 1
                    active = {}
                    for key, (process, _, _, _) in watched.items():
                        if key in finished:
                            continue
                        try:
                            times = process_times(process, allow_running=True)
                            if times["exit"] is None:
                                active[process.pid] = times["birth"]
                            else:
                                finished[key] = times
                        except (OSError, trace.EvidenceValidationError):
                            self.counts["time_query_unavailable"] += 1
                    if active and len(watched) < HANDLE_LIMIT:
                        try:
                            rows = snapshots.collect()
                        except OSError:
                            self.counts["snapshot_unavailable"] += 1
                            rows = []
                        for pid, parent, name in descendants(rows, active):
                            if len(watched) >= HANDLE_LIMIT:
                                self.counts["handle_limit_reached"] = 1
                                break
                            try:
                                with ExitStack() as pending:
                                    process = pending.enter_context(open_process_query_handle(pid))
                                    times = process_times(process, allow_running=True)
                                    images = process_images(process)
                                    trace.windows_path(images["image_dos"])
                                    trace.require(ntpath.basename(images["image_dos"]).casefold() == name,
                                                  "driver child image changed after enumeration")
                                    key = pid, times["birth"]
                                    if key not in watched:
                                        watched[key] = process, images, "descendant", parent
                                        resources.enter_context(pending.pop_all())
                            except (OSError, trace.EvidenceValidationError):
                                self.counts["child_query_unavailable"] += 1
                    self.stop.wait(INTERVAL_SECONDS)
                for key, (process, images, label, parent) in watched.items():
                    try:
                        times = finished.get(key) or process_times(process)
                        self.witnesses.append(times | images | {"label": label, "parent_pid": parent})
                    except (OSError, trace.EvidenceValidationError):
                        self.counts["exit_unavailable"] += 1
        except (OSError, AttributeError, TypeError, ValueError):
            self.counts["monitor_unavailable"] += 1


def family(image):
    return FAMILIES.get(ntpath.basename(image).casefold(), "other")


def driver_lifetime_evidence(events, devices, window, observed, handles, issues):
    source_gaps = sorted(issues & SOURCE_COVERAGE_ISSUES)
    lifetimes = None
    if not source_gaps:
        try:
            lifetimes = EtwLifetimes(events, devices, window)
        except (KeyError, TypeError, ValueError):
            source_gaps = ["etw-process-payload-unverified"]
    by_pid = defaultdict(list)
    for witness in handles.witnesses:
        by_pid[witness["pid"]].append(witness)
    dispositions = Counter()
    disputed = []
    for process in observed.processes.values():
        role = observed.roles.get(process.guid, "unattributed")
        parent = observed.processes.get(process.parent)
        parent_role = observed.roles.get(process.parent, "unattributed")
        if role != "driver" and parent_role != "driver":
            continue
        matching = [w for w in by_pid[process.pid]
                    if abs(w["birth"] - trace.utc_ticks(process.start)) <= BIRTH_TOLERANCE_TICKS
                    and trace.windows_path(w["image_dos"]) == process.image
                    and (w["parent_pid"] is None or parent is not None and w["parent_pid"] == parent.pid)]
        order = None
        if len(matching) != 1:
            status = "handle-unavailable-or-ambiguous"
        elif lifetimes is None:
            status = "etw-coverage-unavailable"
        else:
            witness = matching[0]
            order = lifetimes.order_comparison(process, witness)
            try:
                start, _ = lifetimes.find(process, handle_witness=witness)
                trace.require(start.sequence is not None, "driver-etw-sequence-unverified")
                if witness["parent_pid"] is not None:
                    parent_start, parent_stop = lifetimes.find(parent)
                    trace.require(start.parent == parent_start.pid
                                  and start.parent_sequence == parent_start.sequence
                                  and parent_start.creation <= start.creation <= parent_stop.exit,
                                  "driver-etw-parent-lifetime-unverified")
                trace.require(compare_image_path(witness["image_native"], process.image, devices) == "exact-path-match",
                              "driver-handle-image-unverified")
                status = "MATCH"
            except trace.EvidenceValidationError as exc:
                status = str(exc)
        dispositions[status] += 1
        if process.disputed_exit is not None:
            disputed.append({"record": process.disputed_exit.record, "family": family(process.image),
                             "parent_family": family(parent.image) if parent is not None else "unavailable",
                             "role": role, "parent_role": parent_role, "status": status, "order": order})
    return {**handles.inventory(), "etw_source_issues": source_gaps,
            "scoped_driver_dispositions": dict(dispositions), "disputed": sorted(disputed, key=lambda row: row["record"])}
