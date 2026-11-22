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


## G2.2 source verification result (22 November 2026)

- [Source-only fix `a7b76eb`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a7b76eba8ab9c527c3dbe299c5aba4331753110c) adds a 50 ms lead-in for the **generated final** Sysmon fixture while retaining the strict existing event window and no-cdp audit. Its first [Linux CI #45042350684](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45042350684) FAILED because a historical static test still expected the old consumed marker path in the workflow.
- [G2.2 test follow-up `dda5428`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/dda54289d5c1e70993936aed78cd3017cdc4bcf4) corrects that test without changing the disabled native workflow. [Exact-source Linux CI #45042450714](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45042450714) **SUCCESS: 139/139 synthetic tests plus syntax**. The broad non-native push workflow [#45042350753](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45042350753) was CANCELLED on superseding push; no broad CI PASS is claimed.
- Proposed next smallest check: independently authorised **generated Sysmon calibration-only** hosted Windows execution, not an automatic native rerun. Source-test the proposed calibration harness first. An actual original WebView2 file-handle witness remains unproven.
- **G2 OPEN, four-gate delivery still 1/4 = 25%; official R02.5 0/5, N12 0/2, P4 14/20 (70%).**

## G2.3 | Generated Sysmon-only bookend harness prepared (22 November 2026)

- New source-only generated fixture driver `qa/p4_research/n12_generated_sysmon_bookends.py`: two strictly validated **initial and final** Sysmon Windows windows, 50 ms lead-in before **each** generated parent, no PilotODIN build/launch, no original file-handle observation. Reuses `journey.calibrate` and the original `journey.verify_fixture_sysmon`; all verified outcomes are **calibration-only, not product acceptance**.
- `Invoke_P4_N12_Live_Calibration.ps1 -WithEtw -GeneratedBookendsOnly` is an opt-in future Windows source path reusing existing verified Sysmon provisioning and `finally` cleanup. It rejects all app, FileIO, ProcMon and unrelated capture modes, and requires a distinct one-use source-pinned consent. `-WithEtw` selects the Sysmon-only wrapper branch, not an ETW FileIO trace session.
- New `.github/workflows/p4-n12-generated-sysmon-bookends.yml` remains **DISARMED** (`if: ${{ false }}`) and watches a **nonexistent** new approval marker. Future activation must be an independently authorised direct-child commit with a fresh exact-source marker. The old native FileIO workflow remains disarmed and both earlier approvals remain consumed.
- [G2.3 source review](./P4_R02_5_G2_3_GENERATED_SYSMON_BOOKENDS_SOURCE_DESIGN_2026-11-22.md), new injected synthetic timing/negative tests and source guard tests run only in Linux read-only CI. **Do not claim this source is CI-green until the exact-source GitHub run has passed.**
- **No Windows instrumentation or new owner consent obtained.** Two green generated calibrations, when later separately authorised, would not supply real WebView2 file-handle/FileObject/IRP/path attribution.
- **Delivery remains G1 1/4 = 25%, G2 OPEN. R02.5 0/5, N12 0/2, P4 14/20 (70%) unchanged.**

## G2.3 exact-source CI verified (22 November 2026)

- [Published generated-only source `e5367be`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e5367befccbc3a3d9bdfba934f874d6578a01a40) added gated, default-off Sysmon fixture-only Windows entry plus Linux synthetic CI and docs, **without** enabling any Windows workflow. The first [source CI #45044886616](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45044886616) FAILED on an overly broad branch-order test, not a collector run.
- [Scoped test correction `fac34b4`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/fac34b43393535e1ca8041ee178ebc4182501641) reran source CI [#45044944037](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45044944037), **SUCCESS: 152/152 tests across ten suites**, exact committed Python 3.11 source and syntax. **No Windows native instrumentation or new one-use approval.**
- Both the historical N12 FileIO workflow and future generated-only Sysmon workflow remain disabled; prospective marker does not exist. Future native fixture-only check requires fresh explicit one-use owner source-pinned consent. Even a green generated check would not prove original WebView2 file-handle/IRP attribution.
- **G2 OPEN: delivery remains 1/4 = 25%, official R02.5 0/5, N12 0/2 and P4 14/20 (70%) unchanged.**

## G2.4 | One-use generated Sysmon calibration outcome (22 November 2026)

- Approved reviewed source `0862c8dbfe7cd0305bd6fe18a850ca2fc96788b6`, one direct-child activation [`5f99493`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5f99493c7e3ec951fa6332fbb8f96425ead81e9e), immediately disarmed [`2f910a1`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2f910a1cdcf50eb042ffa6357a1d23833d71b07d). One-use owner approval consumed; marker retained, both Windows workflows disabled.
- Hosted Windows [run #45045760389](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45045760389) **FAILED in generated-driver PREFLIGHT**, after approved checkout and Sysmon provision. Neither of the two generated calibration fixtures ran, no application was built/launched, no Windows collector-timing outcome was established. Fixed-label output `BLOCKED / preflight` and nonacceptance only.
- Source root cause: Python `os.environ` is **not exactly `dict`**, while both driver gates demanded `type(env) is dict`. Correct to `collections.abc.Mapping` while preserving identity/consent restrictions, add realistic non-native tests, and replace the stale synthetic assertion that the now-consumed marker is absent. [Detailed G2.4 review](./P4_R02_5_G2_3_GENERATED_SYSMON_BOOKENDS_SOURCE_DESIGN_2026-11-22.md).
- **Progress stays 1/4 = 25%, G2 OPEN; official R02.5 0/5, N12 0/2, P4 14/20 (70%).** Further native execution requires a new explicitly scoped one-use permission, not a retry.

## G2.4 exact-source source regression verification (22 November 2026)

- [`c0fcd3fb071ce963cc62a725f10241e4d896fa30`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c0fcd3fb071ce963cc62a725f10241e4d896fa30) corrected Python `os._Environ` vs exact-`dict` guard and updated historical consumed-marker tests only. [Linux CI #45046033479](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45046033479) **SUCCESS at exact source, 155/155 synthetic regression tests plus syntax**. No native Sysmon operation occurred during source CI.
- Actual Windows run [#45045760389](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45045760389) remains **BLOCKED / preflight**, one-use consent consumed, zero generated calibration bookends verified. Workflow stays `if: ${{ false }}`. Further Windows tests require another specific source-pinned approval; **G2 OPEN** and four-gate delivery **1/4 = 25%**. Official R02.5 0/5, N12 0/2, P4 14/20 (70%).

## G2.5 | Non-overlapping Sysmon bookends source correction (22 November 2026)

- Read-only review detected that the generated-bookend driver reused the **initial** Sysmon record start for its final phase, which could re-import earlier fixture births and confuse process ID reuse with true final-window events. The candidate correction advances the next first record to the previous **verified** tail + 1, preserving strict channel continuity and refusing missing/regressed/non-integer tails.
- The consumed G2.4 generated-only marker remains unchanged. The future **disarmed** Windows workflow is source-scoped to a new **absent** G2.5 marker, preventing reactivation with the prior marker. No native or product launch is authorised or triggered by this source change. Exact-source CI must pass before another one-use approval is considered.
- Delivery **1/4 (25%)**, G2 OPEN; R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)** unchanged.

## G2.5 exact-source regression verification (22 November 2026)

- [G2.5 commit `e71e918`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e71e918877d8411c561dca9b6ed38833583d6632) published the non-overlapping initial/final Sysmon record boundary and disabled next-use workflow trigger. [Linux source CI #45046441140](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45046441140) **SUCCESS, 157/157 synthetic tests across ten suites**. Two new tail-safety cases reject missing/non-integer/regressed channel verification without retries. No Windows instrumentation was executed.
- G1 25% earned, G2 OPEN, G3/G4 unstarted: **1/4 (25%)**. Next Windows generated calibration requires fresh exact-source one-use approval and absent new marker; prior marker consumed. Official R02.5 0/5, N12 0/2, P4 14/20 (70%).

## G2.6 | Generated-only Windows attempt and source-only permission-gate fix (22 November 2026)

- One approved hosted-Windows [Sysmon bookends run #45046709245](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45046709245) **FAILED, BLOCKED/preflight**, after exact-source guard and Sysmon provisioning. Zero bookends verified, one-use approval consumed. Immediate [workflow disarm](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e8bad5ae2f591bc03ed47141a6f8fc1ff855f3ed); no retry, no acceptance.
- [Detailed G2.6 source review](./P4_R02_5_G2_6_GENERATED_SYSMON_HELPER_CONSENT_READ_REVIEW_2026-11-22.md) identifies missing generated-only `sysmon-tail` consent in independent PowerShell helper, a probable preflight blocker. Fix narrowly adds source/consent/hosted-runner/operation-scoped exception, not broad native permission. Definitive native cause not proven by the redacted receipt.
- [Exact-source Linux CI #45047289406](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45047289406) **SUCCESS: 159/159 synthetic tests**, including source-safe generated-only reader tests. Both Windows workflows remain `if: ${{ false }}`, G2.5 approval consumed, new absent G2.6 marker prepared in disarmed source. Future native use needs a fresh explicitly pinned one-use approval.
- **G2 still OPEN, four-gate delivery 25%; official R02.5 0/5, N12 0/2, P4 14/20 (70%).**

## G2.7 | Redacted preflight blocker labels, source-only (22 November 2026)

- [G2.7 fixed-label engineering review](./P4_R02_5_G2_7_REDACTED_PREFLIGHT_DIAGNOSTICS_2026-11-22.md): the generated-only source driver now separates **HOST_SCOPE, SOURCE_APPROVAL, RUNNER_PATH and SYSMON_CHANNEL** preflight blockers using only enumerated, privacy-safe public labels. Strict failure, host/source consents, original event verification, and all root restrictions remain unchanged.
- [Source implementation `3baa5f7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3baa5f778a200533fde0a19a5f2438353eba9192) had initial CI [#45049057684](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049057684) fail at new-test syntax. A single test-file correction [`a5e548b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a5e548b5c4237108346ca167408990d936f8df99) was followed by [exact-source Linux CI #45049161934](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049161934) **SUCCESS, 168/168 synthetic tests in 11 suites plus AST syntax**. No Windows execution.
- One-use G2.5 native run remains **BLOCKED/preflight**; its approval remains consumed. Both native workflows stay disabled, next marker absent. **G2 OPEN, execution 1/4 = 25%; R02.5 0/5, N12 0/2, P4 14/20 (70%)**.

## G2.8 | Genuine generated-only Windows Sysmon bookends PASSED, G2 still OPEN (22 November 2026)

- Approved reviewed source `598bb9fe80f7caca8cd20eec1ab898b9be027fc6`. [Direct-child single activation `9de17f0`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9de17f04525186cd76e9f9e8d4e976e5ee5bab79) changed exactly two allowed files (workflow gate and added G2.6 marker). [GitHub-hosted Windows #45049623361](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049623361) **SUCCESS**, first attempt. Actual strict Sysmon **initial and final generated process/TCP/UDP calibration PASSED on read 1**. Redacted driver status `GENERATED_BOOKENDS_CORROBORATED`, `blocker=NONE`, `evidence=GENERATED_FIXTURE_ONLY`, `product_launched=false`, original-file-handle `NOT_COLLECTED`, native N12 `NOT_EVALUATED`. Zero uploaded artifacts.
- [Immediate one-line re-disarm `3ca694d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3ca694d086fa7ffa23cba173369a5c9fe94cdefc) kept the one-use approval consumed and disabled. The unrelated source-only workflow at temporary activation SHA [#45049623353](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049623353) failed its deliberate disarm assertion; after retargeting the disabled future marker and updating consumed-marker tests, [exact-source Ubuntu CI #45049817722](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049817722) **SUCCESS 168/168 tests across 11 suites**.
- [Full G2.8 evidence report](./P4_R02_5_G2_8_REAL_WINDOWS_GENERATED_SYSMON_CALIBRATION_RESULT_2026-11-22.md). Generated collector calibration is **corroborated**; original WebView2 file handles, completed real FileIO operations and independently loss-reviewed same-capture containment remain unproven. No original-app run was performed under this consent.
- **G2 still OPEN; delivery 1/4 = 25%.** Official R02.5 0/5; N12 0/2; P4 14/20 (70%). Next task: source review of original native **file** handle witness before another separately authorised Windows app test.

## G2.9 | Original WebView2 file-handle bridge admission audit (22 November 2026)

- [Source-only G2.9 feasibility and exact witness requirements](./P4_R02_5_G2_9_ORIGINAL_WEBVIEW_FILE_HANDLE_FEASIBILITY_2026-11-22.md): live no-CDP child observer and private pipe hold **original WebView process query handles**, *not original file handles*. The generated-writer original handle is also a **process** handle. The Win32 final-path adapter accepts a supplied handle but does not acquire or authenticate an original WebView-owned file handle or prove ETW FileObject pointer/IRP relation. Existing G1 contracts remain candidate-only.
- Explicit **NO-GO** for treating PID, synthetic handles, reopen-by-name, final path or user-supplied proof booleans as native file-destination credit. Scoped real WebView file-handle acquisition and same-object kernel bridge need separate mechanism design, privacy review and new explicit Windows permission before any native measurement.
- New source-only negative admission tests and Ubuntu CI; success/conclusion to be independently recorded from exact-source GitHub Actions. Both native workflows remain disarmed and no fresh approval marker is created.
- **Delivery remains 1/4 = 25%, G2 OPEN; official R02.5 0/5, N12 0/2, P4 14/20 (70%).**

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
