# PilotODIN P4 | Product worker temporary-file containment

21 November 2026. Product Rust source and N12 QA parity correction. Source-level verification only, not a completed native filesystem or R02.5 acceptance check.

## Specific code defect and change

Before this change, the bundled analytics backend used its own app-local data working directory, but inherited Windows TEMP/TMP/TMPDIR from the desktop process. The bundled local AI inference worker retained a resource DLL working directory for CPU backend discovery and likewise inherited the host temporary-file locations. Either child could use the host's temporary storage through a library, even with the backend working directory already corrected.

[Product source 7ea17db](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7ea17dba3449b21630632a81d0be291e6b0c72ea) adds a shared app-local data-home resolver and a fail-closed worker-temp directory helper in frontend/src-tauri/src/lib.rs. The analytics backend is now launched with TEMP, TMP and TMPDIR all pointing to its existing application data home / backend-temp. The local AI inference worker uses a separate inference-temp inside its existing app data home. The inference runtime DLL working directory and PATH remain unchanged. R03 baseline and candidate data partitioning is preserved.

The helper rejects unexpected folder names and canonical paths that escape the chosen data home, including junction/symlink escapes. It does not change the global environment, WebView2 profile path, original app data directory, production Tauri window configuration, firewall, permissions or allowed file mutation destinations. Worker temp subdirectories are created at worker launch time, not during startup of an unrelated feature.

[QA parity source 9993087](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/99930879f3079a8c65beff88ad84278550c733b2) makes the independently launched N12 QA backend use an already-created backend-temp inside its existing, permitted disposable QA home. It refuses absent or symlinked scratch paths. The host source checkout remains import-only and is not a permitted write location. A Python synthetic real-process smoke demonstrates the existing CWD fix separately. This QA change matters because N12 launches a standalone test backend rather than the production Rust sidecar.

## Evidence and test history

The first version of the expanded QA fixture failed at a missing Python Path import, not at the containment code. [Corrected source cfc738b](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cfc738b967ce0192fcc715ab80bcb3a8a3ca25a0) adds that import without weakening any policy.

[Exact source P4 CI #44881225948](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44881225948) completed 4/4 jobs SUCCESS. Results: 909 Python tests passed, 6 skipped, 357 subtests passed, one warning; 104 frontend Node tests passed and the TypeScript/Vite build passed; Windows synthetic ETW/FileIO and preservation fixtures passed; 13 disposable real-HTTP Chromium browser cases passed; four R03 Windows checks passed. The separate P2 Report Export Draft Safety workflow triggered by the first Rust source commit also completed successfully.

The Rust product change is source-reviewed with a new Python static contract and Rust unit tests committed for future compilation. Neither the normal P4 CI nor this task compiled or launched the native Rust/Tauri executable, collected fresh real WebView2 FileIO events, or tested Windows worker temp inheritance in an actual app launch. Passing source/fixture tests is NOT a native acceptance result.

## What remains genuinely open

The historical approved native [N12 #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) still governs: filesystem FAIL, network FAIL, file mutation coverage BLOCKED. Its single backend source checkout write occurred before the previous working-directory correction, and the saved report does not establish that TEMP inheritance caused it.

The actual known WebView2 ambient write failures have not been fixed by this backend/inference change: eight out-of-scope creates, four overwrites, four writes, 23 unsupported WebView operations, plus 113 corroborated out-of-scope WebView-network write candidates. The request-time comparison also left 15 unknown WebView-network write paths, 4,112 background write path gaps and 42 missing background process lifetimes. These still require evidence-led product correction and complete loss-reviewed ETW/FileIO attribution.

Next: do not invent a WebView2 fix without an actual identified mechanism. On a fresh, separately approved, one-use, source-pinned disposable native run, verify WebView2 and worker actual process environments, file destinations, and the same strict protected root and capture requirements. Native workflows remain disarmed. No installer, original user data or live firewall was touched.

Engineering before/after: file mutation 3/4 (75%) -> 3/4 (75%); network 2/3, N12 0/2, firewall 2/3, physical offline inference 1/3, original preservation 0/2, product fixes 7/7, QA dialog driver 3/3, overall P4 14/20 (70%) -> 14/20 (70%). No native R02.5 credit earned.
