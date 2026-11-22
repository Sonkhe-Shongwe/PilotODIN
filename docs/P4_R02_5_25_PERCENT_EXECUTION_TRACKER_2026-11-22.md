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

## Last verified milestone

- **G1 complete: 25%.** Published source integrates *tests and contract semantics*, **not a native path-credit hook**. The strict no-CDP FileIO decision continues to block unresolved WebView2 writes.
- **Next gate G2: 25% -> 50%.** Requires a fresh, separately approved hosted Windows native capture, original file handles, independently proven writer/FileObject/IRP/path joins, calibrations and loss review. Do not attempt under source-only standing authority.

## Source references

- [G1.3 pair contract](./P4_R02_5_G1_3_PRIVATE_FILEIO_PAIR_CONTRACT_2026-11-22.md) and [G1.4 compatibility](./P4_R02_5_G1_4_SOURCE_INTEGRATION_REVIEW_2026-11-22.md)
- [Official P4 acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) and [current status](./PROJECT_STATUS_CURRENT.md)
- [Latest governing session handoff](./SESSION_HANDOFF_CURRENT.md) and [strict trace runbook](../qa/p4_native/N12_TRACE.md)
