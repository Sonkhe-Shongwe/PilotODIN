# P4 R02.5 | No-CDP final native-launch scope guard

**21 November 2026 | bounded source correction and generated negative coverage.** This is not a native build, launch, Windows WebView2 capture, FileIO pass, network pass or P4 acceptance point.

## Decision and source finding

The selected debugger-free N12 lifetime/profile path already validates the isolated WebView2 environment in `no_cdp_environments`. Source review identified a defence-in-depth gap at the final `run_one_no_cdp_app` seam: a future direct caller could supply additional non-debugger `WEBVIEW2_*` overrides or inherited host `TEMP/TMP/TMPDIR` without being rejected by **that final launch function**. The current normal caller passes the validated builder output, so this is a source-level bypass risk, **not an observed native write or an attribution of the historical failure**.

This increment repeats the essential pre-spawn contract in the actual launch function. It requires the exact existing disposable WebView profile directly beneath the QA run root, existing non-symlink profile and `app-temp` directories, the separate no-CDP consent string, the reviewed user-data-folder value, all three temp variables in the already permitted `app-temp`, and no nonempty additional WebView2 environment overrides, including a casing-duplicate UDF key. Any mismatch raises `no-cdp-app-launch-scope-unverified` **before `journey.spawn`**. No new allowed root or permission is introduced.

## Checks and verdict boundaries

The corresponding generated tests in `tests/test_p4_n12_no_cdp_native_path.py` now supply the validated scratch in the positive synthetic launch and reject seven invalid environment variants plus absent consent and a wrong QA root, asserting that `journey.spawn` is never called. Existing tests still enforce disabled native workflows, the Rust main-window close veto, the QA synthetic peer's ordinary close request and absence of CDP use. A green routine CI run of these tests confirms **source/fixture behaviour only**.

**Governing native baseline:** the last approved complete [N12 run #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains **filesystem FAIL, network FAIL, FileIO mutation coverage BLOCKED**. Its reviewed comparisons include 113 out-of-scope WebView-network writes, 15 unresolved WebView-network path gaps, 4,112 background write gaps and 42 missing process lifetimes. The later [debug-only WebView capture #44852642468](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852642468) did not distinguish ordinary no-CDP startup or supply complete attribution. No raw private file names may be reconstructed from these records.

## The next decision-changing evidence, not yet authorised

**Operation to review:** one **separately approved, one-use, source-SHA-pinned** hosted-Windows, unpackaged, disposable `n12_app_lifetime --no-cdp` **lifetime/profile smoke**, using the exact isolated identity `com.pilotodin.p4isolatednativedev`. No installer, release artifact, owner PC, protected original project data, dependency download, firewall change or ACL change. The current relevant workflows stay disabled; this document does not activate a job.

**Controls that must be preserved:** exact checked-out SHA and Cargo.lock/staged EXE hashes; independent one-use N12 lifetime and no-CDP consent; fresh QA backend home and WebView user-data profile; main-window and retained-handle identity; ordinary Tauri hidden-peer/main close; source log marker; Sysmon GUID ancestry and digested ETW parent/start/stop; complete process capture with zero loss/buffer faults; unchanged strict filesystem/network criteria for any later full-N12 run.

**Stop conditions:** Rust compile failure; unexpected process/window/profile; refusal of normal close; lost ETW/Sysmon stage, ambiguous lineage or nonzero event loss. Each stops with a **BLOCKED/FAIL** outcome at the last actual stage, not an inferred pass. A lifetime/profile smoke PASS would establish only whether that debugger-free process can start and close with source-corroborated identity. It would **not** resolve the WebView .tmp write mechanism, R02.5 FileIO completeness, R02.6 egress or R06 original-data preservation. A second separately scoped source-pinned FileIO/network experiment would still be needed to explain real destinations and qualify the official checks.

**Progress held:** P4 14/20 (70%); file-mutation engineering 3/4 (75%), R02.5 official 0/5, desktop network 2/3 (67%), N12 0/2. P5 remains unauthorised and P8 installer freeze remains in force.

Related: [previous no-CDP integration](./P4_N12_NO_CDP_NATIVE_LIFECYCLE_INTEGRATION_2026-11-21.md) · [native evidence reconciliation](./P4_R02_5_FILE_MUTATION_CREDIT_RECONCILIATION_2026-11-21.md) · [phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md).
