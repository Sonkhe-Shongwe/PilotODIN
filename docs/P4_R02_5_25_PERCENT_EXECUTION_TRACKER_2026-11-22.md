# PilotODIN R02.5 | GitHub-first remaining-work 25% execution ledger

**Initial GitHub ledger: 22 November 2026.** This is a *new* four-gate engineering-delivery score, not the 20-point P4 acceptance register, N12 results or the earlier 3/4 file-mutation preparation tracker.

## Rules for incrementing

- Increase only in **25 percentage-point chunks** after all explicit exit evidence for a gate is independently verified. Intermediate source work may be tracked but does not earn partial points.
- GitHub is the primary source of truth for code, review, status and routine **source-only** CI. The owner local Windows tree is not a hidden prerequisite for ordinary GitHub source work. Its unpublished audit or dirty state is **not** deemed inspected; obtain it only if genuinely required for a native permission-gated task.
- Routine GitHub source writes and synthetic CI may proceed under the owner's standing GitHub authority. Any separate native Windows run, real WebView2/ETW/Sysmon capture, possible network egress, private raw file-handle inspection, protected owner data, installer or policy/allowlist change retains the existing specific approval restrictions. A disarmed or consumed capture approval is never reactivated by GitHub source authority.
- No source candidate, synthetic fixture, passing CI run or diagnostic count may turn official R02.5 or N12 green.

## Four execution gates

| Gate | Earned credit | Source of required evidence | Decision / restrictions |
| --- | ---: | --- | --- |
| **G1. GitHub source identity and safe contracts** | 25% | Verified published HEAD, provenance, fail-closed destination and original-writer-pair contracts, negative synthetic compatibility test with **unchanged** strict reducer, old and new regression suites passing at exact source, bounded non-native scope | If there is no authentic original file handle, keep the source candidate **not wired into native path credit**. That is the safe integration decision, not a blocked G1. Local owner audit remains unverified. |
| **G2. Complete real native FileIO evidence** | 25% | New one-use-approved, source-pinned disposable hosted Windows run; actual app; successful Sysmon File/TCP/UDP calibration; original writer and original **file** handle to FileObject/IRP/path/operation joins; independent loss, write/restore, private path handling | Requires distinct owner approval. Missing original handles, losses or path epochs stay **BLOCKED**. Product may still have observed violations at the end of G2. |
| **G3. Correct actual product writing mechanisms** | 25% | Captured writer and physical destination linked to minimal root-cause fix; regression and approved native verification; never enlarge root allowances to hide defects | Material product and native actions restricted. |
| **G4. Strict final mutation closure** | 25% | Independent approved full startup-through-exit complete loss-reviewed capture; zero prohibited mutations/unresolved successful mutating operations and unsupported events, independent protected-root prevention and same-capture write/restore; original data safety and cleanup | Governing official acceptance only. |

## Ledger at G1.4 publication preparation

- **Current delivery score: 1 of 4 gates = 25%. G1 PASSED, source-only.** G1.1, G1.2, G1.3 and G1.4 have been published, with exact-source [G1.4 CI #45038916372](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45038916372) **SUCCESS, first attempt, 126/126 tests** across six suites (35 physical destination, 43 FileIO pair, 3 strict-isolation integration, 12 existing writer-identity join, 25 no-CDP strict reducer, 8 mutation triage). Verified source commit [`8138117`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8138117bcb4479af9e136db303461a61672dee8a), with exactly six scoped files and no modifications to the original strict reducer or native workflow. The source-only G1 exit is met; G2 native original-file-handle capture and product attribution remain **NOT STARTED/BLOCKED pending distinct source-pinned approval**. This score is not R02.5 native acceptance.
- Last green G1.3 source CI: [#45037803846](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45037803846), 74/74 isolated synthetic tests at `39bd933e82673f675b41483fa229b4decdac57c4`.
- **Official register unchanged:** R02.5 0/5; N12 0/2; P4 14/20 (70%); original file-mutation engineering 3/4 (75%).
- Known historical strict results remain filesystem FAIL, network FAIL, mutation coverage BLOCKED. Former no-CDP run #44932378332 failed pre-app on Sysmon TCP/UDP calibration; approval consumed and workflow disarmed. No native app mutation path inference is permitted.

## Required status report after each NEXT

`before N/4 (N*25%) -> after M/4 (M*25%); active gate; exact GitHub revision and workflow run; tests; remaining native/privacy blockers; next smallest task; official scores unchanged unless independent native acceptance`. No announcement of green before verified GitHub results.

## G2.1 | One-use native activation and immediate disarm (22 November 2026)

- Fresh **explicit owner approval** for exactly one disposable GitHub-hosted Windows no-CDP FileIO baseline, pinned to reviewed source `166dfa39efa6a1629c35cc4c2c6c3fc740078c3c`. Not a general native-run permission.
- Activation commit [`58f72bf3e226b2a1d87ab11a6fe3727f424268b4`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/58f72bf3e226b2a1d87ab11a6fe3727f424268b4) is a direct child of reviewed source and changed **exactly two files**: the guarded native workflow plus new marker `qa/p4_research/N12_NO_CDP_FILEIO_OWNER_APPROVAL_20261122_FRESH_ONE_USE.txt`. Old previously consumed marker remains unchanged.
- One triggered push run: [#45041259808](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45041259808), attempt 1, pinned to the activation SHA. Source identity and owner approval job steps succeeded; **in progress at latest 22 November 2026 16:00 UTC check**, preflight dependencies active; no verified build/calibration/app FileIO outcome yet. Do not interpret the run as a native PASS.
- Immediate re-disarm commit [`5a4c14d7cfa8f9af003ef22c19b55ab43488d5b0`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5a4c14d7cfa8f9af003ef22c19b55ab43488d5b0) restored `if: ${{ false }}` with only the workflow modified. The running capture remains pinned to the activation SHA; **no retry**, no second run, and no further native authorisation.
- Explicit scope: one unpackaged staged QA build; initial Sysmon TCP/UDP before any app launch; at most one app startup/exit if calibration passes; existing process-child handle observation; same-capture write/restore and strict redacted reduction; cleanup. External WebView2 connections may occur. **No installer, owner workstation/data, unapproved original file-handle enumeration, raw trace upload, root/policy expansion or acceptance award.**
- Critical dependency: a retained original WebView2 **process** handle does not prove the original **file** handle to FileObject/IRP/path relation. A source-only or incomplete native run cannot satisfy G2, even with a successful build or calibration. The native diagnostic intentionally returns non-acceptance; the job result and redacted report must be reconciled once final.
- **Progress remains 1/4 = 25%; G2 IN PROGRESS. Official R02.5 0/5, N12 0/2, P4 14/20 (70%), engineering preparation 3/4 (75%).**

## G2.2 | Final Sysmon birth-window failure isolated, source correction (22 November 2026)

- [Run #45041259808](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45041259808) **COMPLETED FAILURE**: source guard, dependency preflight, unpackaged binary build and **initial Sysmon TCP/UDP calibration (read 1)** succeeded; app worker and same-capture write/restore stage completed. **Final Sysmon calibration blocked** by `parent-birth-before-window` on read 1, before a full strict redacted FileIO receipt could be produced. No acceptance credit.
- Redacted birth diagnostic: one outside-window parent event `-4710` ticks versus start; independent parent creation `+5279` ticks versus start; near 1 ms discrepancy. This supports a *possible Sysmon timestamp quantisation* explanation but is not an independent Windows proof.
- [G2.2 source review](./P4_R02_5_G2_2_FINAL_SYSMON_BOUNDARY_SOURCE_REVIEW_2026-11-22.md) describes the proposed **50 ms final-fixture lead-in** before generated process creation. It **does not** widen the strict Sysmon event window or alter runtime product code, acceptance, file roots or consumed native workflow.
- The activation remains consumed and disarmed; a second native run needs fresh explicit source-pinned one-use owner permission. GitHub source-only tests/CI alone **cannot** turn this into G2 PASS.
- **Delivery remains 1/4 (25%), G2 OPEN. Official R02.5 0/5, N12 0/2, P4 14/20 (70%) unchanged.**


## Last verified milestone

- **G1 complete: 25%.** Published source integrates *tests and contract semantics*, **not a native path-credit hook**. The strict no-CDP FileIO decision continues to block unresolved WebView2 writes.
- **Next gate G2: 25% -> 50%.** Requires a fresh, separately approved hosted Windows native capture, original file handles, independently proven writer/FileObject/IRP/path joins, calibrations and loss review. Do not attempt under source-only standing authority.

## Source references

- [G1.3 pair contract](./P4_R02_5_G1_3_PRIVATE_FILEIO_PAIR_CONTRACT_2026-11-22.md) and [G1.4 compatibility](./P4_R02_5_G1_4_SOURCE_INTEGRATION_REVIEW_2026-11-22.md)
- [Official P4 acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) and [current status](./PROJECT_STATUS_CURRENT.md)
- [Latest governing session handoff](./SESSION_HANDOFF_CURRENT.md) and [strict trace runbook](../qa/p4_native/N12_TRACE.md)

## G2.0 read-only native preflight | 22 November 2026

- **G2 IN PROGRESS, 25% total, 1/4 gates earned.** This is a source-only readiness checkpoint, not a native capture or G2 acceptance.
- Published [G2.0 preflight source commit `a88f32a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a88f32adde19ffd0ac6b3c8200cb401d3d8fd49f) with exactly three files: nine static regressions, the existing Ubuntu-only CI workflow and [native approval/intake boundary](./P4_R02_5_G2_0_SOURCE_ONLY_NATIVE_PREFLIGHT_2026-11-22.md).
- Exact-source [GitHub Actions #45039766442](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45039766442) **first attempt SUCCESS, 135/135 tests** (35 + 43 + 3 + 12 + 25 + 8 + 9), no native Windows/ETW/Sysmon run, installer or original owner data.
- Corrected unfiltered Sysmon Event 3 XML, source pinning, consumed marker and disarmed native workflow are independently checked **as source**. Actual Event 3 TCP/UDP delivery after the correction remains unproven. New one-use approval is still required for the first genuine hosted Windows baseline; a fresh real file-handle/physical-path witness may require an additional separately approved mechanism. **Do not credit protected roots, outside paths or native acceptance from static checks.**
- Official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, original file-mutation preparation **3/4 (75%)** unchanged.
