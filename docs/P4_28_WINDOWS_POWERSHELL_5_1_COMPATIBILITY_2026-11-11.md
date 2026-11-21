# PilotODIN 1.0 | P4-28 Windows PowerShell 5.1 WebView2 observer compatibility

11 November 2026. P4 safety diagnostic correction only; no installed app, owner data, model, installer or release change.

## 11 November 2026 | Owner-native corrected observer retested successfully

**Actual user-supplied Windows PowerShell screenshot:** After fast-forwarding the local authorised checkout to `7f2eb5f`, owner ran the same read-only observer. The module file search returned only a comment mentioning the previously unsupported `IsPathFullyQualified`, and the command produced a complete structured result without the earlier method-not-found error. This upgrades the **compatibility repair's owner-native execution status to PASS**. Preserve the earlier runtime FAIL as history.

| Current launch-profile field | Owner screenshot |
| --- | ---: |
| `webview2_processes_observed` | 26 |
| `original_profile_processes` | 0 |
| `qa_profile_processes` | 6 |
| `other_profile_processes` | 20 |
| `unresolved_profile_processes` | 0 |
| `observed_user_data_directories` | 26 |
| `snapshot_is_atomic` | false |
| `historical_writer_process_identified` | false |
| `qa_cross_app_write_excluded` | false |
| `original_full_data_preservation_passed` | false |
| `original_project_data_certified` | false |
| `offline_8gb_certified` | false |

**Interpretation is narrow:** 6 observed WebView2 launch arguments are classified beneath the supplied QA application-local-data root, none beneath the supplied original root, and 20 outside both roots; `other` does not identify or exonerate unrelated applications. `observed_user_data_directories=26` means 26 process flags classified by this observer, **not proof of 26 unique directories**. This non-atomic current snapshot cannot identify historical file writers, prove that the original app was or was not running, exclude QA cross-app file writes or waive strict preservation. No raw user paths, command lines, file names or PIDs were recorded into GitHub.

**Phase gates unchanged:** P4-24 full original tree comparison remains **FAIL** (320 baseline vs 346 current files; 74 browser/cache candidate differences); original protected `data/` subtree 0 detected differences, independent backup and original EXE match baseline. No new baseline or automatic cache exclusion. Native source-fixed dock UI, local offline Qwen/8 GB and business Gate C unverified. **P4 ACTIVE, P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** [Synthetic CI #43055194559](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43055194559) at [`a0aa692`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a0aa6922b1eff3324f8c9d6c38171a415973ad5e) remains the last completed exact-code verification for the observer. No new source implementation or owner action is required simply to repeat the snapshot.

## Owner native failure and scope

The owner executed the previously prepared read-only WebView2 observation in Windows PowerShell from a local PilotODIN checkout, using original/QA `LocalAppData` roots. The screenshot contains:

```text
Resolve-P4WebViewProcessOwnership : Method invocation failed because [System.IO.Path] does not contain a method named 'IsPathFullyQualified'.
At ...\Observe_P4_WebView_Profile_Processes.ps1:14 char:11
```

The failed method is in `qa/p4_native/P4_WebView_Process_Evidence.psm1`. `System.IO.Path.IsPathFullyQualified` is not implemented in the .NET Framework path API used by Windows PowerShell 5.1. The screenshot does not separately print `$PSVersionTable`; classify the environment as **consistent with Windows PowerShell 5.1**, not independently version-confirmed. The error occurs after the script attempts to read current `msedgewebview2.exe` process metadata but **before producing any valid aggregate output**. No historical writer identification, profile isolation or zero-process finding follows. The observer is source-defined read-only, but this screenshot alone is not a complete filesystem integrity audit.

**Owner Windows P4-27 observation attempt: FAIL (runtime compatibility).** This is a confirmed diagnostic defect, not a demonstrated original project-data modification.

## Minimal correction at exact commit

[Source commit `a0aa6922b1eff3324f8c9d6c38171a415973ad5e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a0aa6922b1eff3324f8c9d6c38171a415973ad5e) modified only:

1. `qa/p4_native/P4_WebView_Process_Evidence.psm1`: new `Test-P4AbsoluteWindowsPath` uses supported `[IO.Path]::IsPathRooted` and accepts only a fully drive-absolute path or a complete UNC share path before calling `GetFullPath`. It explicitly rejects drive-relative `C:folder` and root-relative `\folder` inputs. This validation now applies to both trusted source-profile roots and a parsed `--user-data-dir`. The original read-only classification, fail-closed ambiguous flags and all false certification fields remain intact.
2. `qa/p4_native/Test_P4_WebView_Process_Evidence.ps1`: disposable fake WebView2 records now cover drive-relative and root-relative flags, refusal of relative source roots and one absolute UNC control. Existing original/QA/other/quoted-flag tests remain.
3. `.github/workflows/p4-target-ranking.yml`: adds a dedicated synthetic Windows runner test step with `shell: powershell` and an assertion that the interpreter major version is 5 (Windows PowerShell 5.1). The original `shell: pwsh` synthetic probes continue unchanged.

No additional dependency installation in production, model weights, original owner datasets, project databases, application launch or QA installer build.

## Verification and limits

| Check | Actual result | Applies to |
| --- | --- | --- |
| [P4 workflow #43055194559](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43055194559) at `a0aa692` | **COMPLETED SUCCESS** (3/3 jobs) | Exact source and synthetic fixtures |
| Windows 2022 existing read-only preservation and WebView fixture suite, `pwsh` | **PASS** | Disposable Windows runner only |
| Added Windows PowerShell 5.1 step, `shell: powershell` | **PASS** | Same disposable fake process metadata, real .NET Framework interpreter |
| P4 Linux Python/Node checks, TypeScript/Vite build | **PASS** | Synthetic CI |
| Disposable real-HTTP Chromium P4 integration | **PASS** | CI HTTP/browser, no physical Windows app |
| Corrected observer run on owner's Windows computer | **NOT YET RETESTED** | Previous owner run remains FAIL |
| Historical file writer, complete original data preservation | **UNRESOLVED / original full-tree FAIL** | No new forensic evidence |

This documentation commit has no separate fresh production CI. Earlier completed source runs remain in the historical record; do not reinterpret the owner screenshot as an accepted test.

## Safe next action and acceptance restrictions

Only if the owner independently chooses another observation and the relevant original/QA application is **already naturally running**: check the local checkout is on the authorised feature branch with no uncommitted owner work, fast-forward it to the current repository source, then run the existing read-only observer as documented in [P4-25](./P4_25_WEBVIEW_PROFILE_PROCESS_OBSERVATION_2026-11-11.md#optional-owner-side-observation-procedure-not-executed). Do not open apps solely for a snapshot, bypass blocked local commands, change execution policy, run as administrator merely for this test, clear cache or replace baselines.

A resulting current WebView2 launch profile is **not evidence of what process modified historical files**. If zero processes run, output is **INCONCLUSIVE**. If the observer still fails, record the exact failure, do not fabricate a PASS. Share only aggregate output, not local usernames/paths/command lines.

Prior P4-24 owner evidence remains: independent backup and original EXE match baseline, critical project `data/` subtree 0 changes, but **strict original data-tree equality FALSE/FAIL** (320 original vs 346 current; 74 browser/cache *candidates*, historical writer UNKNOWN). Source-fixed native dock retest, offline local Qwen and sustained 8 GB, real business Gate C remain open. No owner waiver, phase closure or release certification: **P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED**.
