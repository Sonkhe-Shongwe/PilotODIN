# P4 R02.5 | No-CDP WebView2 strict Kernel-File bridge and acceptance limit

**21 November 2026 | CODE WIRED AND SOURCE/SYNTHETIC TESTS GREEN. REAL PRODUCT FILE MUTATIONS NOT RECAPTURED.**

This directly continues the [no-CDP ambient LOCALAPPDATA/APPDATA candidate](./P4_N12_NO_CDP_AMBIENT_LOCAL_PRODUCT_WRITE_GATE_2026-11-21.md). Our strict focus is the remaining file-mutation engineering 25%, not expanding the P4 feature backlog.

## What this change actually integrates

[Exact tested source commit 2b9fa97](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2b9fa9744c23c0a8ba1c586fec3ad15d62bf8f68) now adds an **explicit, default-off** \`--no-cdp --fileio\` option to the existing hosted-Windows \`qa/p4_research/n12_app_lifetime.py\` path. Unlike the old lifetime-only ETW collector, this option selects the **already implemented** full N12 Kernel-File + Kernel-Process logman provider configuration, its \`journey.etl\` export and the same verified \`etw-export\` decoder. The established \`qa/p4_native/n12_trace.py::inspect_etw_files\` reducer is called on that same SHA-256-identified JSONL event stream. Nothing was added to the governing strict reducer or its permitted/protected root scope.

1. \`qa/p4_native/n12_lifetime_etw.py::fileio_process_session\` reuses \`journey.start_journey_etw\`, \`etw.stop_trace\` and the existing cleanup path. It does not change the legacy process-only session.
2. Full Kernel-File mode brackets both protected/immutable root snapshots *inside* the capture window. The four boundary markers and child launch/close markers must all be present; the established \`snapshot_capture_evidence\` contract remains required. If the new collector fails, abnormal session cleanup is attempted and the error is primary.
3. The no-CDP controller keeps its guarded startup, independent original app handle/ETW lifetime review and final graceful OS-close path. It uses no CDP debugger or netlog. The app-only ambient-local opt-in from the earlier checkpoint remains default-off and isolated to disposable QA profile children.
4. \`qa/p4_research/n12_no_cdp_fileio_review.py\` calls the **original strict** \`trace.load_capture\`, \`trace.bind_processes\`, \`trace.scope\` and \`trace.inspect_etw_files\`. It includes protected immutable observed fixtures, counts confirmed prohibited operations and missing mutation paths, and reports the WebView-network missing-write count. Public results contain **fixed role/operation labels and numeric counts**, never original owner filenames, PIDs, GUIDs or event payloads.
5. The new \`--fileio\` option requires **both** existing no-CDP/lifetime consents and a NEW \`PILOTODIN_N12_NO_CDP_FILEIO_CONSENT=I_APPROVE_ONE_N12_NO_CDP_FILEIO\`, with source SHA, hosted Windows runner and first-run guards. It refuses \`--fileio\` without \`--no-cdp\` or in a separate worker. **No workflow supplies this new consent or activates a native app run.**
6. This special full FileIO output is **always \`status: BLOCKED\`**, with \`native_N12_acceptance: NOT_EVALUATED\` and \`file_mutation_acceptance: NOT_EVALUATED\`. The top-level CLI exits nonzero in this mode even if its independent lifetime diagnostic succeeds. It cannot manufacture containment credit.

## Why the new source-only bridge is NOT a full N12 PASS

The existing no-CDP journey lacks the full N12 before/after **calibrated process/network/file witnesses**, independently complete original **WebView2 child process handles**, positive transient write-and-restore proof and independently verified effective user-data-folder/ambient configuration. The initial FileIO bridge deliberately **does not add or bypass those acceptance prerequisites**. It performs strict mutation observation and counts, not the complete \`complete_journey_audit\` journey acceptance. A zero counter result would still be \`BLOCKED\` and cannot establish absence of transient or unobserved mutations. The original broader trace may contain WebView2, background and named-pipe gaps which are not exempted, and a source-correct app environment does not prove the browser honored it.

The existing restricted generated writer [cross-provider result #44918036581](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44918036581) is useful measurement calibration but is not the actual product process tree. The original full app [#44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) still has **filesystem FAIL, network FAIL, FileIO coverage BLOCKED**. The 113 outside-scope WebView-network write credits, 15 remaining WebView-network path gaps, 4,112 background write paths, 42 missing background process lifetimes, 23 unsupported WebView operations, plus other incomplete categories remain historical open evidence. **No real original WebView2 process or outside-root filename was newly captured.**

## Source-only testing and failures retained

Initial implementation [059136e](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/059136ebb6968bf30addd2172c8e7b410b7f0bd7) introduced the existing collector to no-CDP. The following two synthetic test revisions exposed **test-harness issues**, not a product FileIO verdict:

- [CI #44921084294](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44921084294): the new heavily mocked branch test exceeded Python's static nesting limit. Replaced its contexts with \`ExitStack\`.
- [CI #44921239211](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44921239211): the test reached a real Windows FILETIME clock on a Linux host; patched the test clock to a deterministic synthetic UTC sequence. No product, acceptance or reducer logic altered in either fix.

**Corrected [exact-source CI #44921405079](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44921405079) at [2b9fa9744c23c0a8ba1c586fec3ad15d62bf8f68](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2b9fa9744c23c0a8ba1c586fec3ad15d62bf8f68): COMPLETED 4/4 SUCCESS**. 1,024 Python tests passed, six skipped, 498 subtests; 104 frontend tests passed and Vite build passed; disposable real-HTTP browser tests, hosted-Windows R03 and generated Windows ETW/FileIO controls passed. Source-only tests explicitly cover consent refusal before creating folders/launching, full collector start/stop and exception cleanup, the exact full-capture JSONL handoff, unchanged baseline process-only collector, strict reducer counting prohibited paths, missing identities/paths, immutable observed roots, redaction and mandatory non-acceptance.

**Important:** The green hosted-Windows synthetic ETW/FileIO job continues to test **generated controls only**, not the newly added real PilotODIN/no-CDP FileIO mode. That mode has never been executed and needs new one-use approval.

## Follow-up: original child handle and browser profile gating now integrated

[Source contract and exact CI](./P4_N12_NO_CDP_CHILD_HANDLE_FILEIO_PROVENANCE_GATE_2026-11-21.md): [source 1ed9bfe](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1ed9bfe401dfea7251a6d2d256739c2d012a6756), [CI #44923037927](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44923037927) **4/4 SUCCESS** (1,029 Python passed, 6 skipped, 498 subtests; 104 frontend passed, Vite built, disposable browser, hosted-Windows R03 and generated ETW/FileIO checks). The `--no-cdp --fileio` collector now **requires** the original child-handle transport/hosted scope before journey setup. Redacted diagnostics require matching private WebView + network-child original handle lifetime counts, source/binary identity and independently corroborated OS browser command-line UDF. Both labels remain `REVIEWABLE_ONLY` scope and do not establish effective storage location or per-write original-handle completion identity. The next concrete action is the existing N12 **calibration and same-capture write-and-restore proof**, with unchanged no-native approval constraints.

## Last 25%: previous next bounded checkpoint

**Stop multiplying new generic diagnostics.** Finalise a narrowly reviewable real-app source-pinned capture experiment for just the confirmed WebView2 ambient-temp and out-of-profile mutation mechanisms. Before approval, show how the no-CDP FileIO session obtains complete original scoped WebView2 child handles and Sysmon/ETW birth/exit, confirms the browser's **effective** UDF/ambient folder, preserves all protected paths and positive transient controls, and meets the same original strict N12 mutation coverage and calibration requirements. Use exact source/build hashes, previously established protected/permitted roots, no personal owner data, proper stop and cleanup, and only a separate fresh one-use owner authorization for real Windows execution.

A real captured outside-root write must lead to a **specific product or launch-storage correction**, not a new path exception. Only a subsequent independently complete authorised source-pinned run with zero prohibited operations and zero unresolved successful mutations/actors can earn the fourth internal milestone or an R02.5 acceptance decision.

## Score, unchanged

File mutation **3/4 (75%) before and after**; official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**. Native full-app workflows disarmed. No native PilotODIN app, owner-device files, token, ACL, firewall or installer executed or modified.
