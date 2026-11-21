# P4 R02.5 | No-CDP ambient-local WebView2 differential gate

**21 November 2026 | Source implementation and generated checks, NOT native WebView2 file containment.**

## Why this exact change

Historical approved full native N12 [run #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains **filesystem FAIL, network FAIL, FileIO BLOCKED**. The actual [debug-only WebView2 diagnostic #44852642468](../qa/p4_research/N12_WEBVIEW_DEBUG_ONLY_RESULT_44852642468.md) positively observed **two browser CreateFile operations on temporary files in ambient user-temp**, even without netlog, during CDP readiness. Its Process Monitor shutdown exited nonzero, loss was not independently reviewed, browser effective TEMP assignments were not captured, and exact original file-object identity is unknown. It does NOT prove inherited LOCALAPPDATA/APPDATA causes those writes or that normal no-CDP production behaves the same.

The separately tested QA ambient-local candidate was previously wired to a launch **with remote debugging**. The no-CDP launch already declared its own disposable WEBVIEW2_USER_DATA_FOLDER and app TEMP/TMP/TMPDIR but had no optional local/roaming redirection. Therefore we lacked a debugger-free path for distinguishing inherited ambient user-local storage from a verified profile while preserving the same strict filesystem scope.

## Exact source correction

[Source commit d31f8fa](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d31f8fac343f9cd11083785982d02b552aed712f):

1. The pre-existing opt-in ambient-local fixture now recognizes exactly the owned disposable N12 journey or lifetime roots with numeric build identifiers under verified RUNNER_TEMP. It still rejects unprepared paths, symlinks, target collisions and outside-runner directories. Both QA-only local and roaming children remain **inside the already permitted WebView profile**.
2. The existing no-CDP environment builder keeps the **baseline unchanged**. Only explicit PILOTODIN_N12_QA_AMBIENT_LOCAL_VARIANT=ISOLATED_QA_ROOTS applies the separately vetted LOCALAPPDATA/APPDATA redirection to the **app process**. The Vite and backend environment, WEBVIEW2_USER_DATA_FOLDER, TEMP/TMP/TMPDIR, launch identity and debugging/netlog ban remain unchanged.
3. A final pre-spawn guard recomputes the opt-in destinations and rejects missing or altered targets. In baseline mode, it rejects unapproved QA redirect residue. Unknown variant values fail closed. No app was launched by tests.
4. The source-integrity guard and adversarial unit tests were updated to require the opt-in to remain default-off and source-scoped, and to challenge wrong directories, unprepared and misnamed roots, stale redirects and no-CDP debugger contamination.

**Not a production product fix:** Production Tauri configuration and Rust startup were not changed. There was no changed writable allowlist, owner-data root, Windows ACL/token, runtime browser flag, firewall or installer. Redirecting environment variables by itself is not a Windows containment boundary or proof that actual WebView2 children honor them.

## Exact-source CI

[CI #44919033565](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44919033565) at source d31f8fac343f9cd11083785982d02b552aed712f completed **4/4 SUCCESS**: 1,012 Python passed, 6 skipped, 493 subtests; 104 frontend Node tests and Vite build; disposable browser and hosted-Windows synthetic ETW/FileIO/R03 checks passed. None of these ran the real Tauri/WebView2 application or measured its actual writes.

## Mandatory evidence gap before native authorization

The present no-CDP app-lifetime path uses a **Kernel-Process ETW lifecycle session**, not the full N12 **Kernel-File/FileIO mutation collection and strict reducer**. An apparently successful no-CDP app lifetime could not therefore establish that its WebView2 writes moved, were prohibited, or were entirely observed. The last 25% does not close from this patch.

**Next source-only engineering task, not more generic tests:** integrate the EXISTING complete FileIO collector, process/handle witness, loss counters and strict mutation reducer with this guarded no-CDP startup/readiness/graceful-close path. Preserve source/executable digests, independent effective WebView user-data location, per-actor immutable protected and permitted roots, positive transient write/restore control, unsuppressed named-pipe and unsupported-operation categories, and all positive prohibited operations. No ProcMon-only negative oracle, guessed original paths, relaxed permission policy or loss flag bypass.

Any actual Tauri/WebView2 native execution or variant comparison needs **fresh, explicit, source-pinned, one-use owner approval**. The existing native full-app workflow remains disabled and past approvals consumed. For an A/B causal inference, both baseline and candidate must be run under independently authorized, otherwise comparable source/runtime/stage/capture conditions, not compared against old debug-only evidence with loss unreviewed. No owner's original files, physical machine or installer should be touched.

## Current score, unchanged

Internal file-mutation engineering **3/4 (75%) before and after**; official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**. Historical 113 outside-scope WebView-network write path credits, 15 remaining network-writer path gaps, 4,112 background-write path gaps, 42 missing background process lifetimes and 23 unsupported WebView operations remain OPEN. Overall historical full N12 filesystem FAIL and FileIO BLOCKED.
