"""Guarded no-CDP native QA *lifecycle*, not an N12 file/network pass.

The disabled native workflow does not invoke this path. An authorized caller
must supply source-verified staged QA binary, complete collector context, and
the original Windows process-handle witnesses. Browser identity is evaluated
after close by independent Sysmon/ETW, not by CDP or this module.
"""
from pathlib import Path

from qa.p4_native import n12_trace as trace
from qa.p4_research import n12_app_journey as journey
from qa.p4_research import n12_no_cdp_lifecycle as lifecycle


def no_cdp_environments(base, profile):
    """Construct isolated Vite and app settings without a debugger or netlog."""
    trace.require(type(base) is dict and isinstance(profile, Path)
                  and profile.is_dir() and not profile.is_symlink()
                  and (profile / journey.APP_TEMP_DIR).is_dir()
                  and not (profile / journey.APP_TEMP_DIR).is_symlink(),
                  "no-cdp-disposable-profile-unverified")
    trace.require(base.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == lifecycle.NATIVE_ACK_CONSENT,
                  "no-cdp-opt-in-consent-missing")
    vite_env = {**base, "VITE_PILOTODIN_N12_NO_CDP": "1"}
    app_env = {
        **journey.temporary_environment(base, profile / journey.APP_TEMP_DIR),
        "WEBVIEW2_USER_DATA_FOLDER": str(profile),
    }
    lifecycle.verify_opt_in_environment(
        vite_env=vite_env, app_env=app_env, expected_profile=profile,
    )
    return vite_env, app_env


def run_one_no_cdp_app(*, stack, manifest, root, binary, title,
                       source, expected_hash, app_env, profile):
    """Actual guarded launch seam; no native caller in current workflows.

    The app is never spawned before caller-supplied consent and profile
    validation. This function uses the existing close helper, never kills a
    process as a successful close, and never queries the debugger port.
    """
    from qa.p4_native.n12_lifetime_control import process_images, process_times

    trace.require(app_env.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == lifecycle.NATIVE_ACK_CONSENT
                  and app_env.get("WEBVIEW2_USER_DATA_FOLDER") == str(profile)
                  and not app_env.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS")
                  and type(source) is str and type(expected_hash) is str,
                  "no-cdp-app-launch-scope-unverified")
    observer = lifecycle.NoCdpLifecycleObserver(
        stack=stack, expected_source=source, actual_source=source,
        expected_executable_sha256=expected_hash, actual_executable_sha256=expected_hash,
        expected_image=str(binary), expected_title=title,
    )
    journey.mark(manifest, "launch")
    app = journey.spawn(stack, manifest, "app", [binary], app_env, binary.parent,
                        root / "app.log", prelaunch_log_hook=observer.prelaunch_hook)
    observer.bind_process(app)
    provisional = observer.observe_readiness(timeout_seconds=40,
                                             window_timeout_seconds=15)
    trace.require(provisional["native_N12_acceptance"] == "NOT_EVALUATED",
                  "no-cdp-provisional-verdict-invalid")
    journey.mark(manifest, "ready")
    # A path-substring profile count is *only a diagnostic*, never identity.
    profile_before = int(journey.powershell(
        journey.HELPER, "profile-active", "-ProfilePath", profile, timeout=10,
    ))
    trace.require(profile_before > 0, "no-cdp-profile-before-close-missing")
    observer.prepare_normal_close()
    images = process_images(app)
    journey.mark(manifest, "close")
    journey.request_graceful_close(app, binary, title)
    trace.require(app.wait(timeout=5) == 0, "no-cdp-app-did-not-exit-normally")
    journey.wait_for(lambda: int(journey.powershell(
        journey.HELPER, "profile-active", "-ProfilePath", profile, timeout=10,
    )) == 0, 25, "no-cdp-profile-did-not-exit")
    journey.mark(manifest, "profile-exit")
    receipt = observer.verify_after_close(
        close_request_verified=True, profile_processes_before=profile_before,
        profile_processes_after=0,
    )
    trace.require(receipt["native_N12_acceptance"] == "NOT_EVALUATED"
                  and receipt["profile_process_identity"] == "NOT_EVALUATED",
                  "no-cdp-source-receipt-invalid")
    times = process_times(app) | images
    journey.report_file(root / "no-cdp-source-witness.json", receipt)
    journey.report_file(root / "no-cdp-private-stage.json", {
        "source_sha": source, "executable_sha256": expected_hash,
        "markers": manifest["markers"],
    })
    journey.report_file(root / "private-app-handle.json", times)
    return times
