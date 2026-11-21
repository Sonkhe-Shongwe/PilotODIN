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
from qa.p4_research import n12_no_cdp_child_handles as child_handles
from qa.p4_research import n12_private_child_pipe as child_pipe


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
                       source, expected_hash, app_env, profile, transport_env=None):
    """Actual guarded launch seam; no native caller in current workflows.

    The app is never spawned before caller-supplied consent and profile
    validation. This function uses the existing close helper, never kills a
    process as a successful close, and never queries the debugger port.
    """
    from qa.p4_native.n12_lifetime_control import process_images, process_times

    # Recheck the *launch* boundary independently of the environment builder.
    # A later caller must not bypass the disposable profile, owned scratch, or
    # browser-override prohibition by calling this seam directly.
    trace.require(type(app_env) is dict and isinstance(root, Path)
                  and isinstance(profile, Path) and profile.parent == root
                  and profile.is_dir() and not profile.is_symlink()
                  and (profile / journey.APP_TEMP_DIR).is_dir()
                  and not (profile / journey.APP_TEMP_DIR).is_symlink()
                  and all(type(key) is str for key in app_env)
                  and app_env.get("PILOTODIN_N12_NO_CDP_STORAGE_CONSENT")
                  == lifecycle.NATIVE_ACK_CONSENT
                  and app_env.get("WEBVIEW2_USER_DATA_FOLDER") == str(profile)
                  and all(app_env.get(key) == str(profile / journey.APP_TEMP_DIR)
                          for key in ("TEMP", "TMP", "TMPDIR"))
                  and not any(key.upper().startswith("WEBVIEW2_")
                              and key != "WEBVIEW2_USER_DATA_FOLDER" and value
                              for key, value in app_env.items())
                  and type(source) is str and type(expected_hash) is str,
                  "no-cdp-app-launch-scope-unverified")
    # Optional, independently source/runner/consent guarded. There is no
    # native workflow enabling this branch; check before app creation.
    # Only the Python worker sees the authenticated pipe key. The QA app,
    # backend and Vite must not inherit it.
    transport_env = {} if transport_env is None else transport_env
    trace.require(not any(key in app_env for key in (
                      child_pipe.PIPE_ENV, child_pipe.KEY_ENV,
                      "PILOTODIN_N12_CHILD_HANDLE_CONSENT")),
                  "no-cdp-child-pipe-secret-must-not-reach-app")
    use_child_handles = child_pipe.requested(transport_env)
    if use_child_handles:
        child_pipe.require_worker_scope(transport_env, source, expected_hash)
    observer = lifecycle.NoCdpLifecycleObserver(
        stack=stack, expected_source=source, actual_source=source,
        expected_executable_sha256=expected_hash, actual_executable_sha256=expected_hash,
        expected_image=str(binary), expected_title=title,
    )
    journey.mark(manifest, "launch")
    app = journey.spawn(stack, manifest, "app", [binary], app_env, binary.parent,
                        root / "app.log", prelaunch_log_hook=observer.prelaunch_hook)
    observer.bind_process(app)
    child_observer = None
    if use_child_handles:
        from datetime import datetime, timezone
        child_observer = child_handles.ScopedQaChildHandleObserver(
            root_process=app, expected_app_image=str(binary))
        child_observer.start_live(profile=profile, env=transport_env)
        sampling_started_ticks = trace.utc_ticks(datetime.now(timezone.utc))
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
    if child_observer is not None:
        from datetime import datetime, timezone
        retained = child_observer.finish()
        sampling_finished_ticks = trace.utc_ticks(datetime.now(timezone.utc))
        private_evidence = child_handles.PrivateChildHandleEvidence(
            source_sha=source, executable_sha256=expected_hash,
            root_birth_ticks=child_observer._root_birth,
            sampling_started_ticks=sampling_started_ticks,
            sampling_finished_ticks=sampling_finished_ticks,
            witnesses=retained,
            collector_receipt=child_observer.redacted_receipt())
        # Raw GUID/PID/full image/times transfer only via authenticated
        # in-memory Windows pipe; neither logger nor JSON file sees them.
        child_pipe.send_from_worker(transport_env, private_evidence)
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
