# PilotODIN P2 | Owner residual decisions, closure readiness and focused Windows Narrator QA

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** **P2 ACTIVE / REVIEW_REQUIRED. P3 NOT AUTHORISED. P8 NOT CERTIFIED.**

## Explicit owner decisions (binding at P2 scope, not release)

On 6 November 2026 the owner expressly selected: **(1) P2-N03: defer the optional physical Windows dirty Deliver tab-close Keep/Leave observation, with a recorded residual risk; (2) P2-A01: require a short, focused physical Windows keyboard and Narrator test before P2 closure; (3) do not begin P3 until P2 closure is justified, signed off and recorded.** This is separate from the already accepted owner decision `P2-UNICODE-1.0-DEFER-2026-11-06` to preserve standard PDF/HTML and defer end-user mixed Unicode PDF.

These choices do **not** approve P2 closure now, waive serious defects, authorise a packaged release, permit font redistribution, or confer full Windows accessibility certification. Source docs below retain original test/CI evidence and do not need duplicated runs.

## P2-N03: deferred *observation*, not certified functionality

- **Requirement:** With Explore also open, close the **active edited Deliver tab** using the tab's small X. The existing native `Leave Deliver / Keep editing` prompt should preserve the draft and tabs on Keep, and only close Deliver after Leave.
- **Prior evidence:** [Source correction, tests and real HTTP/Chromium simulation](./P2_NATIVE_DELIVER_TAB_CLOSE_SAFETY_2026-11-06.md): production `UnifiedShell.close` guarded, with previous focused CI 97/97 and shared frontend 160/160 + build, real HTTP/browser 7/7 at their documented historical source SHAs. These do **not** establish physical WebView2 tab-X operation.
- **Residual risk:** A native-specific tab-X prompt/focus/IPC failure could result in unexpected unsaved report dismissal. The **impact could be serious if reproduced**; likelihood and field severity are **not independently established**. No confirmed new defect is being waived or mislabelled low severity. Avoid claiming tab-X native correctness as owner Windows ACCEPTED.
- **Owner disposition:** `P2-N03 = DEFERRED BY OWNER (OPTIONAL NATIVE OBSERVATION, 2026-11-06)`. The owner accepts the explicit *verification gap* for P2 development closure review, not any discovered data-loss defect. Follow-up is assigned to **PilotODIN owner / Windows release QA** at the next appropriate native regression or **before P8 installed-release certification**. Record any actual issue as a new critical/high safety investigation immediately, regardless of this deferral.
- **Mitigation until separately tested:** Existing sidebar Explore / New project native consent and two-window consent passed owner Windows tests; these are independently accepted alternative ways to leave Deliver. Preserve warning and confirmed Save revision workflow. Do not imply sidebar acceptance is proof for tab X. No code change or optional sixth QA rerun on unchanged source is requested now.

## P2-A01: required focused Windows keyboard + Narrator test

**Status: FOUR INTERACTIONS OWNER-REPORTED PASS, FINAL WINDOWS CONSOLE/SESSION EXIT PENDING.** Existing five-step native consent and three-step cross-window owner tests remain **SCOPED ACCEPTED**. The additional requirement is not to repeat those tests, but to verify the accessibility modality against actual Windows Narrator.

### New scoped launcher

From the updated feature branch with the existing Python virtual environment, npm `node_modules` and offline Cargo already available, close any old QA windows, and launch:

`Run_PilotODIN_P2_Narrator_Focus.bat`

The **new test-only BAT** invokes the **existing** `tools/Run_P2_Native_Deliver_Consent_Local.ps1 -AccessibilityOnly` option. The unchanged default (no flag) still asks exactly the original five consent questions, while this opt-in mode asks **four different A01 questions**. Both use the same **independent synthetic Tauri QA identity**, disposable four-row CSV project, GET/HEAD-only backend policy, no installer/model/export/save/upload, test-only port ownership and status-only ZIP. The opt-in source has no production `UnifiedShell`, backend, Rust or immutable-report edits.

### Owner actions, in the single synthetic Windows window

1. Turn on Windows **Narrator** with **Windows+Ctrl+Enter**. In Deliver, type a short invented note and, using Narrator navigation, confirm the **Unsaved report draft** warning can be located/understood. It may announce automatically or when focused/read. Record A01-1 **No** if inaccessible or not actually checked.
2. Using the **keyboard**, reach/activate sidebar **Explore**. A true native **Leave Deliver / Keep editing** dialog appears; verify Narrator conveys its purpose and distinguishes the two choices. Record A01-2 **No** if these are not understood or announced.
3. With **Tab / Shift+Tab**, reach both dialog choices; use **Enter/Space** on **Keep editing**. The unsaved note and Deliver remain. Focus returns to a usable control and the keyboard is not trapped. Record A01-3 **No** if any part fails.
4. Retry Explore and choose **Leave Deliver** with the keyboard. Explore becomes usable with an intelligible focus/Tab sequence. Return to Deliver, type a fresh note, use keyboard navigation to activate header **New project**, and select **Leave Deliver** only after the native dialog. The synthetic importer should be understandable to Narrator and keyboard-operable, opening only after consent. Do **not** import. Record A01-4 **No** if part fails or was not checked.
5. Close the synthetic QA window; turn Narrator off with **Windows+Ctrl+Enter** when finished. Answer only the **four** focused yes/no PowerShell prompts, honestly. Share the final console screenshot with `a01_warning_narrator`, `a01_native_dialog_narrator`, `a01_keep_focus`, and `a01_leave_importer_focus` and report any confusing announcement or focus behaviour. The status-only archive path printed by the runner is sufficient; do not upload actual report content/datasets.

**Acceptance threshold:** All four **actually owner-observed** entries `OWNER_REPORTED_PASS` plus actual native session/build exit without failure allow **P2-A01 scoped owner-native PASS**, subject to review of any contradictory visual/accessibility observations. A `FAIL_OR_NOT_OBSERVED` must remain **OPEN** and be investigated; do not call the phase closed. A success is not WCAG certification, full screen-reader coverage or P8 installed Windows release acceptance. This test-only runner has **not yet been executed on Windows**, so no PASS is claimed in this document.

## 6 November 2026 | Final P2-A01 owner Windows four-test console accepted

The owner supplied the **final actual Windows PowerShell screenshot**, with four yes responses and exactly four successful observation keys: `a01_warning_narrator`, `a01_native_dialog_narrator`, `a01_keep_focus`, and `a01_leave_importer_focus`. All display `OWNER_REPORTED_PASS`. Rust completed the native development compilation and the terminal reports `P2-A01 native keyboard/Narrator: OWNER-REPORTED OBSERVATIONS COMPLETE (REVIEW REQUIRED).` The BAT success branch reports `P2-A01: OWNER ACCESSIBILITY OBSERVATIONS RECORDED; REVIEW REQUIRED.` A **status-only QA archive path was printed**, for run `P2-NATIVE-DELIVER-CONSENT-20261106T124947Z-869704ffb9`. Neither its ZIP contents nor exact local Git HEAD was independently inspected.

**Acceptance decision: P2-A01 four required physical Windows synthetic Tauri keyboard/Narrator observations SCOPED ACCEPTED.** Actual system dialog and edited draft were previously screenshot-visible; speech, navigation and focus are attested by owner's final four responses, not independently recorded audio/instrumentation. The console is paused at the final BAT keypress, not installed app evidence. This does not certify full application accessibility or P8 release. No new defect is reported. Do not repeat A01 on unchanged code.

**Other gates:** P2-N03 optional native dirty-tab-X check remains owner-deferred with a recorded potential data-loss impact if a future native regression occurs. Historic P2-linked high-severity BE-028 through BE-031 require an accurate scope/evidence disposition before a whole-P2 no-critical/high claim. Owner full matrix freeze and explicit P2 closure are not yet recorded. **P2 ACTIVE / REVIEW_REQUIRED; P3 NOT AUTHORISED; P8 NOT CERTIFIED.**

## 6 November 2026 | Owner Windows accessibility observations: all four reported working, final runner pending

**Fresh owner evidence:** A screenshot from the actual `PilotODIN P2 Native Deliver Consent - SYNTHETIC DEV QA` Windows Tauri window shows a real system dialog titled `PilotODIN - Unsaved Deliver report`, with the explicit buttons `Leave Deliver` and `Keep editing`, over an open Deliver editor with the disposable narrative `aaa`. This directly demonstrates the native modal and edited report presence in the synthetic QA app; a still screenshot does **not** prove keyboard input, actual Narrator speech or later importer state.

**Direct owner-reported four focused results, prior to runner exit:** Owner explicitly wrote `a1 is fine`, `a2 als i dentifies`, `a3 yes all works`, `a4 greate as well` after being given the four A01 tasks. Record:
- `a01_warning_narrator: OWNER_REPORTED_PASS (CONVERSATION; FINAL CONSOLE PENDING)` — owner confirms warning discoverable by Narrator.
- `a01_native_dialog_narrator: OWNER_REPORTED_PASS (CONVERSATION; FINAL CONSOLE PENDING)` — owner confirms purpose and Leave/Keep options identifiable.
- `a01_keep_focus: OWNER_REPORTED_PASS (CONVERSATION; FINAL CONSOLE PENDING)` — owner confirms Tab/Shift+Tab, Keep preserves report and focus.
- `a01_leave_importer_focus: OWNER_REPORTED_PASS (CONVERSATION; FINAL CONSOLE PENDING)` — owner confirms Explore/Leave and later New project importer accessible.

**Scope-specific interpretation:** This is credible **actual owner Windows Narrator/keyboard observation**, unlike previous simulated-browser coverage, but no terminal screenshot shows the four exact runner `OWNER_REPORTED_PASS` strings, QA artifact integrity result or successful native process exit. For the predeclared A01 acceptance gate, **A01 = OWNER-REPORTED FOUR INTERACTIONS PASS / FINAL RUNNER VERIFICATION PENDING**, not yet unconditional `SCOPED CLOSED`. The owner should close the test window, answer the **four** `yes/no` questions truthfully, and share the resulting PowerShell console. Do not redo the already exercised interactions or the previous five/three accepted native journeys unless an observed failure changes the result.

**Additional closure issue identified during final triage:** The historical master Issue #2 main defect table still lists P2-linked high-severity `BE-028` (report evidence/composition), `BE-029` (workflow/discoverability), `BE-030` (export presentation) and `BE-031` (HTML filename). Later implementation clearly addresses parts, including guided drafting, bounded evidence fact inspection, revision idempotency/comparison, renderer exhibit tables/chart logic, explicit `Content-Disposition` exposure and strict HTML-vs-PDF filename validation. The **historical Issue #2 rows have not yet been reclassified as wholly fixed/accepted**. The actual remainder of each high item must be reviewed against current source and accepted test modality; do **not** call the entire P2 critical/high gate closed merely because the two old startup blockers were fixed. This reconciliation is separate from A01 and precedes P2 closure signoff. Other cross-phase high/critical entries in Issue #2 stay owned by their authorised phase, not silently waived.

## P2 closure-readiness assessment against adopted phase policy

The [adopted one-primary-phase closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) requires a frozen in-scope matrix, no unresolved confirmed critical/high defects, required true browser/native evidence, narrow changed-source regression/build, data-safety guarantees and reconciled Issue #2 / both handoffs.

| Policy gate | Current evidence and remaining action | Status |
| --- | --- | --- |
| Frozen P2 scope | [14-row current register](./P2_ACCEPTANCE_REGISTER_CURRENT.md): U04 Unicode deferred, U07 standard PDF/HTML retained, N03 optional observation deferred by owner, A01 physical Windows required; final owner-accepted **whole-P2 phase scope/freeze** must still be recorded | **REVIEW REQUIRED** |
| Confirmed high/critical in-scope defects | Prior scope-targeted QA entries document corrections, not a newly confirmed unaddressed critical/high P2 issue in the records reviewed. The latest full [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) and any subsequently reported failures require a deliberate final triage; do not infer global cleanliness from absence of a reported complaint | **FINAL P2 HIGH-SEVERITY ISSUE TRIAGE REQUIRED (BE-028–031)** |
| Essential workflows pass appropriate modalities | Previously accepted saved revisions, legacy PDF/HTML, authenticated browser and synthetic native five-step consent + three-step two-window observations remain accepted at their exact scopes. New **A01 screen-reader and focus** modality is still unobserved | **A01 OWNER INTERACTIONS PASS REPORTED; FINAL RUNNER/EXIT PENDING** |
| Changed code tests and build | No production source change in this increment. QA-only runner optional-mode contracts can be tested at source level; the new mode's native Windows run/build is **pending**. Prior CI results remain attached to historical commits | **QA SOURCE CHECK; WINDOWS PENDING** |
| Data protection / no mutation | Existing isolated QA runner seeds disposable data and blocks API writes. This plan does not touch real datasets, immutable saved reports, font binaries, models or installer | **EXISTING ISOLATION PRESERVED (source-level)** |
| Authoritative documentation / owner closure decision | Current acceptance register, source-specific owner decision and handoffs/Issue #2 updated for N03/A01; **P2 owner closure signoff is not yet supplied** | **PENDING AFTER A01 AND TRIAGE** |

**Result: P2 CANNOT YET BE MARKED CLOSED. P3 MUST NOT START.** After the actual A01 Windows test, inspect the four responses, review any accessibility defects, reconcile remaining high/critical Issue #2 scope and freeze/accept the final P2 matrix with an explicit owner closure decision. Only then may the next roadmap phase be activated in a separate authorised increment. P8 installed/offline/8 GiB release, Unicode font distribution and its OFL approval remain separate and **NOT CERTIFIED / NOT_GRANTED**.

## Exact verification limitations of this change

This increment introduces **test-only** `-AccessibilityOnly` mode, a BAT entrypoint and a source-contract test. The opt-in mode has no effect on the default five-step flow except through shared file edits. Do not claim previous five owner observations were rerun or affected. No Windows PowerShell AST parser, true Tauri/WebView2 accessibility response, user-supplied Narrator evidence or release build was available when this document was authored. Use GitHub/source checks as engineering preflight only and retain Windows-dependent acceptance OPEN.
