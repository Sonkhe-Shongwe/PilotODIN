"""Fail-closed OS-evidence browser identity for a future no-CDP N12 probe.

No process is launched or changed. This verifier is not wired into the native
runner, and its positive receipt does not establish file/network isolation.
All private PIDs, paths and commands stay inside the returned identity object.
"""
from dataclasses import dataclass, field
import ntpath
import re

from qa.p4_native import n12_trace as trace


_WEBVIEW = "msedgewebview2.exe"
_TYPE_SWITCH = re.compile(r"(?:^|\s)--type(?=[=\s]|$)", re.I)
_DEBUG_SWITCH = re.compile(
    r"(?:^|\s)--(?:remote-debugging-port|remote-debugging-pipe|log-net-log)(?=[=\s]|$)", re.I
)
_PROFILE_SWITCH = re.compile(r'(?:^|\s)--user-data-dir=(?:"([^"\r\n]+)"|([^\s"]+))(?=\s|$)', re.I)
_PROFILE_TOKEN = re.compile(r"(?:^|\s)--user-data-dir(?=[=\s]|$)", re.I)


@dataclass(frozen=True)
class BrowserIdentity:
    # Private corroborated process coordinates. Never serialize or log these.
    guid: str = field(repr=False)
    pid: int = field(repr=False)
    image: str = field(repr=False)
    profile: str = field(repr=False)

    def redacted_receipt(self):
        return {
            "scope": "no-cdp-browser-identity-only",
            "browser_process_identity": "UNIQUE_SYSMON_ETW_APP_PROFILE",
            "candidate_count": 1,
            "native_N12_acceptance": "NOT_EVALUATED",
            "file_event_coverage": "NOT_EVALUATED",
            "network_isolation": "NOT_EVALUATED",
        }


def _profile_from_command(command):
    """Require one complete quoted/unquoted Chromium user-data-dir switch."""
    tokens = _PROFILE_TOKEN.findall(command)
    matches = list(_PROFILE_SWITCH.finditer(command))
    trace.require(len(tokens) == len(matches) == 1, "no-cdp-browser-profile-ambiguous")
    raw = matches[0].group(1) or matches[0].group(2)
    try:
        return trace.windows_path(raw)
    except (TypeError, AttributeError, trace.EvidenceValidationError) as exc:
        raise trace.EvidenceValidationError("no-cdp-browser-profile-invalid") from exc


def resolve_browser_identity(*, processes, roles, app_guid, expected_app_image,
                             expected_app_sha256, disposable_profile, launch, ready,
                             close, capture_end, app_handle_witness, etw_lifetimes):
    """Bind one browser through Sysmon and independent ETW lifetime evidence.

    The caller must supply a capture-scoped Sysmon process map, role bindings,
    pinned app executable/hash, app Windows handle witness, and the real
    EtwLifetimes object built from loss-reviewed OS events. A synthetic fake
    used by unit tests never certifies native execution. Process identity is
    only returned after close, when ETW stop records are available.
    """
    trace.require(type(processes) is dict and type(roles) is dict
                  and type(app_guid) is str and app_guid in processes,
                  "no-cdp-app-identity-missing")
    app = processes[app_guid]
    trace.require(roles.get(app_guid) == "app" and app.image == trace.windows_path(expected_app_image)
                  and type(expected_app_sha256) is str
                  and re.fullmatch(r"[0-9a-f]{64}", expected_app_sha256)
                  and app.sha256 == expected_app_sha256,
                  "no-cdp-app-source-unverified")
    profile = trace.windows_path(disposable_profile)
    trace.require(app.end is not None, "no-cdp-app-exit-unverified")
    trace.require(launch < ready < close < capture_end and app.start <= launch
                  and app.end >= close, "no-cdp-stage-order-unverified")

    # Enumerate every Sysmon GUID descendant, even one omitted from roles.
    # Never allow an unbound WebView child to disappear from candidate review.
    scoped = [p for p in processes.values()
              if p.guid == app_guid or _descends_from(p, app_guid, processes)]
    webviews = [p for p in scoped if ntpath.basename(p.image) == _WEBVIEW]
    trace.require(bool(webviews), "no-cdp-browser-zero-or-multiple")
    trace.require(all(roles.get(p.guid) in {"webview", "webview-network"}
                      for p in webviews), "no-cdp-webview-role-unverified")
    trace.require(all(not _DEBUG_SWITCH.search(p.command) for p in scoped),
                  "no-cdp-debug-switch-present")
    browsers = [p for p in scoped if p.guid != app_guid
                and ntpath.basename(p.image) == _WEBVIEW
                and not _TYPE_SWITCH.search(p.command)]
    trace.require(len(browsers) == 1, "no-cdp-browser-zero-or-multiple")
    browser = browsers[0]
    trace.require(roles.get(browser.guid) == "webview" and browser.parent == app_guid,
                  "no-cdp-browser-ancestry-unverified")
    trace.require(browser.start >= launch and browser.start <= ready
                  and browser.end is not None and close <= browser.end <= capture_end,
                  "no-cdp-browser-lifetime-unverified")
    trace.require(_profile_from_command(browser.command) == profile,
                  "no-cdp-browser-profile-mismatch")

    # Independently verify app/child image, PID/sequence, creation and stop
    # using the existing ETW validator. No inferred/guessed browser PID.
    trace.require(app_handle_witness is not None,
                  "no-cdp-app-handle-unverified")
    app_birth, app_stop = etw_lifetimes.find(app, handle_witness=app_handle_witness)
    browser_birth, browser_stop = etw_lifetimes.find(browser)
    trace.require(etw_lifetimes.parent_sequence_comparison(browser, app)
                  == "etw-parent-sequence-agrees"
                  and browser_birth.parent == app_birth.pid
                  and browser_birth.parent_sequence == app_birth.sequence
                  and app_birth.creation <= browser_birth.creation <= browser_stop.exit
                  and browser_stop.exit <= trace.utc_ticks(capture_end)
                  and browser_birth.creation >= trace.utc_ticks(launch)
                  and browser_birth.creation <= trace.utc_ticks(ready)
                  and browser_stop.exit >= trace.utc_ticks(close)
                  and app_stop.exit >= trace.utc_ticks(close),
                  "no-cdp-etw-browser-ancestry-or-lifetime-unverified")
    return BrowserIdentity(browser.guid, browser.pid, browser.image, profile)


def _descends_from(process, app_guid, processes):
    """Return true only for a complete, acyclic GUID ancestry chain."""
    seen = {process.guid}
    current = process
    while current.parent and current.parent in processes:
        if current.parent in seen:
            return False
        if current.parent == app_guid:
            return True
        seen.add(current.parent)
        current = processes[current.parent]
    return False
