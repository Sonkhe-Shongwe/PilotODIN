# PilotODIN R02.5 | Focused storage backend-temp parity and WebView2 causal limit

21 November 2026. Source-only code correction and reopened actual native evidence. **No native capture or R02.5 acceptance.**

## Original evidence, not assumptions

The last approved full N12 native Windows audit, [run 44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004), remains **filesystem FAIL, network FAIL and mutation coverage BLOCKED**. It recorded eight out-of-scope WebView creates, four overwrites, four writes, 23 unsupported WebView operations, one backend checkout write and four non-loopback browser network events. Its same-capture diagnostic credited 226,959 permitted and **113 outside-scope** WebView-network writes, leaving 15 of the original 227,087 WebView-network path gaps. Background FileIO still had 4,112 unresolved write paths and 42 missing process lifetimes. Protected endpoint hashes matched, but this cannot exclude write-and-restore.

The later one-use [debug-only focused WebView native run 44852642468](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852642468) observed **two browser .tmp CreateFile events in user-temp**, both at readiness, even when netlog was absent. Remote debugging was still on. The browser's actual TEMP/TMP/UDF settings, private exact target names and complete ProcMon loss review were not established; ProcMon exited nonzero. Therefore **netlog is not a necessary cause**, but there is **no evidence that normal non-CDP WebView2 behaves the same way**.

Tauri production startup uses the default app-local WebView data directory, and does not explicitly enable QA browser debug/netlog switches. Microsoft [WebView2 UDF guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/user-data-folder) does not guarantee that all runtime temporary files go to the UDF; [WebView2 environment/override rules](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/webview2-idl) allow startup overrides. A speculative production folder change, debugger flag, relaxed write policy, broad ACL rule or inferred crashpad cause is not justified by the existing redacted records.

## Concrete source inconsistency corrected

The full N12 journey and Rust product backend already use a dedicated owned backend-temp directory. The **separate focused storage diagnostic** still called the helper without the data-home argument, causing its QA backend to inherit host TEMP/TMP/TMPDIR. That could introduce unrelated backend writes into a browser-focused experiment, obscuring provenance.

[Code cf80e32](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cf80e327e051dfb5ffe306b896ae3bd143d69ce0) updates the focused launch in n12_app_lifetime.py to use the existing full-journey contained backend environment. The pre-existing prepare_journey function creates the dedicated backend-temp; it must exist and not be symlinked. Tests now reject missing data home, missing scratch and synthetic symlink, and verify host-temp variables are not inherited while PYTHONPATH and CWD remain correct. No new directory permission, scope exception, product config or acceptance change.

[Exact-source routine P4 CI #44883892689](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44883892689) **4/4 SUCCESS** at cf80e32: **910 Python passed, 6 skipped, 357 subtests passed, one warning**, **104 Node/frontend passed** and Vite built, **13 real-HTTP disposable browser checks**, Windows synthetic ETW/FileIO controls and **four R03 Windows tests** passed. No Rust native compilation or real WebView2 app launch in this run.

## Next falsifiable engineering decision

The source-only no-CDP log, unique-window, browser-identity and profile-shutdown witnesses already exist but are **not wired** to a working native WebView2 storage launcher/reducer. The current focused diagnostic needs CDP to obtain a browser PID and readiness. A meaningful next *engineering* change, rather than another synthetic observer, is to integrate the existing witnesses into a **fail-closed production-parity no-CDP QA launch** with independent Sysmon/ETW loss review, normal native close and exact browser/UDF identity. That is **not a product fix** and cannot earn native acceptance until actually measured.

The discriminating native question is whether **browser user-temp creates persist when both remote debugging and netlog are absent**, with full FileIO/path/actor coverage. If they persist, isolate a specific browser runtime/Windows write mechanism before changing production. If not, investigate QA instrumentation contamination. An invalid or incomplete capture remains BLOCKED in either case. Exact private paths were not retained in earlier public artifacts; they cannot be recovered by guessing. Existing N12 and focused workflows remain disarmed, and any native build, capture, ACL/firewall change, installer or original-data inspection requires fresh explicit one-use approval.

**Official progress unchanged:** P4 14/20 (70%), file mutation 3/4 (75%), desktop network 2/3, N12 0/2, original preservation 0/2. No R02.5 point.
