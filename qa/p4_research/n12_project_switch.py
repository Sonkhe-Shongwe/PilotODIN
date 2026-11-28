"""Operate the staged N12 project-switch dialog without a PowerShell child."""

import argparse
import ctypes
from ctypes import wintypes
import ntpath
import os
from pathlib import Path
import re
import time

from qa.p4_native.n12_lifetime_control import open_process_query_handle, process_images, process_times
from qa.p4_native.n12_trace import EvidenceValidationError, local_disposable_path, require
from qa.p4_research import n12_app_build as build


ACTIONS = ("Stay", "Switch project")
DIALOG_TITLE = "PilotODIN - Unsaved changes"
WM_GETTEXT = 0x000D
BM_CLICK = 0x00F5
SMTO_ABORTIFHUNG = 0x0002


class WindowsControls:
    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        hwnd, uint, lparam = wintypes.HWND, wintypes.UINT, wintypes.LPARAM
        self.callback = ctypes.WINFUNCTYPE(wintypes.BOOL, hwnd, lparam)
        self.user32.EnumWindows.argtypes = (self.callback, lparam)
        self.user32.EnumChildWindows.argtypes = (hwnd, self.callback, lparam)
        self.user32.GetWindowThreadProcessId.argtypes = (hwnd, ctypes.POINTER(wintypes.DWORD))
        self.user32.GetWindowTextW.argtypes = (hwnd, wintypes.LPWSTR, ctypes.c_int)
        self.user32.GetClassNameW.argtypes = (hwnd, wintypes.LPWSTR, ctypes.c_int)
        self.user32.IsWindowVisible.argtypes = (hwnd,)
        self.user32.IsWindowEnabled.argtypes = (hwnd,)
        self.user32.SendMessageTimeoutW.argtypes = (
            hwnd, uint, wintypes.WPARAM, lparam, uint, uint, ctypes.POINTER(ctypes.c_size_t),
        )
        self.user32.SendMessageTimeoutW.restype = lparam

    def windows(self, parent=None):
        windows = []

        @self.callback
        def collect(window, _):
            windows.append(window)
            return True

        if parent is None:
            require(self.user32.EnumWindows(collect, 0), "Could not enumerate native windows.")
        else:
            self.user32.EnumChildWindows(parent, collect, 0)
        return windows

    def visible_owned(self, window, pid):
        owner = wintypes.DWORD()
        return (self.user32.GetWindowThreadProcessId(window, ctypes.byref(owner)) and
                owner.value == pid and self.user32.IsWindowVisible(window))

    def title(self, window):
        text = ctypes.create_unicode_buffer(256)
        self.user32.GetWindowTextW(window, text, len(text))
        return text.value

    def is_button(self, window):
        kind = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(window, kind, len(kind))
        return kind.value == "Button" or kind.value.startswith("WindowsForms10.BUTTON.")

    def send(self, window, message, wparam, lparam, timeout_ms):
        result = ctypes.c_size_t()
        return self.user32.SendMessageTimeoutW(window, message, wparam, lparam, SMTO_ABORTIFHUNG,
                                                timeout_ms, ctypes.byref(result))

    def label(self, button):
        text = ctypes.create_unicode_buffer(256)
        if self.send(button, WM_GETTEXT, len(text), ctypes.addressof(text), 250):
            return text.value
        return ""


def press_project_switch(pid, action, expected_image, *, timeout=12):
    require(action in ACTIONS and pid > 0, "Invalid native project-switch action or PID.")
    with open_process_query_handle(pid) as process:
        image = process_images(process)["image_dos"]
        require(ntpath.normcase(image) == ntpath.normcase(str(expected_image)),
                "The dialog owner does not match the expected executable.")
        windows = WindowsControls()
        deadline = time.monotonic() + timeout
        stage = "APP_WINDOW_NOT_VISIBLE"
        while time.monotonic() < deadline:
            require(process_times(process, allow_running=True)["exit"] is None, "The dialog owner exited.")
            owned = [window for window in windows.windows() if windows.visible_owned(window, pid)]
            dialogs = [window for window in owned if windows.title(window) == DIALOG_TITLE]
            require(len(dialogs) <= 1, "DIALOG_AMBIGUOUS: multiple matching project-switch dialogs")
            if dialogs:
                stage = "DIALOG_FOUND_BUTTONS_MISSING"
                dialog = dialogs[0]
                matches = {label: [] for label in ACTIONS}
                for child in windows.windows(dialog):
                    if windows.visible_owned(child, pid) and windows.is_button(child):
                        label = windows.label(child)
                        if label in matches:
                            matches[label].append(child)
                require(all(len(buttons) <= 1 for buttons in matches.values()),
                        "BUTTONS_AMBIGUOUS: multiple matching native button handles")
                if all(matches.values()):
                    button = matches[action][0]
                    if windows.user32.IsWindowEnabled(button) and time.monotonic() < deadline:
                        require(process_times(process, allow_running=True)["exit"] is None and
                                windows.visible_owned(dialog, pid) and windows.visible_owned(button, pid),
                                "The dialog owner or control changed.")
                        require(windows.send(button, BM_CLICK, 0, 0, 1000),
                                "The native button did not acknowledge BM_CLICK.")
                        return
            elif owned and stage == "APP_WINDOW_NOT_VISIBLE":
                stage = "APP_VISIBLE_DIALOG_MISSING"
            time.sleep(0.2)
    raise EvidenceValidationError(f"Native project-switch discovery timed out. Stage={stage}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--action", choices=ACTIONS, required=True)
    args = parser.parse_args()
    try:
        env = os.environ
        run = env.get("GITHUB_RUN_ID", "")
        require(re.fullmatch(r"[0-9]+", run) and env.get("GITHUB_RUN_ATTEMPT") == "1" and
                env.get("PILOTODIN_P4_UNPACKAGED_NATIVE_DEV_CONSENT") == build.CONSENT and
                env.get("PILOTODIN_N12_APP_JOURNEY_CONSENT") == "I_APPROVE_ONE_N12_APP_JOURNEY",
                "N12 project-switch requires an approved hosted journey.")
        staged = Path(env["RUNNER_TEMP"]) / f"pilotodin-n12-build-{run}"
        expected = local_disposable_path(build.executable(staged), runner_temp_only=True).resolve(strict=True)
        press_project_switch(args.pid, args.action, expected)
    except (EvidenceValidationError, OSError, KeyError) as error:
        parser.exit(2, f"N12 native project-switch failed: {error}\n")
    print("Project-switch action delivered using native button handles")


if __name__ == "__main__":
    main()
