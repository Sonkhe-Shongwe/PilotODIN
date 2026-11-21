# PilotODIN P2 | Mounted Deliver incoming handoff latest-request safety

**Date:** 5 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**P2:** ACTIVE / REVIEW_REQUIRED. P1 development CLOSED. P8 offline Windows release NOT CERTIFIED.

## Problem and exact scope

The earlier accepted Explore-to-Deliver test navigated from Explore to a newly mounted Deliver and validated an ordinary project-scoped saved snapshot. It did not exercise a new `preselectEvidenceId` prop while `ReportWorkspace` remained mounted with unsaved analyst input. The original `ReportWorkspace` did guard dirty incoming handoffs with Keep/Discard, but a source-level stale-request boundary remained: when the incoming prop was withdrawn or replaced while the modal was open, `pendingDiscard` could retain the obsolete requested ID. `approveReportDiscard` checked only the project, so a later click could apply that withdrawn handoff and reset text, title and exhibits. The consumed-ID marker also did not reset on withdrawal, preventing a genuine reissue of the same ID.

This was **source-confirmed risk, not an owner-observed installed-app failure**. The verified remedy and acceptance apply only to report evidence handoff; it is not a change to dataset import, Quality approval, model training, generated PDF or project persistence.

## Production correction

- [`a69ec0d7ac4e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a69ec0d7ac4e335914d50780f5e82d2fc10c65f1): `frontend/src/ReportWorkspace.tsx` now clears its consumed incoming-ID marker when parent preselection is withdrawn. A narrow effect invalidates only pending `handoff` discard actions whose project or evidence ID no longer equals the current prop; existing `new` and `open` confirmations remain unchanged. The approval handler independently verifies the pending handoff ID still matches the latest prop before applying the approved reset. No backend/API/schema/data or approved saved report was modified.
- The existing user-controlled Keep/Escape/Discard dialog, pending-write refusal, exact project evidence checks, stale-read invalidation, and immutable backend report logic are preserved.

## Actual regression execution and boundaries

- Added `frontend/p2_mounted_handoff_qa.html` and `frontend/src/p2MountedEvidenceHandoffQa.tsx`. This is a **development-only, CI-flagged localhost 5178 page**, not a production navigation path. It directly mounts the actual `ReportWorkspace` with a parent that can change `preselectEvidenceId` while keeping the child mounted. No duplicate report implementation or fake API.
- Added `frontend/e2e/p2-real-http-mounted-handoff.spec.ts` to the existing trusted GitHub Actions real-HTTP suite. It seeds one disposable three-row CSV and two genuinely saved Explore snapshots in runner-temporary FastAPI/SQLite **outside the browser**. Browser requests are strictly restricted to necessary read-only GETs. It never posts a report, changes Quality, exports a file, contacts an external origin or invokes models.
- Full browser scenario verifies dirty authored title/narrative/selected exhibits; incoming A Keep; unchanged rerender not replaying a refused handoff; incoming B Escape; A withdrawal while modal visible removing obsolete consent; reissued A requiring new consent; invalid evidence refusing any reset; B being replaced by A while the dialog is open and only A applying after approval; and later new dirty text requiring another explicit discard before applying B. It checks backend report list and Quality history unchanged and browser write/remote audit empty.
- [Real FastAPI/SQLite + Chromium CI #42108605339](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42108605339) **COMPLETED SUCCESS, 3/3 actual Playwright** at tested application SHA [`a69ec0d7ac4e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a69ec0d7ac4e335914d50780f5e82d2fc10c65f1). The two earlier real P2 scenarios still pass; third is new live mounted handoff. CI runner is isolated and disposable.
- [Focused P2 #42108851071](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42108851071) **COMPLETED SUCCESS, 61/61 Node source/contracts + TypeScript/Vite production build** at test-only assertion update SHA [`65c16b63aae3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/65c16b63aae370ed5dc13426b8e9671bb2ac878a), with the same production application source.
- Shared frontend cross-phase verification: [GitHub Actions #42108851036](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42108851036). Its precise completed result must be verified separately before counting acceptance.
- Intermediate [#42108605170](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42108605170) and [#42108740549](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42108740549) **FAILED** due to legacy test-only source regex expecting the old unguarded one-line handler and then missing parenthesized condition. Final test-only fix correctly expects latest-ID consent and revoked modal cleanup. Do not report these failed intermediate runs as successful.

## Remaining acceptance and next phase-bound task

**Development acceptance:** mounted real browser handoff, revocation and replacement are accepted **scoped**, assuming the separate shared-frontend run is green. This does NOT establish Windows Tauri/WebView2 native OS dialog presentation/Narrator, cross-window project race or installed offline 1.0 release. Physical native acceptance of the latest Deliver project/workspace exit consent remains open.

The P2 normal authenticated packaged mixed-script Unicode PDF is still **NOT ACCEPTED** because independent approval and code-pinned final SHA-256 for all three original Noto binaries and their three complete OFL notices remain `NOT_GRANTED`. No font asset, PyInstaller sidecar, installed binary or original private dataset has been modified.

**Next:** seek the independent original-font/OFL/face and six-file hash release decision or a bounded owner-native Deliver consent interaction check. Do not replay closed P1 and developer-only font experiments without a new affected source change.
