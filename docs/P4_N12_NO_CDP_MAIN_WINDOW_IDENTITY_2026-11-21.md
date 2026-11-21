# PilotODIN P4 | Native main-window identity without CDP

**21 November 2026.** **Source-only read-only guard with scoped fixture CI PASS.** No native no-CDP PilotODIN runtime, installer, owner-device access, capture, network or FileIO acceptance was executed.

## Requirement and decision-making observation

The existing `n12_app_lifetime.py` requires CDP port 9331 and a CDP readiness driver before the normal Windows `CloseMainWindow` path. A fixed log line without a uniquely verified **main window attached to the live original app process** cannot safely establish readiness or justify a close. The N12 negative and storage gates require no assumed identity.

`qa/p4_research/n12_no_cdp_main_window.py` adds an opt-in, **read-only Windows API observer** and a pure generated-data selector. The observer uses the **retained subprocess handle**, the same Windows process creation timestamp captured at launch, and the executable's **exact DOS path from that handle**, plus a complete top-level `EnumWindows` snapshot. It checks exactly one visible, unowned root window with the expected case-sensitive title and PID. Foreign same-title windows, hidden duplicates, ambiguous/missing matches, wrong executable, changed process lifetime, changed HWND or premature process exit block. A second observation before an independently controlled close must match the first. The private HWND, PID and process birth are not serialized; a positive redacted source receipt always says `native_N12_acceptance=NOT_EVALUATED` with browser, network and FileIO also unassessed.

This module contains **no application startup, close, window creation, permission change or network access**, and no current CI job calls the real Win32 observer. The existing CDP native launcher, close-ticket veto, process-identity close helper and all native workflow disarms remain unchanged. The new function is **not yet integrated** into the no-CDP launch path. It must never be used to grant native acceptance from fixture-only records.

## Focused and broader exact-source verification

Code [`969cb4b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/969cb4beffd866425b8e52188c9de7a075eeb674) added the guard, [11 generated window-selector tests](../tests/test_p4_n12_no_cdp_main_window.py), and CI paths/tests that were missing for the earlier [browser identity module](./P4_N12_NO_CDP_BROWSER_IDENTITY_2026-11-21.md). [P4 Actions run #44874237979](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44874237979) finished **4/4 SUCCESS at exact SHA**.

- Source/backend/frontend job: **848 Python tests passed, 6 skipped, 316 subtests passed, 1 warning**, **104 Node cases passed**, and the TypeScript/Vite build passed.
- Windows synthetic source controls: **11 main-window tests**, **11 browser-identity tests (one Windows-only conditional skip)** and **16 existing log-witness tests** succeeded at fixture scope. The existing Windows FileIO, ETW and window-close controls completed.
- Disposable real-HTTP Chromium: **13 cases passed**. The R03 Windows synthetic analytics/fallback job passed **4 tests**.
- The pure simulated selector can prove it refuses manufactured ambiguity, but **no real Win32 window was enumerated** and no actual no-CDP WebView2 instance was started. The tested GitHub workflow does not compile the changed Rust guard or run a native PilotODIN app.

## Next bounded checkpoint, and stop rules

**Next justified code-only work** is a separate, explicitly opt-in no-CDP driver mode that (1) preserves a prelaunch empty `app.log` descriptor before spawn, (2) obtains the original app handle creation timestamp, (3) calls this read-only unique-main-window observer before using the bounded app-log readiness witness and rechecks the same identity before a **separately verified** normal Windows close, and (4) replaces port 9331 readiness/profile-exit assumptions with independently checked app and profile lifecycle. It must not infer browser PID from title or classify absent ETW/ProcMon paths as safe. Review the mode contract and exact-source tests before seeking **fresh one-use owner approval** for any native execution.

The latest complete approved N12 result remains **filesystem FAIL, network FAIL, file-mutation coverage BLOCKED**. P4 **14/20 (70%)**, file-mutation **3/4 (75%)**, N12 **0/2 (0%)**, desktop network **2/3 (67%)**, physical offline inference **1/3 (33%)** and R06 preservation **0/2 (0%)**. No engineering acceptance points earned.
