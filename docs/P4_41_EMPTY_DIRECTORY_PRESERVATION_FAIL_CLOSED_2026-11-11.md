# PilotODIN 1.0 | P4-41 Original-app-data empty-directory preservation integrity

**Date:** 11 November 2026. **Phase:** P4 ACTIVE. **Source status:** fixed, exact-source CI PASS; **owner original-data preservation:** FAIL / not remeasured in this change. **Risk:** P4-R06 (plus historical P4-R02/R03 and real-business Gate C).

## Verified source defect and safety consequence

Prior `qa/p4_native/Compare_P4_Original_Storage.ps1::Tree` computed an aggregate SHA over each **file's** relative-path digest, byte count and content SHA. This is compatible with historical P4-22 read-only `baseline.json` schema v1 but cannot see empty folders. The comparator additionally compared only file counts, file hashes and original EXE. As a consequence, a newly added or removed **empty directory** could leave file fingerprints unchanged and return `status='FULL_FINGERPRINT_MATCH'`, overstating integrity relative to the observed directory tree. This is source-confirmed and disposable-fixture reproduced, **not a claim of another owner machine incident**.

## Bounded fail-closed correction

- [Source `5e92a593b8c0624de8858f64ea0042002b21ef14`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5e92a593b8c0624de8858f64ea0042002b21ef14): add an **in-memory**, case-insensitive directory-relative-path set to the read-only scan, covering empty folders. Compare the directory layout of the **verified independent backup** and current tree; a difference makes `full_original_data_tree_matches_baseline=false` and `status='REVIEW_REQUIRED_FULL_PRESERVATION_NOT_PASSED'`, independent of unchanged file hashes. Report aggregate directory counts and classified added/missing counts only. No directory names, full paths, source contents or per-file hashes appear in output. Browser/cache candidates remain failures, not exempted.
- **Historical-baseline limit:** Do **not** modify/recompute P4-22 file-only baseline schema v1. Because it never recorded directory lists, this added backup-to-current directory check is **not independent proof of exact directory layout at baseline creation**. The output explicitly marks `directory_layout_reference='independent_backup_only_p4_22_v1_baseline_files_only'`. Existing verified backup **file** hash still matches historical baseline; full historical directory provenance cannot be inferred.
- [Test fixture correction `e5f4ac22021c1f172fa282e7b46b269714df7d98`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e5f4ac22021c1f172fa282e7b46b269714df7d98): first attempt used unsupported PowerShell `New-Item -LiteralPath` in **disposable test only**; change to `-Path` (controlled synthetic path).
- [CI coverage `817783dcb8d95841c23ff048bbc7f89956c33f7f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/817783dcb8d95841c23ff048bbc7f89956c33f7f): run the same pure comparator regression in PowerShell **5.1** and existing Windows PowerShell **7** on disposable Windows Server 2022 GitHub runner. No packages, NSIS jobs, owners' records or installed PilotODIN processes were touched.

## Exact-source verification and accurately retained unsuccessful attempts

| Evidence | Verified result | Boundary |
| --- | --- | --- |
| [P4 workflow #43093680329](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43093680329) at `817783dc` | **COMPLETED SUCCESS 3/3 jobs** | GitHub CI, not owner hardware |
| P4 Python and Node | **147 Python pytest PASS; 40 Node PASS, 0 fail** | Synthetic/source contracts |
| Frontend TS/Vite build | **PASS** | Not Tauri/NSIS packaging |
| Chromium disposable real-HTTP | **9 tests PASS** | Test-only local HTTP backend/browser |
| Windows read-only preservation regressions | **PASS on PowerShell 7.6.9 and 5.1.20348.5773**, including added and missing empty directories, unchanged-file-hash negative, restored match, previous file drift/backup/exe guard | Only synthetic copy inside hosted CI |
| Historical first run [#43093371099](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43093371099) | **CANCELLED after Windows synthetic test failure** because `New-Item -LiteralPath` was unsupported; fixed | Never count as PASS |
| Follow-up [#43093470715](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43093470715) | **CANCELLED** after successor workflow push; Windows synthetic comparator had passed before cancellation | Never count as whole workflow PASS |

## Remaining owner acceptance and STOP rules

No real owner files were read or written by this increment. Historical owner independent backup and production EXE matched baseline; critical `data/` store showed zero detected file changes. However, **strict full original app-data preservation still FAILS** on the already-recorded evidence: 320 files in backup versus 346 observed in original app-data tree, 74 WebView/cache *candidate* changed files, process/writer history UNKNOWN. The new comparator cannot identify that writer or close this historical failure. It does not certify project recovery, backup restoration, current native WebView2, offline Qwen on 8 GB hardware, or true business Gate C. R01–R06 remain open; no risk waiver was approved.

The owner explicitly ordered **no intermediate installer builds, downloads or installations until the final stage**. All P4–P7 packaging prohibitions continue; separate explicit approval is required even for future P8 release work. Never clean owner app-data, amend baselines or create a fresh candidate to manufacture a PASS.

**Next:** Only a clearly justified P4 acceptance evidence step or meaningful new confirmed defect should drive more implementation. Source-only work cannot substitute for actual owner Windows/8 GB and independent real-world business evidence. **P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**
