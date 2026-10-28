# PilotODIN P1 — consolidated development closure register

**P1 PRIMARY PREPARE DRAFT SWITCH DEFECT: OWNER WINDOWS 12/12 FIXTURE CONTRACTS PASS, NEW BROWSER 0/1 FAIL; SOURCE PATCH PENDING ACCEPTANCE (28 OCT 2026).** Screenshot: `node --test tests/p1-playwright-pilot-contract.test.cjs` **12 tests/12 PASS, 0 fail/skipped/cancelled**, 548.3904ms; `npx playwright test --config=playwright.config.ts -g "primary Prepare unsaved target"` **1 FAILED** at `e2e/isolated-workspace.spec.ts:460`, `expect.poll(()=>prompts.length).toBe(1)` timed out after 8s, actual 0 prompts. Confirms missing **primary Prepare draft consent** before global project switch, not an unmocked API or a proven actual erase (later assertions were not reached). Production patch `95297a4050cc2481b3aef162d0bb6d4e650a38c0` adds a project-scoped in-memory primary draft indicator for native Prepare/Model/Predict form edits and chosen target suggestions, with **no form values persisted/transmitted**. Shell now combines primary and existing secondary-dock project-switch warnings into **one prompt** for global selector, direct Studio project load and pre-upload gating; Cancel returns before switching/upload, and direct Studio successful project read retires the primary marker only after fetch, preserving it on read failure. It intentionally does not claim all click-driven model controls, external cross-tab primary selection, window close/reload or invalid global-project fetch safety. Four pre-existing source-contract test files patched as needed; seven fresh targeted Node cases in `frontend/tests/p1-primary-draft-switch-safety.test.cjs` (UNRUN) cover guard semantics, single consent, no stale cross-project marker and source wiring. **Exact new-source Windows gates**, from `frontend` after safely pulling: `node --test tests/p1-primary-draft-switch-safety.test.cjs tests/p1-primary-project-load-approval.test.cjs tests/p1-external-project-transition-guard.test.cjs` then `npm run build` then `npx playwright test --config=playwright.config.ts -g "primary Prepare unsaved target"`. These revised-source results **ALL PENDING**. Earlier 12/12 Playwright fixture contracts and five accepted browser tests are separately CLOSED and must not be rerun without changed dependencies. No backend/dataset/ML/AI/CSP/installer/CI/package lock changes; P1 remains the single active phase until closure.

**Active as of:** 28 October 2026. **Closure status: OPEN.** This is the working acceptance matrix for the single active phase under [Phase Focus Policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md). No numerical completion percentage is an official gate.

**Scope:** Robust import/project recovery, versioned Quality safety, primary/secondary Studio projects, navigation/unsaved forms, browser/native responsive, accessibility, and project-state synchronization. Non-P1 P2 reporting/font, P6/P7 AI autonomy and P8 release packaging are dependencies, not silently included as completed P1 work.

| P1 capability / gate | Status | Evidence boundary or missing acceptance |
| --- | --- | --- |
| Import recovery with isolated rollback | ACCEPTED, SCOPED | Four owner-run recovery tests, earlier upload staging and one Chrome Cancel pre-upload. Interrupted/oversized/malformed real OS paths and transaction failure coverage still require consolidation. |
| Versioned Quality, approvals and project separation | ACCEPTED, SCOPED | Existing backend/Windows and manual Quality history, undo/reapply, two-project data isolation. Must preserve immutable originals and approvals; broad unusual input verification remains open. |
| Primary navigation, selected project and edited secondary dock | ACCEPTED, SCOPED | Owner Windows 41/41, 24/24, 49/49 checkpoints and manual Chrome consent; separate source revisions, not an aggregated suite. |
| Responsive edited secondary dock in Chromium | ACCEPTED, SCOPED | Isolated Playwright 1/1 owner Windows; below-minimum-width synthetic browser hide/restore only, not native window snapping, scaling or touch. |
| Browser normal Back/Forward with edited dock | ACCEPTED, SCOPED | Isolated Playwright 1/1 owner Windows with synthetic Explore responses. |
| Cancelled external edited-dock promotion | ACCEPTED, SCOPED | Real defect reproduced 0/1, fixed by precommit Navigation API, then 27/27 Node + Vite build + 1/1 Chromium PASS on 28 Oct 2026. Chrome only; legacy WebView/traverse behavior not certified. |
| Primary Prepare/Model form drafts when switching projects | **OPEN — NEXT** | Current `App.loadProject` resets target, excluded features, model options, confirmation/split fields. Existing shell only tracks edits to the *secondary* dock. Need targeted synthetic test and reject/retain behavior for primary fields before any reset. |
| Cross-tab external project selection/reload and draft reconciliation | **OPEN** | Several owner cross-tab Cancel/storage tests accepted for edited secondary dock, but primary draft, reload/restart, multi-tab race and stale project choice not comprehensively accepted. Do not presume persistent unsaved forms. |
| Keyboard, screen reader, narrow native desktop | **OPEN/PARTIAL** | Scoped left-rail keyboard/tab-focus tests accepted; Issue #7 and manual WebView2 scaling/snap/accessibility checks still open. |
| End-to-end import → Quality → project switch → restore under failure | **OPEN** | Assemble a bounded full P1 regression/owner desktop walkthrough only after missing cases are fixed; account for in-flight upload and project unavailability. |

## Nonnegotiable P1 closeout

- No unreviewed destructive change to a user's source dataset; project selection Cancel happens before discard or upload.
- Real Cancel must preserve **primary and secondary** unsaved edits, selected dataset/version and route; failed fetch cannot clear an existing workspace.
- Define what is persisted versus intentionally ephemeral. Clearly warn before reload/close where preservation is not supported; never silently promise permanent storage for in-memory drafts.
- Cross-tab storage events must not trigger endless conflicting project writes or silently override the active edited project.
- Support accessible keyboard navigation, focus restoration, 125%/150% Windows scaling and genuine supported narrow viewports in the eventual installed app.
- Pass focused tests and new-source build, then owner browser/native acceptance as relevant. Unverified items remain open; no invented acceptance.
- Close remaining critical/high P1 Issue #2 defects and explicitly document owner-approved deferrals.

## Immediate next engineering sequence

1. **Primary unsaved draft switch gate (DISCOVERY AUTHORED; WINDOWS PENDING):** One new two-project synthetic Playwright test edits primary Prepare target `fraud_reported` and attempts an unrelated project switch. Cancel must keep project, URL and target, with zero real API writes. A new Node test checks fake project response contracts. Current suite: 12 Node authored, 6 browser authored (prior 5 accepted). Do not claim acceptance until Windows evidence, then implement the smallest production correction required.
2. Once implemented and accepted, address primary draft preservation/explicit warnings across ordinary route changes, tab close and new-project import.
3. Cross-tab reload reconciliation for edited primary/secondary forms and failed project reads.
4. Native WebView2 and Windows scaling/legacy traversal acceptance.
5. One final P1 integrated checklist with severity-based defect closure and source-commit evidence.

**No P1 '100%' claim** until this register's in-scope critical/high gates are actually closed. Explicit P8 installer and P2 production PDF font approval remain independent gates.
