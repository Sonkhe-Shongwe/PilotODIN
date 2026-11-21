# PilotODIN P4 | No-CDP lifecycle source observer, no native activation

**21 November 2026. Source-only implementation and exact-source routine fixture CI PASS.** This record does not authorize or prove any PilotODIN native execution, owner-device action, native acceptance, installer, permission, firewall or original-data access.

## Why this small integration exists

The previously separate components each reject invalid observations but did not guarantee their *order*: [prelaunch held-open log identity](./P4_N12_NO_CDP_LOG_WITNESS_2026-11-21.md), [unique live main-window identity](./P4_N12_NO_CDP_MAIN_WINDOW_IDENTITY_2026-11-21.md), and [Sysmon/ETW browser identity](./P4_N12_NO_CDP_BROWSER_IDENTITY_2026-11-21.md). The next native diagnostic must not assume the CDP port, or treat a fixed app-log marker, a PID or an arbitrary window as permission to close.

## Source change and the actual contract

[Implementation `c3407df`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c3407dff358afc58ba43a382c475472589e90176) adds `qa/p4_research/n12_no_cdp_lifecycle.py`, fixed generated-fixture tests `tests/test_p4_n12_no_cdp_lifecycle.py`, and routine CI selection. [Corrected code `3afdaad`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3afdaade7b430738f19ba505659a7076517f6a8d) provides the synthetic process's expected cleanup method, preserving the existing fail-safe process cleanup callback. The earlier CI run was cancelled on the superseded SHA, not promoted as a passing result.

The **observer does not start or close a process**. A later separately authorised caller must explicitly own those operations, the exact executable hash, the existing normal `CloseMainWindow` helper and independent capture completeness.

1. `verify_opt_in_environment` requires the existing explicit Vite no-CDP switch, Rust-side separate consent value, exact disposable WebView2 data-folder path and **no other nonempty WebView2 environment overrides**. This is a source validator, not an environment setter or permission grant. No current native workflow calls it or supplies a newly approved capture.
2. `prelaunch_hook` integrates with the existing optional `journey.spawn(..., prelaunch_log_hook=...)`. It keeps a fresh `app.log` read handle alive in the caller's `ExitStack`, checks source/executable digests and prevents stale logs.
3. `bind_process` accepts only a live positive PID bound to the **retained original handle's creation time**. The production default reader is `n12_lifetime_control.process_times(..., allow_running=True)`; fixture tests supply a labelled fake.
4. `observe_readiness` requires a unique main-window identity bound to that birth and exact executable/title, **then** the bounded exact one-time log marker. It grants only a provisional `NOT_EVALUATED` receipt, not a close action. There is no CDP port or browser PID lookup.
5. `prepare_normal_close` rechecks exactly the same window, handle birth and PID before the caller can separately invoke the reviewed Windows normal-close helper. This class cannot call `CloseMainWindow` or bypass the Rust close veto.
6. `verify_after_close` requires the caller's separately verified close action, the same process with exit code **0**, no duplicate postclose marker and diagnostic WebView profile-path process counts **positive before, zero after**. These counts are substring matches from the existing `profile-active` helper, so **do not prove uniquely identified browser exit, loss-free capture or absent disk writes**. `profile_process_identity`, browser identity, file coverage, network and native acceptance explicitly remain **NOT_EVALUATED**. The source observer cannot be used to award an N12 point.

All private process, handle, window, path and raw app-log values remain internal. A failed gate prevents a positive receipt; the external native process/collector flow is still disabled.

## Exact-source verification

[Routine P4 run #44876093837](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44876093837) completed **4 of 4 jobs SUCCESS** at corrected code `3afdaad`:

- **861 Python tests passed, 6 skipped, 331 subtests passed, 1 warning** in the source/backend suite. The new generated lifecycle test file contains **13 tests** and checks true ordering, exact provenance, prelaunch refusal, absent readiness, bad/changed main window, erroneous close, early/nonzero process exit, duplicate log, incomplete profile count diagnostic, and held-handle cleanup.
- **104 Node/frontend source contracts passed** and TypeScript/Vite build completed.
- **13 disposable real-HTTP Chromium browser cases passed**, without a native PilotODIN WebView2 process.
- Windows synthetic source/file/ETW/control jobs completed and the R03 Windows API fixture passed **4 checks**. No actual Windows `observe_main_window` call, native Rust compilation, or new N12 capture occurred.

The superseded first commit `c3407df` started [run #44876055346](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44876055346), which was **cancelled** after the fixture correction; it is not a qualifying CI pass.

## Next actionable source checkpoint

A future **explicitly approved one-use** QA launcher must adopt this observer around the real source-pinned app launch and normal-close helper. The bounded and unambiguous *startup window wait* is now implemented and [source/fixture verified](./P4_N12_NO_CDP_BOUNDED_WINDOW_WAIT_2026-11-21.md), but a future real runner still needs a source-pinned no-debug WebView2 runtime profile, independently verified WebView2 browser **lifetime and profile identity** after exit instead of the path-substring count, and full ETW/FileIO/network coverage. The existing one-use native workflows remain disarmed, and existing `n12_app_lifetime.launch_and_close` still uses CDP and port 9331; do not claim they have been replaced by this source-only observer.

**Ledger remains:** P4 **14/20 (70%)**; file mutation **3/4 (75%)**; desktop network **2/3 (67%)**; N12 **0/2 (0%)**; physical offline inference **1/3 (33%)**; original-data preservation **0/2 (0%)**. Governing native N12: filesystem **FAIL**, network **FAIL**, mutation coverage **BLOCKED**.
