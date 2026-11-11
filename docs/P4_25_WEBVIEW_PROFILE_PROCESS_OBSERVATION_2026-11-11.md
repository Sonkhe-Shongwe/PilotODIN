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
