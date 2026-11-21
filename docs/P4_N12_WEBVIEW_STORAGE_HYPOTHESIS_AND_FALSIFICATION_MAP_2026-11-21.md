# P4 N12 | WebView2 storage mechanism hypotheses and falsification map

**21 November 2026 | Source-only investigation, not a new Windows capture.** This record follows the [actual N12 file-mutation reconciliation](./P4_R02_5_FILE_MUTATION_CREDIT_RECONCILIATION_2026-11-21.md) and [product-tree feasibility audit](./P4_N12_PRODUCT_TREE_ISOLATION_FEASIBILITY_2026-11-21.md). Existing native N12 #44838416004 remains filesystem **FAIL**, network **FAIL**, FileIO completeness **BLOCKED**; no source-only fixture can change that.

## Reviewed source and three distinct launch surfaces

| Launch surface | Reviewed source | Directly supported fact | Not yet shown |
| --- | --- | --- | --- |
| Production desktop | \`frontend/src-tauri/tauri.conf.json\`, \`frontend/src-tauri/src/lib.rs\` | Tauri v2 creates one main window via \`tauri::Builder::default()\`. The window config does not explicitly set \`dataDirectory\` or \`additionalBrowserArgs\`. Backend and inference workers have app-owned TEMP/TMP/TMPDIR. | The actual WebView2 UDF path, process token, any external policy/environment overrides, and what happens for each runtime write. |
| Standard N12 QA | \`qa/p4_research/n12_app_journey.py::app_environment\` | The app launch declares disposable \`WEBVIEW2_USER_DATA_FOLDER\`, TEMP/TMP/TMPDIR and \`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS\` with remote debugger plus netlog within profile. | That the actual browser honoured all values and kept every file operation inside the permitted profile. |
| N12 Stage 1 no-CDP | \`qa/p4_research/n12_no_cdp_native_path.py::no_cdp_environments\` | Declares disposable UDF and temp, deliberately **does not** add debugger/netlog launch arguments. | Actual child identities (seven original handles historically missing), their environment and effective UDF, or full FileIO completeness. |
| Standard N12 opt-in storage hypothesis | \`qa/p4_research/n12_ambient_local_candidate.py\` | Only explicit \`ISOLATED_QA_ROOTS\` selects additional QA app \`LOCALAPPDATA\` and \`APPDATA\` redirection into verified disposable subdirectories; strict allowlist unchanged. | Whether browser/network/Crashpad children use these values, Known Folder APIs or unrelated runtime paths. |

**External runtime specification, not verified host behaviour:** Tauri v2 supports window \`dataDirectory\` relative to app storage and a runtime \`WebviewWindowBuilder::data_directory\` option; absent an explicit override, default storage selection comes from Tauri rather than our own Rust storage code. Microsoft WebView2 UDF configuration can also be affected by environment and registry/group policy, and browser processes may share a user-data-folder context. The official WebView2 user-data-folder guidance recommends an explicit writable UDF and waiting for browser processes to exit before cleanup. These specifications **do not establish** which override was active in the original approved PilotODIN capture. See [Tauri v2 configuration](https://v2.tauri.app/reference/config/), [Microsoft WebView2 environment reference](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/webview2-idl), [WebView2 process model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model), and [WebView2 user-data folder guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/user-data-folder).

## Competing explanations, not presumed root causes

The machine-readable source-only [hypothesis plan](../qa/p4_research/n12_webview_storage_mechanism_map.py) provides six deliberately unresolved explanations with an independent discriminator and negative control for each:

1. **H1 ambient variables:** actual WebView browser/child writes follow inherited LOCALAPPDATA/APPDATA rather than the declared profile; candidate shifts destination under an otherwise comparable environment.
2. **H2 effective UDF differs:** policy/registry/environment overrides cause the effective WebView UDF to differ from the requested one; the requested variable **alone** is insufficient.
3. **H3 runtime other storage:** independently attributed browser writes outside an **independently verified** effective UDF; don't assume Chrome cache, Crashpad or Windows Known Folder without observed exact path/identity.
4. **H4 debug/netlog side effect:** the network logger/debugger variant changes observed file operations. No-CDP vs standard N12 is not a controlled causal comparison by itself, and the existing ProcMon A/B comparison cannot qualify coverage with its unreviewed loss flag.
5. **H5 wrong/stale actor identity:** an event assigned to WebView2 is not backed by an original process handle, image, PID+birth, parent and correlating Sysmon/ETW lifetime. Historical Stage 1 still lacks seven original WebView2 child handles.
6. **H6 FileIO completeness failure:** background writes, unsupported mutations, handle-path gaps, event/buffer loss or independent positive controls remain unresolved even if more WebView paths are recovered.

### Minimum discriminating native evidence, if separately approved

For each writer/destination hypothesis, a future one-use hosted Windows journey would need: **(a)** exact source SHA and staged executable SHA-256; **(b)** canonical permitted/protected roots, unchanged rules and independent before/after snapshots; **(c)** independently corroborated actual browser/network process identity and lifespan, including original handles when required; **(d)** actual process-start environment or independent effective UDF/policy evidence, not mere launcher intent; **(e)** ETW FileIO operation, path/object lifecycle/rundown, loss counters and a positive transient-control trace; **(f)** public redacted role/destination family summaries, not full private owner paths; **(g)** source-matched A/B launch flags and runtime versions if causal comparison is actually attempted.

**Do not auto-run an A/B experiment:** the current standard N12 and no-CDP environments differ in multiple dimensions, while the old ProcMon A/B completeness contract remains unreachable; the experiment must be redesigned first. One positive outside-path operation is significant even with otherwise matching protected endpoint hashes. The 113 known outside-scope WebView-network path credits, 15 still-missing WebView-network paths, 4,112 background missing paths, 42 missing process lifetimes, other unresolved categories and 23 unsupported WebView operations all remain relevant. The raw original personal file paths were not retained and must not be invented.

## Automated source integrity contract

\`qa/p4_research/n12_webview_storage_mechanism_map.py\` only parses the six explicit checked-in source files, separates the three launch configurations and opt-in ambient candidate, and reports fixed-label \`SOURCE_MATCH\` or \`SOURCE_DRIFT_BLOCKED\`. Its regression tests intentionally tamper with requested UDF, netlog arguments, no-CDP isolation, production custom storage, the QA opt-in guard and false native success. **Even a perfect source match reports \`cause_of_outside_writes: UNKNOWN\`, \`native_N12_acceptance: NOT_EVALUATED\`, \`file_mutation_acceptance: NOT_EVALUATED\`.** No Windows, token, ACL, WebView2 app, owner data or installer is touched by the module.

## Next useful source-only micro-step

Review the exact N12 FileIO reducer's WebView-network **process and file-object lifetime association** alongside the Stage 1 original-handle gap. Identify one sound, externally supportable, minimum process-to-FileIO binding for a future native experiment. **Do not** change the strict reducer or relax permissions without independent proof. Only propose a fresh one-use source-pinned capture after the verification design and stop conditions are demonstrably feasible.

**Official metrics unchanged:** P4 14/20 (70%), file mutation 3/4 (75%), R02.5 0/5, N12 0/2, desktop network 2/3, physical offline inference 1/3, original-data preservation 0/2.
