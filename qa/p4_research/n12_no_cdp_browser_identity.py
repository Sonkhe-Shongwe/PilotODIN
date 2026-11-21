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
    # The launch stage is recorded BEFORE journey.spawn creates the app.
    trace.require(launch < ready < close < capture_end
                  and launch <= app.start <= ready and app.end >= close,
                  "no-cdp-stage-order-unverified")

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


@dataclass(frozen=True)
class ProfileShutdownWitness:
    # Private process GUID and browser handle are never exposed in a receipt.
    browser: BrowserIdentity = field(repr=False)
    webview_guids: tuple[str, ...] = field(repr=False)

    def redacted_receipt(self):
        return {
            "scope": "no-cdp-profile-shutdown-source-only",
            "browser_process_identity": "UNIQUE_SYSMON_ETW_APP_PROFILE",
            "profile_process_lifetimes": "SYSMON_ETW_DESCENDANTS_EXITED",
            "webview_process_count": len(self.webview_guids),
            "profile_isolation": "NOT_EVALUATED",
            "native_N12_acceptance": "NOT_EVALUATED",
            "file_event_coverage": "NOT_EVALUATED",
            "network_isolation": "NOT_EVALUATED",
        }


def verify_profile_shutdown(*, processes, roles, app_guid, expected_app_image,
                            expected_app_sha256, disposable_profile, launch, ready,
                            close, profile_exit, capture_end, app_handle_witness,
                            etw_lifetimes, capture_loss_reviewed, capture_issues):
    """Independent descendant exit checks after the ordinary OS close.

    The caller must provide a *complete, loss-reviewed* Sysmon/ETW capture.
    Synthetic fixtures cannot certify native WebView2 shutdown. The historical
    substring-only profile-active count is not a sufficient witness.
    """
    from qa.p4_native.n12_exit_corroboration import SOURCE_COVERAGE_ISSUES

    trace.require(capture_loss_reviewed is True and type(capture_issues) is set
                  and not (capture_issues & SOURCE_COVERAGE_ISSUES),
                  "no-cdp-profile-process-coverage-unverified")
    trace.require(close < profile_exit < capture_end,
                  "no-cdp-profile-exit-stage-unverified")
    trace.require(type(processes) is dict and type(roles) is dict
                  and all(key == p.guid for key, p in processes.items()),
                  "no-cdp-profile-process-map-unverified")
    browser = resolve_browser_identity(
        processes=processes, roles=roles, app_guid=app_guid,
        expected_app_image=expected_app_image,
        expected_app_sha256=expected_app_sha256,
        disposable_profile=disposable_profile, launch=launch, ready=ready,
        close=close, capture_end=capture_end,
        app_handle_witness=app_handle_witness, etw_lifetimes=etw_lifetimes,
    )
    profile = trace.windows_path(disposable_profile)
    scoped_webviews = []
    for p in processes.values():
        if ntpath.basename(p.image) != _WEBVIEW:
            continue
        explicit_profile = bool(_PROFILE_TOKEN.search(p.command))
        if explicit_profile:
            supplied_profile = _profile_from_command(p.command)
            trace.require(supplied_profile != profile or p.guid == browser.guid
                          or _descends_from(p, browser.guid, processes),
                          "no-cdp-profile-external-contender")
        if _descends_from(p, app_guid, processes):
            trace.require(p.guid == browser.guid
                          or _descends_from(p, browser.guid, processes),
                          "no-cdp-profile-webview-unbound-parent")
            trace.require(roles.get(p.guid) in ("webview", "webview-network"),
                          "no-cdp-profile-webview-role-unverified")
            trace.require(not explicit_profile or supplied_profile == profile,
                          "no-cdp-profile-child-profile-mismatch")
            scoped_webviews.append(p)
    trace.require(sum(p.guid == browser.guid for p in scoped_webviews) == 1,
                  "no-cdp-profile-browser-unverified")
    verified = {app_guid: etw_lifetimes.find(
        processes[app_guid], handle_witness=app_handle_witness)}
    for p in sorted(scoped_webviews, key=lambda process: process.guid):
        born, stopped = etw_lifetimes.find(p)
        trace.require(p.end is not None
                      and launch <= p.start <= p.end <= profile_exit
                      and trace.utc_ticks(launch) <= born.creation
                      <= stopped.exit <= trace.utc_ticks(profile_exit),
                      "no-cdp-profile-descendant-exit-unverified")
        parent = processes.get(p.parent)
        trace.require(parent is not None
                      and ((p.parent == app_guid) if p.guid == browser.guid
                           else (p.parent == browser.guid
                                 or _descends_from(parent, browser.guid, processes))),
                      "no-cdp-profile-parent-unverified")
        if parent.guid not in verified:
            verified[parent.guid] = etw_lifetimes.find(parent)
        parent_birth, parent_stop = verified[parent.guid]
        trace.require(etw_lifetimes.parent_sequence_comparison(p, parent)
                      == "etw-parent-sequence-agrees"
                      and born.parent == parent_birth.pid
                      and born.parent_sequence == parent_birth.sequence
                      and parent_birth.creation <= born.creation <= parent_stop.exit,
                      "no-cdp-profile-etw-parent-or-lifetime-unverified")
        verified[p.guid] = (born, stopped)
    return ProfileShutdownWitness(browser, tuple(sorted(p.guid for p in scoped_webviews)))
