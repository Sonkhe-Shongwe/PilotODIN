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

- **Current delivery score: 0 of 4 gates = 0%.** G1 published source substeps G1.1, G1.2 and G1.3. G1.4's exact-source broad regression outcome is pending GitHub CI. Mark **25% only if and when that run succeeds** and the fixed scope is independently checked.
- Last green G1.3 source CI: [#45037803846](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45037803846), 74/74 isolated synthetic tests at `39bd933e82673f675b41483fa229b4decdac57c4`.
- **Official register unchanged:** R02.5 0/5; N12 0/2; P4 14/20 (70%); original file-mutation engineering 3/4 (75%).
- Known historical strict results remain filesystem FAIL, network FAIL, mutation coverage BLOCKED. Former no-CDP run #44932378332 failed pre-app on Sysmon TCP/UDP calibration; approval consumed and workflow disarmed. No native app mutation path inference is permitted.

## Required status report after each NEXT

`before N/4 (N*25%) -> after M/4 (M*25%); active gate; exact GitHub revision and workflow run; tests; remaining native/privacy blockers; next smallest task; official scores unchanged unless independent native acceptance`. No announcement of green before verified GitHub results.

## Source references

- [G1.3 pair contract](./P4_R02_5_G1_3_PRIVATE_FILEIO_PAIR_CONTRACT_2026-11-22.md) and [G1.4 compatibility](./P4_R02_5_G1_4_SOURCE_INTEGRATION_REVIEW_2026-11-22.md)
- [Official P4 acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) and [current status](./PROJECT_STATUS_CURRENT.md)
- [Latest governing session handoff](./SESSION_HANDOFF_CURRENT.md) and [strict trace runbook](../qa/p4_native/N12_TRACE.md)
