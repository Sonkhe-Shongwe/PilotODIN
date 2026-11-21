"""Source-only observer for the future N12 no-CDP app lifecycle.

This module never spawns, closes, kills, polls a network port, or enumerates OS
processes by itself. Existing journey.spawn may call its prelaunch_hook after
exclusive app.log creation, while the caller must separately own the native
launch, Windows CloseMainWindow action, and profile capture authorisation.
Nothing in current native workflows invokes this observer.
"""
from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_no_cdp_log_witness as log
from qa.p4_research import n12_no_cdp_main_window as window


NATIVE_ACK_CONSENT = "I_APPROVE_ONE_N12_NO_CDP_STORAGE"


def verify_opt_in_environment(*, vite_env, app_env, expected_profile):
    """Validate already supplied isolated QA settings. Never set consent."""
    trace.require(type(vite_env) is dict and type(app_env) is dict
                  and vite_env.get("VITE_PILOTODIN_N12_NO_CDP") == "1"
                  and app_env.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == NATIVE_ACK_CONSENT,
                  "no-cdp-opt-in-consent-missing")
    # The QA profile must be an explicit absolute Windows path. Do not infer
    # it from a debugger PID or browser port, or silently accept other flags.
    try:
        profile_matches = (trace.windows_path(expected_profile)
                           == trace.windows_path(app_env.get("WEBVIEW2_USER_DATA_FOLDER")))
    except (TypeError, AttributeError, trace.EvidenceValidationError):
        profile_matches = False
    trace.require(profile_matches, "no-cdp-profile-setting-mismatch")
    trace.require(not any(name.upper().startswith("WEBVIEW2_")
                          and name.upper() != "WEBVIEW2_USER_DATA_FOLDER"
                          and value for name, value in app_env.items()),
                  "no-cdp-browser-override-present")
    trace.require(not any(name.upper().startswith("WEBVIEW2_") and value
                          for name, value in vite_env.items()),
                  "no-cdp-vite-browser-override-present")
    return True


class NoCdpLifecycleObserver:
    """Guarded source path: prelaunch -> handle -> window -> log -> preclose -> exit.

    The class has no start, close, or native capture method. The caller must
    use the separately authorised launcher and normal OS close helper.
    Synthetic tests inject handle/window readers, but not a fake native pass.
    """

    def __init__(self, *, stack, expected_source, actual_source,
                 expected_executable_sha256, actual_executable_sha256,
                 expected_image, expected_title):
        trace.require(callable(getattr(stack, "callback", None)),
                      "no-cdp-cleanup-stack-missing")
        trace.require(type(expected_title) is str and bool(expected_title)
                      and type(expected_image) is str and bool(expected_image),
                      "no-cdp-main-window-contract-missing")
        self._stack = stack
        self._source = expected_source
        self._actual_source = actual_source
        self._exe = expected_executable_sha256
        self._actual_exe = actual_executable_sha256
        self._image = expected_image
        self._title = expected_title
        self._witness = None
        self._process = None
        self._birth = None
        self._window = None
        self._provisional = None
        self._close_prepared = False
        self._finished = False

    def prelaunch_hook(self, app_log):
        """Supply directly to journey.spawn(..., prelaunch_log_hook=...)."""
        trace.require(self._witness is None and self._process is None,
                      "no-cdp-prelaunch-repeated")
        witness = log.prepare_prelaunch_log(
            app_log, expected_source=self._source, actual_source=self._actual_source,
            expected_executable_sha256=self._exe,
            actual_executable_sha256=self._actual_exe,
        )
        self._stack.callback(witness.close)
        self._witness = witness
        return witness

    def bind_process(self, process, *, handle_reader=None):
        """Pin the retained original handle's birth, not an independently reused PID."""
        trace.require(self._witness is not None and not self._witness.handle.closed
                      and self._process is None and type(getattr(process, "pid", None)) is int
                      and process.pid > 0 and callable(getattr(process, "poll", None))
                      and process.poll() is None,
                      "no-cdp-live-app-handle-unverified")
        if handle_reader is None:
            from qa.p4_native.n12_lifetime_control import process_times
            handle_reader = lambda app: process_times(app, allow_running=True)
        identity = handle_reader(process)
        trace.require(type(identity) is dict and identity.get("pid") == process.pid
                      and type(identity.get("birth")) is int
                      and identity["birth"] > 0 and identity.get("exit") is None
                      and process.poll() is None,
                      "no-cdp-live-app-handle-unverified")
        self._process = process
        self._birth = identity["birth"]

    def observe_readiness(self, *, window_observer=None, timeout_seconds=30,
                          window_timeout_seconds=10, clock=None, sleep=None):
        trace.require(self._process is not None and self._window is None
                      and self._provisional is None and not self._finished
                      and self._witness is not None and not self._witness.handle.closed,
                      "no-cdp-ready-stage-invalid")
        window_options = {
            "expected_image": self._image, "expected_title": self._title,
            "expected_birth_ticks": self._birth,
            "timeout_seconds": window_timeout_seconds,
            "observer": window_observer,
        }
        if clock is not None:
            window_options["clock"] = clock
        if sleep is not None:
            window_options["sleep"] = sleep
        # The clean absence-only wait is independent of the log read.
        # A bad/duplicate window can never be mistaken for a slow startup.
        identity = window.wait_for_main_window(self._process, **window_options)
        options = {"expected_pid": self._process.pid,
                   "main_window_identity_verified": True,
                   "timeout_seconds": timeout_seconds}
        if clock is not None:
            options["clock"] = clock
        if sleep is not None:
            options["sleep"] = sleep
        provisional = log.wait_for_readiness(self._witness, self._process, **options)
        self._window = identity
        self._provisional = provisional
        return {
            "scope": "no-cdp-provisional-source-readiness-only",
            "window": "unique-window-source-observed",
            "log": "provisional-marker-observed",
            "native_N12_acceptance": "NOT_EVALUATED",
            "file_event_coverage": "NOT_EVALUATED",
            "network_isolation": "NOT_EVALUATED",
        }

    def prepare_normal_close(self, *, recheck_window=None):
        """Return a scoped witness, never call CloseMainWindow or bypass its veto."""
        trace.require(self._provisional is not None
                      and not self._close_prepared and not self._finished
                      and self._process.poll() is None,
                      "no-cdp-close-stage-invalid")
        if recheck_window is None:
            recheck_window = window.confirm_same_main_window
        checked = recheck_window(
            self._window, self._process, expected_image=self._image,
            expected_title=self._title,
        )
        trace.require(isinstance(checked, window.MainWindowIdentity)
                      and (checked.hwnd, checked.pid, checked.process_birth_ticks)
                      == (self._window.hwnd, self._window.pid,
                          self._window.process_birth_ticks)
                      and self._process.poll() is None,
                      "no-cdp-window-recheck-unverified")
        self._close_prepared = True
        return {"scope": "no-cdp-preclose-window-witness-only",
                "normal_close": "EXTERNAL_HELPER_REQUIRED",
                "native_N12_acceptance": "NOT_EVALUATED"}

    def verify_after_close(self, *, close_request_verified,
                           profile_processes_before, profile_processes_after):
        """Only after external Windows normal close and retained-handle exit 0.

        Profile path substring counts are a diagnostic, NOT complete browser
        exit attribution. Never grant file/network/native N12 acceptance.
        """
        trace.require(self._close_prepared and not self._finished,
                      "no-cdp-postclose-stage-invalid")
        trace.require(close_request_verified is True
                      and self._process.poll() == 0,
                      "no-cdp-graceful-close-unverified")
        trace.require(type(profile_processes_before) is int
                      and profile_processes_before > 0
                      and type(profile_processes_after) is int
                      and profile_processes_after == 0,
                      "no-cdp-profile-count-diagnostic-unverified")
        receipt = log.verify_after_normal_close(
            self._witness, self._provisional, process=self._process,
            expected_pid=self._process.pid, close_request_verified=True,
        )
        self._finished = True
        return {
            **receipt,
            "scope": "no-cdp-source-lifecycle-witness-only",
            "window": "same-window-observed-before-close",
            "profile_count_diagnostic": "before-positive-after-zero",
            "profile_process_identity": "NOT_EVALUATED",
            "network_isolation": "NOT_EVALUATED",
            "native_N12_acceptance": "NOT_EVALUATED",
            "owner_native_execution_authorized": False,
        }
