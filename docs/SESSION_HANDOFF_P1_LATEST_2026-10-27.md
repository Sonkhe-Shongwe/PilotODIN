# PilotODIN 1.0 — latest P1 continuity checkpoint (27 October 2026)

## Owner Windows project A→B screenshot evidence — partial restoration acceptance

**New actual Chrome Live Dev evidence (six screenshots; 27 Oct 2026):** The synthetic `P0_SYNTHETIC_UI_ML_80` was selected with `Home`, `Your data`, `Quality`, then `Prepare` tab and synthetic Quality `Region` whitespace finding. Subsequently `insurance_claims_CLEANED` was selected and showed a **different saved tab set** (`Settings`, `Model`, `Evaluate`, `Predict`, `Deliver`, `Investigate`, `Home`, `Quality`, then `Prepare`), an insurance-specific **1,000-row dataset inspector** (`months_as_customer`, `age`, `policy_number`, `policy_bind_date`) and its own Quality issues including ambiguous date formats and missing authorities contacted. No `project unavailable` warning or visibly interchanged fields appear in the submitted screenshots. **Scoped owner browser A→B correct-content/tab-isolation evidence PASS**. The sequence ends on `insurance_claims_CLEANED`; **B→A return was not shown**, and momentary in-flight stale flashes are not fully disproven by still screenshots. The new project-restoration eight-case Windows suite and completed Vite production build also were **not supplied**, so do **not** close the full new P1 mount-guard gate.

**Quality v2 now clarified:** The synthetic Quality screenshot explicitly lists **`Surrounding whitespace` / `Region` / 5 affected / `undone`**. This supports that the previous Region trim is no longer active in the current working state, consistent with observed Version 2 and zero active corrections. **Do not treat old v1 trim as currently applied**. The image does not establish exactly when or by whom an undo was approved; do not automatically redo, revert, mutate Quality data or retrain.

**Remaining bounded checkpoint:** Show the restored synthetic project after switching back from insurance (no re-import, no training), and confirm the current new eight-case test result plus final successful `npm run build` output if performed. No previously accepted P0/P1/P2 tests need repeating. Keep the wider Issue #7 responsiveness/accessibility and all installer/font/8GB gates open.


## 27 October latest P1 project restoration mount boundary — source verified, Windows build pending

**Authoritative branch:** `feature/live-dev-workspace-20261023` in `Sonkhe-Shongwe/PilotODIN`. Check live HEAD and Issue #2/#7 again before the next implementation. Previous **responsive dock browser pause/restore** (Quality + Prepare) passed the scoped Windows screenshot inspection, with **8/8 targeted Node cases passed**. The screenshot did not conclusively show the final production build completion or prove exact saved fraction, draft retention or all sidebar/theme gates. Earlier project-catalogue and Quality-preview **14/14 Windows tests + Vite build passed** and remain closed. Do not repeat accepted checks simply for evidence.

**New source-level project-switching risk addressed:** `UnifiedShell.tsx` updates `projectId` during a project change before its `useEffect` reloads that project's persisted tabs, active view and dock. Previously the shell could briefly mount a **new-project App under old-project tabs/dock selection** while the restoration effect was pending. This is an identifiable code-ordering risk, not a reported instance of actual data leakage or corruption. Existing project catalogue request race protections remain unchanged.

**Committed bounded fix:**
- `frontend/src/workspaceLayout.ts::isProjectWorkspaceRestored` allows project-specific mount only when **catalogue is ready AND the last restored project ID equals the selected ID**. Pure function, no storage/data writes.
- `frontend/src/UnifiedShell.tsx` computes `workspaceReady`, temporarily suppresses project-specific tabs and split panes until the current project's state is restored, and renders a neutral `Restoring project workspace` placeholder in the primary view instead of mounting `App` or `InvestigationCanvas` early. It then uses the existing project-specific saved tabs, active stage, dock and route as before. No import, quality, model, output or backend mutation.
- New `frontend/tests/p1-project-restore-mount-gate.test.cjs` contains **8 cases**: A/B restoration mismatch, readiness states, empty import workspace, rapid A→B→A, pure project/dock isolation, and source integration across primary, tabs and secondary mount.

**Verification actually completed:** Live GitHub source refetched; static contract checks passed for exact helper, import, project ID matching, tabs/dock gating, placeholder and existing persisted-state effect guards. The exact pure helper function was replicated byte-for-byte into an isolated Node/TypeScript check: **9/9 scenario assertions PASS**, `tsc --noEmit --strict --target ES2021 --module ESNext` PASS. This is **NOT** execution of the full committed 8-case test or the complete current shell production build. The new source commit is **not yet Windows UI accepted**.

**Next targeted Windows verification when owner is available:** After safely pulling feature branch, from `frontend`, run only `node --test tests/p1-project-restore-mount-gate.test.cjs` and `npm run build` (also establishes a completed post-responsive-dock build). Then if practical switch between **two already existing** projects and back and verify each project shows its own tabs and selected workspace, with no false unavailable warning or previous-project content. Don't import new data or rerun accepted ML/Quality report cases for this.

**Separate unresolved data-state observation:** Latest owner Quality UI screenshot for `P0_SYNTHETIC_UI_ML_80` shows **working v2 / active corrections 0**, whereas previous screenshot showed approved v1 Region trim. Cause is **UNKNOWN without transformation history**. Do not assert v1 is still active, automatically restore or undo, clean again, or retrain based only on this version number. Need history only when the next decision depends on it.

**Still open:** broader Issue #7 navigation/sidebar/theme acceptance and draft preservation, real concurrent 8 GB load NOT_MEASURED, P2 font redistribution NOT_GRANTED, mixed end-user Unicode PDF NOT_ACCEPTED, P2 overall REVIEW_REQUIRED and P8 clean offline installer NOT_CERTIFIED.


## 27 October owner responsive dock screenshots — scoped browser PASS

The owner provided three real Windows Chrome Live Development screenshots from the synthetic project `P0_SYNTHETIC_UI_ML_80`. First, **Quality primary + Prepare secondary** appear side by side; second, the narrower Chrome window shows a **single accessible Quality pane** (with compact navigation); third, the widened window again shows **Quality + the same Prepare dock**. **Scoped visual PASS:** active primary not obscured, second pane temporarily absent in narrow-window view, previous secondary selection visibly restored in wide view. The user did not capture a specific `Docked view paused` status notice, exact measured width threshold, original split fraction or draft form persistence; do not assert those separate checks. This observed success does not certify all responsive/sidebar/dock cases or Issue #7 as a whole.

Owner PowerShell screenshot after the source change shows **8 authored responsive-dock tests, 8 passed, 0 failed, 0 skipped**. This is the **Windows targeted Node test PASS**. The screenshot also shows an `npm run build` invocation and Vite 6.4.5 `building for production... transforming (1598) ...`, followed by a later PowerShell prompt; it does **not** visibly show a final `built in ...` line, emitted assets or an explicit exit code. **Do not promote this to a verified successful post-change production build**. Prior 14/14 project-catalogue/Quality-preview tests and their completed build remain accepted independently; they predate this responsive dock increment. No previously accepted suites should be rerun.

**Unexpected unrelated project-state observation:** The new Quality screenshots show **WORKING VERSION 2** and **ACTIVE CORRECTIONS 0**, whereas a prior owner screenshot showed v1 with one active `trim_whitespace · Region` (five changed cells). This suggests a possible subsequent undo/reversal, but the screenshots do **not** expose transformation history or prove which action created v2. Do not assert that the v1 correction remains active, reapprove automatically, apply Undo, restore v0 or retrain without first reviewing Quality history and user intent.

**Next bounded engineering action:** Continue P1 workspace reliability and test/repair any reproducible visual regression without another dock resize drill. At a natural next build checkpoint, verify a complete `npm run build` terminal result once (only if still required for this modified source); for project history, ask only for a history view if a decision about v2 becomes necessary. Outstanding owner-only checks: switching between two existing projects and back, and a preview-only Quality whitespace display check where a suitable proposal exists; avoid asking for unsafe Undo activity solely for QA. Release blockers unchanged: true joint 8 GB RAM NOT_MEASURED, P2 font approval NOT_GRANTED, product Unicode PDF NOT_ACCEPTED, overall P2 REVIEW_REQUIRED, P8 offline native installer NOT_CERTIFIED.


**Status:** This narrow current-session supplement supersedes older P1 *next-step* descriptions in `docs/SESSION_HANDOFF_CURRENT.md`, without replacing its historical accepted QA evidence. **GitHub is authoritative:** `Sonkhe-Shongwe/PilotODIN`, branch `feature/live-dev-workspace-20261023`; verify HEAD and Issue #2/#7 before changing code.

## Already completed, do not repeat

- **P0:** Scope-limited Windows synthetic ML API/version journey and browser Evaluate/Predict functional journey closed with evidence. These are not complete model, release, or hardware certification.
- **Quality:** In existing synthetic `P0_SYNTHETIC_UI_ML_80`, owner has ALREADY approved `trim_whitespace · Region` (five cells). Working **v1 apply**, immutable original v0 retained. No more approval, Undo, cleaning or retraining requested for this test.
- **P1:** Category labels were distinct in actual Windows Predict browser, 7/7 targeted tests and build accepted. Later category-to-Quality handoff had **9/9 Windows Node and Vite build PASS** after the Windows-safe `CategoryQualityReviewPrompt.tsx` rename. Contextual guidance is intentionally absent for already-applied Quality v1; its exact click path was not filmed.
- **Most recent Windows automated gate, owner screenshot on 27 Oct:** `node --test tests/p1-project-catalogue-race.test.cjs tests/p1-quality-preview-whitespace.test.cjs` returned **14 passed / 0 failed**. `npm run build` succeeded (`tsc --noEmit && vite build`), Vite 6.4.5, **1,628 modules**, **6.14 seconds**. Main **523.94 kB** JS chunk warning was nonfatal. Issue #2 comment `6441534492` and Issue #7 comment `6441539736` record acceptance. **Do not rerun those 14 tests or that prior build just for evidence.**

## This session: P1 measured responsive dock pause

A real source-level UX gap existed in `UnifiedShell.tsx` and `workspaceLayout.ts`: a previously saved two-pane layout could still render two cramped views when the workspace, particularly with expanded navigation sidebar, becomes narrow.

**Implementation now source-committed:**
- `frontend/src/workspaceLayout.ts`: pure `hasRoomForDock(dock, measuredWorkspaceWidth)`, incorporating **300 px minimum per pane** and **9 px divider**, respecting the saved asymmetric fractional width; it never mutates the dock layout.
- `frontend/src/UnifiedShell.tsx`: uses `ResizeObserver` on the actual pane container, with a window-resize fallback, to allow split view only when both panes fit. When narrow it retains `dock.secondary` and saved width, shows only the active primary pane, and displays a clear status message. Widening or collapsing the navigation sidebar can restore the saved split automatically. A project switch still restores the project's own saved dock layout.
- `frontend/src/unified-shell.css`: readable low-emphasis narrow-width notice.
- `frontend/tests/p1-responsive-dock-pause.test.cjs`: **eight authored test cases** for both pane minima, asymmetric widths, temporary resizing, no data/layout mutations, the shell measurement/wiring and CSS notice.

**Evidence:** GitHub source re-fetched and inspected for pure width boundary, nonmutating layout use, observer cleanup, fallback, conditionally hidden secondary and persisted dock restoration. **14 isolated width-boundary assertions on a reproduced pure function** passed locally, but this is **NOT** a claim of running the complete committed eight-case test file or full current TypeScript/Vite build. **Current scoped acceptance: SOURCE COMMITTED / WINDOWS BUILD AND MANUAL RESPONSIVE QA NOT YET EXECUTED**.

## Exact next scoped verification (no prior-suite reruns)

1. Safely pull the feature branch without discarding local changes. In the existing `frontend` checkout run **only** `node --test tests/p1-responsive-dock-pause.test.cjs`, then `npm run build`. Report first failure if either red.
2. In existing Live Dev use already-imported projects; dock a workspace beside the primary pane. Reduce window width until the dock is paused, verify primary remains accessible, then widen again and check the same secondary selection and split fraction return. This is owner visual scope, not a hardware stress or unsaved draft retention test.
3. Earlier unrelated manual gates, **still not observed:** switching between two existing projects without stale-project warnings; Quality v1 Undo **preview only** showing `[SPACE]` markers, then **Cancel**. Do not use these as grounds to repeat completed tests or apply Undo. Batch them only if naturally convenient.

## Preserve other open boundaries

- Broader Issue #7 sidebars, responsive dock and cross-workspace theme accessibility remain OPEN until user Windows visual evidence.
- True combined 8 GB peak RAM `NOT_MEASURED`.
- P2 font/OFL/RFN redistribution `NOT_GRANTED`; mixed end-user Unicode PDF `NOT_ACCEPTED`; P2 overall `REVIEW_REQUIRED`.
- P8 clean offline Windows installer `NOT_CERTIFIED`; no font packaging, arbitrary AI code execution or model download undertaken.

**No datasets, stored model artifacts, experiment outcomes, release binaries, installed product, original CSVs or user permissions were changed in this session.**
