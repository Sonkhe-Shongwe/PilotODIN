# PilotODIN 1.0 | P4-24 Storage drift isolation and source verification | 11 November 2026

## Binding acceptance and phase scope

**P4 ACTIVE. Gate C UNVERIFIED/NOT WAIVED. P5 NOT AUTHORISED. P8 NOT CERTIFIED.** This source-only increment improves read-only evidence. It does **not** waive the original production EXE + whole original-data-tree preservation check, accept browser cache changes, identify a writing process, certify physical owner data integrity or authorize a new installer.

Original production Tauri app identifier: **com.pilotodin.studio**. Separate P4 native QA identifier: **com.pilotodin.p4nativeqa**. The native launcher in [lib.rs](../frontend/src-tauri/src/lib.rs) passes app.path().app_local_data_dir().join("data") as PILOTODIN_HOME to the Python engine. [backend/storage.py](../backend/storage.py) locates pilotodin.sqlite3, datasets, and models beneath PILOTODIN_HOME. Consequently, files below relative **data/** within the original local application-data directory are treated as **critical project-store files**, never as disposable caches.

## Owner evidence, with boundaries

- The independently saved pre-QA original-data backup has **320 files**, while the later original directory has **346**. The owner observed **30 added, 40 modified and 4 missing** relative paths/content SHA256s (74 differences). The strict post-offline preservation probe returned **FAIL**. Earlier strict PASS is a prior point-in-time result, not a current acceptance result.
- The current separate **QA executable hash passed**. The standalone current **original production executable** hash result was not visible and is still unresolved.
- Owner folder-name classification of the largest 15 changed directories found **46 browser-storage candidate** and **16 cache-like candidate** changes, totaling **62 of 74**. The remaining 12 are not classified by that evidence. These are folder-name pattern hints, NOT proof of ordinary cache churn, harmlessness, or process ownership.
- Original app data might have changed through normal WebView, SQLite journals, legitimate application use, another process, or a cross-app defect. None of these explanations is established. Existing [P4-22](./P4_22_WINDOWS_INTEGRITY_AND_RESOURCE_READINESS_2026-11-09.md) warns that recursive hashing is not an atomic snapshot: concurrent writes can cause mismatch.
- RAM sampling was skipped because the full strict integrity preflight failed; **NOT_TESTED** is not a performance failure. The owner reported scoped offline workspace functionality, not certified offline local Qwen inference or sustained 8 GB resource use.

## New source-only read-only diagnostic

[Compare_P4_Original_Storage.ps1](../qa/p4_native/Compare_P4_Original_Storage.ps1) is a separate opt-in diagnostic. It does not modify the original [Measure_P4_Native_Readiness.ps1](../qa/p4_native/Measure_P4_Native_Readiness.ps1) preservation probe.

The comparator takes explicit paths to the existing baseline JSON, independently copied pre-QA backup, current production app-data directory, and production EXE.

1. Confirms baseline version and purpose; refuses reparse-point inputs or nested backup/current locations.
2. Recomputes the full P4-22 original-data relative-path/bytes/content-SHA256 aggregate for the backup; **any backup versus baseline mismatch aborts**, and the comparator never resets or generates a baseline.
3. Measures standalone original production EXE SHA256 and entire production original-data-tree equality separately.
4. Counts changed files **in memory** as critical project-store (relative data/ prefix, with precedence), browser/cache candidate (known WebView/Chromium folder names outside data/), or unclassified (everything else). Includes added, missing and modified counts for critical store.
5. Displays only aggregate counts, integrity booleans and safety flags. No raw filenames, file paths, file contents or individual file hashes are printed or saved. It writes no reports; performs no file repair, cleanup, backend requests, application launches, installer operations, training, downloads or network calls.
6. **All category changes remain in the strict overall fingerprint**. Even cache-only differences yield REVIEW_REQUIRED_FULL_PRESERVATION_NOT_PASSED; flags explicitly say full_data_integrity_waived=false, project_data_certified=false, writer_process_identified=false and offline_8gb_certified=false.

The tool has **NOT been run on the owner's files**. A zero critical-change count in a future owner-side report would be useful bounded evidence but not prove writer attribution or full app preservation. Do not ask for another sequence of manual folder enumeration; future owner-side diagnostic usage requires an explicit safe coordinated decision preserving the current failed evidence and original backup.

## Actual engineering and test results

**Source/test commit:** [e82e99b775214bfd244516f94da111dcb24e7f12](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e82e99b775214bfd244516f94da111dcb24e7f12).

**Exact-source P4 workflow:** [#43038562027](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43038562027), **COMPLETED SUCCESS**, all three jobs:

- Windows 2022 disposable synthetic probe PASS: existing P4-22 baseline and verification tests PASS, and new [Test_P4_Original_Storage_Compare.ps1](../qa/p4_native/Test_P4_Original_Storage_Compare.ps1) PASS for unchanged backup/original, browser-only drift **still rejected as full preservation failure**, altered SQLite and missing dataset files below critical data/, changed unclassified file, changed original EXE, tampered backup refusal and backup file immutability. No owner's original data, QA installer or model was used.
- **110/110 Python tests PASS**, **29/29 frontend Node tests PASS**, frontend TypeScript/Vite build PASS and **9/9 real-HTTP Chromium P4 tests PASS**.
- Earlier [workflow #43038396925](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43038396925) **FAILED** in the new disposable test harness because PowerShell New-Item does not support -LiteralPath. Fixed by using -Path at e82e99b. Earlier failure preserved, not recast as a success.

A successful synthetic Windows job is **not** direct Windows owner file-integrity evidence, resource certification, or proof that the QA process never wrote outside its intended path.

## Next evidence and release restrictions

Preserve the trusted backup, saved original P4-22 baseline and failed verification; no cleanup, restore, cache exclusion, new baseline or reinstall to force a pass. First decide whether a single opt-in, source-matched **read-only** native run against these preserved sources is justified to identify changes specifically within critical data/ and verify original production EXE. If needed, collect process-aware native evidence separately because folder classification cannot identify who wrote files.

Full original production data preservation remains **FAILED pending root cause**. Offline local model, sustained 8 GB, current-source Windows docking/native UI retest and real-world operational Gate C remain unresolved. **P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**
