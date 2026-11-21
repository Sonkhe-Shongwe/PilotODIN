# PilotODIN 1.0 | P4-34 No intermediate installer workflow guard

**Date:** 11 November 2026  
**Phase:** P4 ACTIVE  
**Owner requirement:** "no mor installers until we reach the end"  
**Scope:** Enforce the already-recorded freeze against accidental installer creation by existing GitHub jobs on the active development branch.

## Why this mattered

The owner explicitly prohibited further intermediate installers through P4–P7. The instruction was already preserved in status and session handoff, but the active branch still defined multiple installer-capable GitHub Actions jobs, including the native P4 packaging workflow's automatic push trigger and manual dispatch. Documentation alone would not stop accidentally triggering another large installer build while editing source or workflows.

## Source change

[Commit `03cefc7eea9fd8688f9407c5f7d594edb4c38d72`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/03cefc7eea9fd8688f9407c5f7d594edb4c38d72) changes **four existing workflow files and one P4 Node source-contract test only**:

| GitHub Actions workflow | Guarded job | What is prevented |
| --- | --- | --- |
| `.github/workflows/p4-native-windows-milestone.yml` | `full-p4-qa-package` | P4 Tauri/NSIS packaging, CI disposable installer and experimental artifact |
| `.github/workflows/bundled-windows-installer.yml` | `offline-windows-installer` | Build E offline Windows NSIS installer |
| `.github/workflows/windows-desktop.yml` | `windows-installer` | Desktop preview installer build and publication |
| `.github/workflows/verify-existing-installer.yml` | `clean-install` | Download/CI installation of an archived NSIS package |

Each job now has an unconditional `if: ${{ false }}` before its Windows runner and steps, with comments explaining that only a later **P8/final release-stage explicit owner approval** may authorise removal. No workflows or jobs were deleted and no normal P4 source/logic or executable app was changed. `frontend/tests/p4-review-queue-contracts.test.cjs` adds a regression asserting all four frozen jobs have the blocking condition.

This is a **branch-scoped implementation**. Historical `build-e` or other branches can contain different workflow definitions. The standing owner instruction applies to all proposed actions; avoid triggering installer workflows from any branch. These changes do not automatically rewrite another branch, nor do they protect against someone with write access deliberately removing the guards.

## Exact-source verification

All verification at **source SHA `03cefc7eea9fd8688f9407c5f7d594edb4c38d72`**:

| GitHub Actions | Outcome | What was demonstrated |
| --- | --- | --- |
| [P4 target review queue #43075838711](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43075838711) | **COMPLETED SUCCESS, 3/3 jobs** | P4 Python/Node including frozen-job regression, TypeScript/Vite, disposable real-HTTP Chromium, Windows synthetic PowerShell/integrity checks |
| [Adjacent P1 isolated frontend #43075838653](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43075838653) | **COMPLETED SUCCESS** | Existing source/frontend/browser contract regression |
| [P4 native Windows package workflow #43075838775](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43075838775) | **COMPLETED SKIPPED**, sole job skipped | The P4 packaging workflow's own trigger reached GitHub, but **no Windows runner, installer, source/model packaging or artifact was created** |

These results verify the guard operates on the active branch. They are not a fresh full native UI or 8 GB owner-hardware acceptance test. The previous one authorised packaged Windows QA artifact remains separately recorded in [P4-33](./P4_33_GITHUB_ONLY_WINDOWS_QA_BUILD_PROVENANCE_2026-11-11.md) and must **not** be rebuilt, installed or downloaded for an intermediate P4 milestone.

## Binding acceptance remains unchanged

The previously preserved independent backup and original installed EXE matched their baselines and the original critical project `data/` subtree showed 0 changes. Yet **strict full app-data directory equality still FAILS** (320 files in baseline, 346 in later original folder, 74 WebView/cache *candidates*, historic writer UNKNOWN). The owner's P4-28 live snapshot of 26 WebView2 processes (6 QA, 0 original, 20 other) cannot assign prior writes. Do not clean caches, replace the baseline, certify the complete original store or waive the mismatch.

True offline Qwen/8 GB operation on owner hardware, newest-source native UI parity and independently verified operational Gate C remain **UNVERIFIED/NOT TESTED**. Owner previously declined closure with residual risks deferred. Do not close P4, start P5 or certify P8.

**Disposition:** Installer freeze **ENFORCED on active branch + tested with a GitHub SKIPPED package job**. P4 **ACTIVE**, P4-R01–R06 **OPEN**, P5 **NOT AUTHORISED**, P8 **NOT CERTIFIED**. Source-only development and non-packaging automated tests may continue.
