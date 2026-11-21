# PilotODIN P4 | N12 QA-only ambient-local storage candidate

**21 November 2026. Source-only preparation and fixture verification. No native filesystem or R02.5 acceptance.**

## Why this is a testable, not confirmed, fix

The last approved complete [N12 journey #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains filesystem **FAIL**, network **FAIL**, file-mutation coverage **BLOCKED**. It recorded eight outside-scope WebView creates, four overwrites, four writes, 23 unsupported operations and a backend checkout write. The same-capture file-credit comparison corroborated **226,959 permitted** and **113 outside-scope** WebView-network writes, leaving **15** network-write path gaps; other unknown mutations and the 42 missing process-lifetime records remained.

QA n12_app_journey.py already redirects TEMP, TMP, TMPDIR and WEBVIEW2_USER_DATA_FOLDER into a disposable WebView profile, but the app launch inherits the runner's LOCALAPPDATA and APPDATA. One narrow hypothesis is that some ambient WebView2 writes follow those inherited user-local directories. The candidate redirects only these two variables for the QA desktop app into subfolders of the **already permitted** disposable WebView profile. Actual browser startup may use Windows Known Folder APIs or runtime policy instead; no native process proof exists. Official [WebView2 environment documentation](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/webview2-idl) and [Tauri v2 storage configuration](https://v2.tauri.app/reference/config/) describe available mechanisms but do not prove the original files' identity.

## Scope of the source change

[Initial source 7f9bdf3](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7f9bdf3fcff804b3423d7a9ed9d989a94b32666c) and [final tested c667232](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c667232fc3419cf3b72cc19ec3d547eff38abdba) add qa/p4_research/n12_ambient_local_candidate.py, link it to the existing N12 QA journey, and add focused cases.

- The baseline is unchanged unless PILOTODIN_N12_QA_AMBIENT_LOCAL_VARIANT=ISOLATED_QA_ROOTS is explicitly selected. Invalid modes are rejected. This flag **does not authorise native execution**.
- Two new folders, ambient-local and ambient-roaming, are created only under the already prepared, unique runner-temp N12 WebView profile. Existing paths, symlinks, reused or unexpected profiles, bad runner confinement and incompatible temp variables stop the candidate.
- Only the QA desktop app launch receives redirected LOCALAPPDATA and APPDATA. The separately launched QA test server and driver receive the original environment. A backend sidecar that is spawned later by the desktop app **may inherit** the changed desktop environment; this requires native verification. WEBVIEW2_USER_DATA_FOLDER, TEMP, TMP, TMPDIR, browser flags and ports remain unchanged.
- No protected root or permitted write path changes. No changes to production Tauri/Rust, filesystem reducers, network allowlists, firewall, permissions, installer or original owner files. Public receipts explicitly retain browser/runtime inheritance and native containment as NOT_VERIFIED.
- Source-only tests create disposable synthetic paths, not a real PilotODIN/WebView2 process or native FileIO collector.

## Failure and CI record

First automatic CI on initial source called pytest in the minimal Windows synthetic job, which lacked that dependency. Changing only the new tests to the existing unittest runner exposed three mistaken fixture expectations: app_environment correctly normalises incoming TEMP/TMP/TMPDIR before the direct candidate guard receives them. The final test correction checks unsafe values directly at the guard and checks source-level normalisation separately. Production and strict filesystem rules were not weakened. Superseded runs [#44879885609](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44879885609) and [#44879958246](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44879958246) were cancelled and are not counted as passes.

[Exact-source routine P4 CI #44880039668](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44880039668), source c667232, **COMPLETED 4/4 SUCCESS**: **902 Python passed, 6 skipped, 357 subtests passed, one warning**, **104 frontend tests passed** and Vite build, **12 Windows candidate source fixtures passed**, Windows ETW/FileIO generated checks passed, **13 disposable real-HTTP Chromium tests**, **4 Windows R03 checks**.

## Remaining acceptance requirements

No actual WebView2 ambient write was redirected or prevented in this CI. The existing native workflow remains disarmed and the prior N12 source-pinned one-use approvals have been consumed. A separately authorised native experiment is required to establish which process wrote the user-local files, what environment it used, whether the candidate changes destinations, and whether any known prohibited writes remain. The original strict FileIO/Sysmon/ETW loss, path and identity gates, protected snapshots and positive transient write control must stay in force. ProcMon coverage cannot be claimed merely from a readable export.

**Official status unchanged:** P4 **14/20 (70%)**, file mutation **3/4 (75%)**, N12 **0/2**, desktop network **2/3**, firewall preflight **2/3**, physical offline inference **1/3**, original-data preservation **0/2**. No acceptance credit earned.
