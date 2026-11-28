# PilotODIN P4 | No-CDP WebView2 profile shutdown corroboration

**21 November 2026. Source-only preparation, synthetic exact-source CI PASS.** No native PilotODIN app, WebView2 shutdown or filesystem/network acceptance has been independently observed by this change. The owner-approved native N12 baseline remains filesystem FAIL, network FAIL, file-mutation coverage BLOCKED.

## Specific gap

The previously prepared browser verifier corroborated one root msedgewebview2.exe app child, but an individual browser stopping does not prove that its renderer, network or other WebView descendants stopped. The legacy profile-active diagnostic matches a profile-path substring in command lines and can be zero even when a relevant unobserved process exists. That counter cannot become a native acceptance proof by itself.

## Narrow new source contract

The added read-only function verify_profile_shutdown in qa/p4_research/n12_no_cdp_browser_identity.py reuses resolve_browser_identity to require one pinned root browser, exact app executable SHA and retained Windows process-handle witness, exact declared disposable profile, and independent Sysmon GUID / ETW parent-sequence agreement. It adds:

1. Explicitly reviewed source process capture completeness: capture_loss_reviewed must be the literal True, capture_issues must be an inspected set and cannot contain the shared Sysmon/ETW coverage defects (record gap, bookend mismatch, restart/config error, ETW event/buffer loss or no buffers).
2. A separate close < profile_exit < capture_end marker order.
3. Complete GUID-keyed process records for the supplied capture. Every WebView process in the app subtree must belong to the *same* verified browser subtree. A separate WebView explicitly using the same disposable profile blocks.
4. Every related renderer/network child must have a unique Sysmon lifetime and independently corroborated ETW start, stop, full image, parent PID and parent sequence. All observed child exits must be no later than the reviewed profile-exit marker. Missing stops, late exits, impossible ordering, stale/forged ancestry or changed explicit child profile refuse a positive receipt.
5. A private internal ProfileShutdownWitness records the browser and child GUIDs, with a redacted public receipt that says profile_process_lifetimes=SYSMON_ETW_DESCENDANTS_EXITED at *source-contract scope* and explicitly keeps native_N12_acceptance, profile_isolation, file_event_coverage and network_isolation as NOT_EVALUATED.

The implementation does **not** start, kill, close or enumerate a native process, change environment variables, activate a workflow, interpret CDP browser PID, assert Windows profile isolation, or pretend ETW loss-review values have been independently established. The caller must supply authentic source-wide capture and full process map, which the ordinary routine synthetic jobs do not. The current native storage reducer continues relying on cdp_browser_pid and is not wired into this source function. Actual WebView2 command-line/profile conventions are not verified by any new native run; if the root does not publish the expected complete user-data-dir argument, the existing strict check still blocks rather than guessing.

## Exact-source tests, failure analysis and correction

- Implementation [b36ed32](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b36ed3288a33405e57bbc42dfebc0d7a92718fd8) added the source checks and generated cases to the already selected test file. Its first [routine run #44878295549](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44878295549) exposed two **negative fixture expectation errors**: app-parented renderer with an explicit shared profile was correctly refused as a profile contender before the ancestry decision; appending a second profile switch was correctly refused as ambiguous before the mismatched-profile decision. These expected reasons were not changes in product/runtime behaviour.
- Corrected generated test fixtures at [10287c9](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/10287c97a903fb0ddac3c49df6c1b8e6849f93b5) keep all real source gates intact and isolate the intended conditions. [Exact-source P4 routine CI #44878358373](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44878358373) completed **4/4 jobs SUCCESS** on that SHA.
- Linux/source: **882 Python tests passed, 6 skipped, 346 subtests passed, 1 warning**, **104 Node/frontend tests passed**, TypeScript/Vite build PASS.
- Windows hosted synthetic: **22 source-only browser/profile tests passed**, together with the existing Windows ETW/FileIO/window/close fixture suite. Disposable real-HTTP Chromium **13 passed**. R03 hosted synthetic **4 passed**.
- New negative cases cover missing ETW child stop, child surviving profile-exit, mismatched child parent sequence, wrong ancestry, missing roles/forged GUID-map keys, wrong explicit child profile, external same-profile contender, missing capture review, known Sysmon/ETW losses and false profile-exit stage. An unrelated other-profile WebView remains excluded.

## Current limitations and next acceptance-relevant action

A fake ETW validator and a caller-supplied capture-loss Boolean are insufficient to prove a real no-CDP WebView2 lifetime. The routine test suite did not launch Rust/Tauri, the native WebView2 runtime, profile isolation, or FileIO/network capture. The profile token parser currently expects one complete root --user-data-dir argument; do not weaken it based on speculation. The exact source-only verifier is prepared for a **future separately authorised, one-use, source-pinned native collector**, but should first be incorporated into a protected reducer path that uses actual trusted Sysmon/ETW event-loss accounting and independently checks the complete process map, without treating ProcMon CSV absence as full file-operation coverage.

Native N12 re-execution still requires new one-use owner approval; existing workflows stay disarmed. Product installers frozen, original data untouched, firewall/permission changes unapproved.

**Official progress unchanged:** P4 **14/20 (70%)**; product fixes **7/7 (100%)**, dialog driver **3/3 (100%)**, file-mutation coverage **3/4 (75%)**, desktop network **2/3 (67%)**, firewall preflight **2/3 (67%)**, N12 acceptance **0/2 (0%)**, physical offline inference **1/3 (33%)**, original-data preservation **0/2 (0%)**. No native acceptance point earned.

## Later guarded read-only reducer integration (source-only)

A consent-gated [no-CDP QA lifetime mode](./P4_N12_NO_CDP_NATIVE_LIFECYCLE_INTEGRATION_2026-11-21.md) now calls `verify_profile_shutdown` after loading the existing actual Sysmon process map and digest-checked ETW events from the life-cycle collector. It refuses missing ordered markers, incomplete process identities or reported capture loss. The earlier “must be incorporated” direction above is now addressed **at code scope only**. [Code `51be1e2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/51be1e225dc736f8e003659612c0c93787f3c1fb) passed [P4 CI #44885183619](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44885183619), 4/4 source/synthetic; **no live native ETW, actual browser shutdown or filesystem/network acceptance** was observed. The profile-active string count stays diagnostic, not attribution.
