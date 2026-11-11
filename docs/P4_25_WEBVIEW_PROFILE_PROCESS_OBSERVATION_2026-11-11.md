# PilotODIN 1.0 | P4-25 WebView2 profile process observation
11 November 2026. Phase 4 only. No installer, model training or original owner-data write.

## Binding P4 and original preservation evidence

Production Tauri identifier: com.pilotodin.studio. Distinct QA identifier: com.pilotodin.p4nativeqa. Rust launch_backend uses app_local_data_dir()/data for PILOTODIN_HOME (SQLite, datasets, models). These source-level facts are NOT proof of physical Windows WebView2 process ownership or isolation.

Owner-native read-only P4-24 result: independently verified backup matches saved baseline TRUE, standalone original EXE matches baseline TRUE, original protected data/ project-store changes 0 (0 added/modified/missing), WebView/cache candidate changes 74, unclassified changes 0. Original production data backup 320 files, current 346 files; full-tree fingerprint FALSE and status REVIEW_REQUIRED_FULL_PRESERVATION_NOT_PASSED. All 74 are classified only by WebView/Chromium directory-segment names, NOT proven harmless. No current original-data-integrity waiver or file-writer attribution has been approved. The earlier manual 62/74 folder counts were partial; newer entire-tree output covers 74/74. Original QA executable integrity had previously matched.

## New bounded source implementation

- [Observe_P4_WebView_Profile_Processes.ps1](../qa/p4_native/Observe_P4_WebView_Profile_Processes.ps1) is an optional, read-only Windows-only live snapshot of msedgewebview2.exe Win32_Process metadata, via Get-CimInstance. Takes explicit original and separate QA local-app-data root arguments; does not launch either app, query unrelated processes or write files.
- [P4_WebView_Process_Evidence.psm1](../qa/p4_native/P4_WebView_Process_Evidence.psm1) is a pure classifier for a supplied process snapshot. It accepts exactly one fully qualified --user-data-dir argument per WebView2 process, checks normalized directory-boundary-aware prefixes, and counts original/QA/other/unresolved profiles. Missing, relative or conflicting launch flags are unresolved; an empty process list is inconclusive.
- Private command lines, profile paths, file names, user data and per-process identifiers remain in memory and are never output/persisted. Output has aggregate counts and explicit false flags for historical file-writer attribution, no-QA-cross-app-write proof, full original-data preservation, critical project-data certification and offline 8 GB certification.
- It does NOT inspect historical file writes, prove that any observed process wrote any file, or rule out other processes. A QA-profile launch flag is neither proof of never writing outside the QA path nor business release acceptance. The original strict P4-22 baseline/collector and full-tree failure are unchanged.

## Follow-up verified CI on the subsequent documentation/README commit

After the P4-25 source and the initial report were committed, GitHub completed [P4 workflow #43049490270](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43049490270) **SUCCESS** at exact [`7fda31d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7fda31d0d0fe15bfa4867c52173bd79ab84ca2a6). All three jobs completed successfully: Linux synthetic Python/Node/build, disposable real-HTTP Chromium, and synthetic Windows preservation/profile observer. The `qa/p4_native/README.md` change in that commit met the P4 workflow push-path trigger. This corrects the initial point-in-time statement that the documentation successor had no fresh CI. It was an exact-source rerun of already implemented code, NOT a new production implementation or owner native test. No original data, acceptance gate, historical writer attribution or owner decision changed. The present report correction is documentation-only and carries no fresh CI claim.

## Engineering source commit and verification

First implementation [4bdccbe](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4bdccbe6bc4bd2e908ac0e990b8d468e08fa3248), workflow [#43048430220](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43048430220), ended CANCELLED on newer push; its Windows job FAILED because mandatory PowerShell binding rejected the empty synthetic process list. This failure remains in the evidence history. Fixed by accepting empty arrays in [c02b491](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c02b49187422b95d1b2c3e9a165d02b58155bd61).

**Exact source SHA:** c02b49187422b95d1b2c3e9a165d02b58155bd61.
**Full P4 GitHub CI:** [#43048615880](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43048615880) COMPLETED SUCCESS, all 3 jobs at that SHA:
- Windows 2022 synthetic P4-22 and P4-24 integrity fixtures PASS; new P4-25 synthetic WebView2 classifier PASS for original/QA/outside profiles, prefix sibling guard, conflicting/relative/empty flags, overlapping roots rejection, distinct source Tauri IDs and no observer write operations.
- Python 110/110 PASS, Node 29/29 PASS, TypeScript/Vite frontend build PASS, disposable real-HTTP Chromium browser 9/9 PASS.
- None used owner files, actual owner WebView2 processes, an installer or model training. At initial report capture the subsequent documentation/README run had not finished; its later verified conclusion is recorded above.

## 11 November 2026 | P4-28 native observer attempt FAILED in Windows PowerShell, compatibility correction CI PASS

Owner-provided Windows PowerShell screenshot shows that the P4-27 optional observer was **actually attempted** but returned `[System.IO.Path] does not contain a method named 'IsPathFullyQualified'`. There was **no valid owner process-count output**. The error is consistent with Windows PowerShell 5.1 / .NET Framework. The [P4-28 source fix](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a0aa6922b1eff3324f8c9d6c38171a415973ad5e) removed that unavailable method and added Windows PowerShell 5.1 synthetic CI. Exact-source [#43055194559](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43055194559) **COMPLETED SUCCESS** with all three jobs. Owner physical retest is **PENDING**. The optional command below must only be rerun using corrected local source and existing naturally running apps. Strict original full-data-tree preservation remains **FAIL**. No historical writer attribution or risk waiver.

## Optional owner-side observation procedure (NOT EXECUTED)

This is an **owner-approved, opt-in, read-only Windows diagnostic**, not an automatic next development action. Use it only when PilotODIN is already naturally running and owner decides to collect live metadata. Do **not** start either application solely for the test; do not run the older `Measure_P4_Native_Readiness.ps1` RAM collector, modify/rebaseline files, restore/delete caches, or install software for this observation. It cannot resolve the historical writer attribution on its own.

Open Windows PowerShell in the trusted *current source* PilotODIN repository root (branch `feature/live-dev-workspace-20261023` containing the P4-26 fix). The commands below use the default Windows local-app-data roots derived from the existing distinct Tauri identifiers; confirm the actual root layout locally before use. They print no private root path, command line, PID, file content or hash:

```powershell
if (-not $env:LOCALAPPDATA) { throw 'LocalAppData unavailable; no observation taken.' }
$originalRoot = Join-Path $env:LOCALAPPDATA 'com.pilotodin.studio'
$qaRoot = Join-Path $env:LOCALAPPDATA 'com.pilotodin.p4nativeqa'
& .\qa\p4_native\Observe_P4_WebView_Profile_Processes.ps1 `
    -OriginalDataRoot $originalRoot -QaDataRoot $qaRoot |
  Select-Object status,webview2_processes_observed,original_profile_processes,qa_profile_processes,other_profile_processes,unresolved_profile_processes,historical_writer_process_identified,qa_cross_app_write_excluded,original_full_data_preservation_passed,original_project_data_certified,offline_8gb_certified
```

If the file is missing, the expected roots cannot be established, the PowerShell execution policy refuses the script, or CIM access errors, **stop and record NOT TESTED/UNRESOLVED**. Do not download unverified replacements, bypass execution policy, elevate privileges, modify app files or force a new process to start. The command is intended to be run in the user's existing trusted repository checkout, not via remote execution.

Record only the sanitized aggregate output and whether original, QA or neither application was *already* running. Interpret zero observed processes as **INCONCLUSIVE**; a resolved original/QA launch flag establishes **only a current profile argument**, not writer identity or absence of past cross-app writes. Missing/ambiguous flags remain unresolved. No output category waives the previously failed strict original-data-tree comparison.

**Latest source evidence:** P4-26 classifier/test source `50351860537ff2c55be83d01c82f152fc21d09f2` passed [CI #43052326497](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43052326497) in a synthetic Windows runner, not on owner hardware. Owner live process observation: **NOT EXECUTED**. Full original preservation: **FAIL**. P4 closure and P5 authorisation: **NOT APPROVED**.

## Acceptance and next constrained work

| Requirement | State |
| --- | --- |
| Owner original EXE and original protected data/ against preserved baseline | Separate EXE PASS, protected subtree 0 differences, scoped on-owner evidence only |
| Strict entire original data directory | **FAIL / OPEN**, 74 WebView/cache candidate differences |
| Process profile observation source and synthetic Windows logic | **PASS at c02b491** |
| Actual owner live original/QA WebView2 processes and past writer identification | **NOT TESTED / UNKNOWN**, cannot infer past writes from flags |
| RAM/8 GB, real offline local Qwen, source-fixed docking native retest | **NOT TESTED / PENDING** |
| Independent real business Gate C | **UNVERIFIED / NOT WAIVED** |

Next: preserve independent baseline, backup and failed original verification. Do not create a new baseline, restore/delete files, drop cache from strict hash acceptance, start original app solely for this audit, repeat manual file-counting or generate an installer. If genuinely justified, separately coordinate owner-authorised read-only live process observation when apps are naturally running, acknowledging no past writer attribution even then. Until root-cause and explicit owner disposition, original full-tree preservation is **FAILED**. P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.
