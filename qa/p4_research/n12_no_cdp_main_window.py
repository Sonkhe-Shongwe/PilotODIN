"""Read-only no-CDP Windows main-window identity, not native N12 acceptance.

The pure selector is exercised with generated windows. The Windows observer is
NOT invoked by current N12 workflows. It performs only user32 window queries and
reads the original subprocess handle; it cannot launch or close a window.
"""
from dataclasses import dataclass, field
import ctypes
from ctypes import wintypes
import os
import time

from qa.p4_native import n12_trace as trace

MAX_ENUM_WINDOWS = 4096
MAX_TITLE_CHARS = 1024
MAX_WINDOW_WAIT_SECONDS = 20
WINDOW_POLL_SECONDS = 0.1


@dataclass(frozen=True)
class WindowRecord:
    # Private observation. Do not publish repr or serialize these records.
    hwnd: int = field(repr=False)
    pid: int = field(repr=False)
    title: str = field(repr=False)
    visible: bool
    owner_hwnd: int = field(repr=False)
    root_hwnd: int = field(repr=False)


@dataclass(frozen=True)
class MainWindowIdentity:
    hwnd: int = field(repr=False)
    pid: int = field(repr=False)
    process_birth_ticks: int = field(repr=False)

    def redacted_receipt(self):
        return {
            "scope": "no-cdp-main-window-source-witness-only",
            "main_window_identity": "UNIQUE_MATCHING_PROCESS_WINDOW",
            "native_N12_acceptance": "NOT_EVALUATED",
            "browser_process_identity": "NOT_EVALUATED",
            "file_event_coverage": "NOT_EVALUATED",
            "network_isolation": "NOT_EVALUATED",
        }


def select_main_window(records, *, expected_pid, expected_image,
                       observed_image, expected_birth_ticks, observed_birth_ticks,
                       expected_title, process_live):
    """Pure, fail-closed selection from a complete trusted OS window snapshot.

    PIDs and snapshots are only meaningful when the caller independently pins
    a live original Windows process handle and exact creation timestamp.
    """
    trace.require(type(expected_pid) is int and expected_pid > 0
                  and process_live is True and type(expected_birth_ticks) is int
                  and expected_birth_ticks > 0
                  and type(observed_birth_ticks) is int
                  and observed_birth_ticks == expected_birth_ticks,
                  "no-cdp-window-process-lifetime-unverified")
    try:
        image_ok = trace.windows_path(observed_image) == trace.windows_path(expected_image)
    except (TypeError, AttributeError, trace.EvidenceValidationError):
        image_ok = False
    trace.require(image_ok, "no-cdp-window-executable-mismatch")
    trace.require(type(expected_title) is str and 0 < len(expected_title) <= MAX_TITLE_CHARS,
                  "no-cdp-window-title-unverified")
    trace.require(isinstance(records, (list, tuple)) and len(records) <= MAX_ENUM_WINDOWS
                  and all(isinstance(r, WindowRecord) for r in records),
                  "no-cdp-window-snapshot-unverified")
    trace.require(len({r.hwnd for r in records}) == len(records)
                  and all(type(r.hwnd) is int and r.hwnd > 0
                          and type(r.pid) is int and r.pid >= 0
                          and type(r.title) is str
                          and type(r.visible) is bool
                          and type(r.owner_hwnd) is int and r.owner_hwnd >= 0
                          and type(r.root_hwnd) is int and r.root_hwnd >= 0
                          for r in records),
                  "no-cdp-window-snapshot-unverified")
    # An identically titled foreign window means the title cannot independently
    # identify the window. Hidden duplicates are ambiguous as well.
    trace.require(not any(r.title == expected_title and r.pid != expected_pid for r in records),
                  "no-cdp-window-title-collision")
    matches = [r for r in records if r.title == expected_title and r.pid == expected_pid]
    # Only a clean *absence* of both expected app windows and the exact
    # expected title is retryable. A wrong-title app window, foreign-title
    # collision, hidden match or duplicate is a hard identity failure.
    if not matches and not any(r.pid == expected_pid for r in records):
        raise trace.EvidenceValidationError("no-cdp-window-not-yet-present")
    trace.require(len(matches) == 1, "no-cdp-window-missing-or-ambiguous")
    main = matches[0]
    trace.require(main.visible and main.owner_hwnd == 0 and main.root_hwnd == main.hwnd,
                  "no-cdp-window-not-unique-top-level")
    return MainWindowIdentity(main.hwnd, expected_pid, expected_birth_ticks)


def _enumerate_windows(expected_pid, expected_title):
    """Read top-level windows, process IDs, owner/root and exact visible title.

    This is a Windows-only read. It must be called only in a separately
    approved native QA observation, never from routine fixture CI.
    """
    trace.require(os.name == "nt", "no-cdp-window-windows-only")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetAncestor.restype = wintypes.HWND
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL

    rows = []
    issues = []

    @callback_type
    def each_window(hwnd, _):
        try:
            if len(rows) >= MAX_ENUM_WINDOWS:
                issues.append("no-cdp-window-enumeration-limit")
                return False
            process_id = wintypes.DWORD()
            thread = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if not thread:
                issues.append("no-cdp-window-pid-unavailable")
                return False
            length = user32.GetWindowTextLengthW(hwnd)
            if length < 0 or (length > MAX_TITLE_CHARS and process_id.value == expected_pid):
                issues.append("no-cdp-window-title-unavailable")
                return False
            if length > MAX_TITLE_CHARS:
                title = ""  # Cannot equal the bounded expected QA title.
            else:
                buffer = ctypes.create_unicode_buffer(MAX_TITLE_CHARS + 1)
                count = user32.GetWindowTextW(hwnd, buffer, len(buffer))
                if count <= 0 and length > 0 and process_id.value == expected_pid:
                    issues.append("no-cdp-window-title-unavailable")
                    return False
                title = buffer.value
            if process_id.value == expected_pid or title == expected_title:
                if not user32.IsWindow(hwnd):
                    issues.append("no-cdp-window-handle-invalid")
                    return False
                rows.append(WindowRecord(
                    int(hwnd), int(process_id.value), title,
                    bool(user32.IsWindowVisible(hwnd)),
                    int(user32.GetWindow(hwnd, 4) or 0),  # GW_OWNER
                    int(user32.GetAncestor(hwnd, 2) or 0),  # GA_ROOT
                ))
        except Exception:
            issues.append("no-cdp-window-enumeration-error")
            return False
        return True

    try:
        ok = user32.EnumWindows(each_window, 0)
    except (OSError, ValueError, TypeError) as exc:
        raise trace.EvidenceValidationError("no-cdp-window-enumeration-error") from exc
    trace.require(ok and not issues, issues[0] if issues else "no-cdp-window-enumeration-error")
    return rows


def observe_main_window(process, *, expected_image, expected_title, expected_birth_ticks):
    """Bind a unique Windows main window to the *retained* live app handle.

    Does not use CDP, the browser port, unverified PID lookup, or any close
    command. Reobservation after readiness must agree on hwnd and birth.
    """
    trace.require(os.name == "nt", "no-cdp-window-windows-only")
    trace.require(getattr(process, "poll", None) is not None
                  and process.poll() is None
                  and type(getattr(process, "pid", None)) is int
                  and getattr(process, "_handle", None),
                  "no-cdp-window-process-lifetime-unverified")
    from qa.p4_native.n12_lifetime_control import process_images, process_times
    original = process_times(process, allow_running=True)
    images = process_images(process)
    trace.require(original.get("pid") == process.pid
                  and original.get("exit") is None,
                  "no-cdp-window-process-lifetime-unverified")
    identity = select_main_window(
        _enumerate_windows(process.pid, expected_title),
        expected_pid=process.pid, expected_image=expected_image,
        observed_image=images.get("image_dos"),
        expected_birth_ticks=expected_birth_ticks,
        observed_birth_ticks=original.get("birth"),
        expected_title=expected_title, process_live=True,
    )
    # Do not admit a window from a process that exited during enumeration.
    trace.require(process.poll() is None
                  and process_times(process, allow_running=True) == original,
                  "no-cdp-window-process-lifetime-unverified")
    return identity


def wait_for_main_window(process, *, expected_image, expected_title,
                         expected_birth_ticks, timeout_seconds=10,
                         observer=None, clock=time.monotonic, sleep=time.sleep):
    """Bound the *absence-only* startup wait, without weakening identity checks.

    A full OS observation on every attempt must independently pin the original
    live handle and exact image/birth. Only a clean 'not yet present' error may
    be retried. Ambiguous windows, invalid snapshots, changing identity, and
    access failures stop immediately; no browser port is queried.
    """
    trace.require(type(timeout_seconds) in (int, float)
                  and 0 < timeout_seconds <= MAX_WINDOW_WAIT_SECONDS,
                  "no-cdp-window-wait-timeout-invalid")
    trace.require(callable(getattr(process, "poll", None))
                  and type(getattr(process, "pid", None)) is int
                  and process.pid > 0,
                  "no-cdp-window-process-lifetime-unverified")
    if observer is None:
        observer = observe_main_window
    trace.require(callable(observer) and callable(clock) and callable(sleep),
                  "no-cdp-window-observer-unverified")
    deadline = clock() + timeout_seconds
    last_sample = None
    while True:
        trace.require(process.poll() is None,
                      "no-cdp-window-app-exited-before-ready")
        try:
            seen = observer(
                process, expected_image=expected_image, expected_title=expected_title,
                expected_birth_ticks=expected_birth_ticks,
            )
        except trace.EvidenceValidationError as exc:
            if str(exc) != "no-cdp-window-not-yet-present":
                raise
        else:
            trace.require(isinstance(seen, MainWindowIdentity)
                          and seen.pid == process.pid
                          and seen.process_birth_ticks == expected_birth_ticks
                          and type(seen.hwnd) is int and seen.hwnd > 0,
                          "no-cdp-window-result-unverified")
            trace.require(process.poll() is None,
                          "no-cdp-window-app-exited-before-ready")
            completed_at = clock()
            trace.require(last_sample is None or completed_at >= last_sample,
                          "no-cdp-window-clock-invalid")
            trace.require(completed_at <= deadline,
                          "no-cdp-window-wait-timeout")
            return seen
        current = clock()
        trace.require(last_sample is None or current >= last_sample,
                      "no-cdp-window-clock-invalid")
        last_sample = current
        if current >= deadline:
            raise trace.EvidenceValidationError("no-cdp-window-wait-timeout")
        sleep(min(WINDOW_POLL_SECONDS, max(0.0, deadline - current)))


def confirm_same_main_window(previous, process, *, expected_image, expected_title):
    """Read-only recheck just before an independently controlled normal close."""
    trace.require(isinstance(previous, MainWindowIdentity),
                  "no-cdp-window-previous-identity-unverified")
    new = observe_main_window(process, expected_image=expected_image,
                              expected_title=expected_title,
                              expected_birth_ticks=previous.process_birth_ticks)
    trace.require((new.hwnd, new.pid, new.process_birth_ticks)
                  == (previous.hwnd, previous.pid, previous.process_birth_ticks),
                  "no-cdp-window-changed-before-close")
    return new
