# P2 controlled batch 2 — report read and navigation safety

**25 October 2026. First owner Windows run FAIL (one obsolete source contract); repair-only test committed and pending owner execution.**

## Accepted prior P2 batch
Owner executed `Run_PilotODIN_P2_Composer_Batch.bat` and supplied a Windows screenshot explicitly showing `p2-composer-behavior-and-regressions: PASS`, `frontend-typescript-vite: PASS`, `P2 composer controlled batch: PASS`, and `P2 composer focused batch passed`. Local ZIP printed `pilotodin-p2-composer-batch-quomf182.zip`, but ZIP/logs were not uploaded or independently inspected. **Focused controller behavior/source contracts/build accepted**, not mounted React UI or desktop export acceptance. No replay required.

## Three related source-identified issues
1. **Stale evidence lists**: initial async project evidence GET and the post-Quality-capture evidence GET previously had no shared request ordering; a slower initial result could overwrite a newer list containing the captured audit.
2. **Superseded exports**: after beginning an HTML/PDF GET, switching projects or reports could still allow the response to launch Save As/browser download for the now-superseded screen. Even if native Save As is already in flight, stale notices/errors must not override the new screen. A native dialog/save already opened is not undoable.
3. **Draft modified during Open**: the previous report Open ticket was invalidated by a new report selection, but not when the user edited the currently displayed title/narrative/evidence while an old Open GET was pending. That older result could replace the new edit.

## Implementation constraints
- Pure existing `frontend/src/reportComposerGate.ts` extended with `currentView/isCurrentView` and independently latest-response `ReportReadGate` channels for `evidence` and `export`. Both channels explicitly invalidate on project change/unmount.
- In `frontend/src/ReportWorkspace.tsx`, project evidence GET and post-capture GET now apply only their latest token; invalidated initial responses cannot replace the verified post-capture options.
- Report export captures its report id, revision, view and export request token. Once bytes arrive it rechecks token/view BEFORE opening any native Save As/browser download. After a native Save As call, any notice/error/busy update also checks view and token. This prevents stale UI updates; cannot reverse a save already initiated by the user.
- Direct draft edits invalidate older report Open ticket and clear `open` busy state; Save/Audit scope and manual selection remain as previously protected.
- No backend, persisted reports, evidence hash, original datasets, data approval policy, Tauri/Rust, storage schema, model inference or new dependencies changed.

## One Windows acceptance gate
`Run_PilotODIN_P2_Report_Read_Safety.bat` calls `tools/Verify_P2_Report_Read_Safety_Local.py`. The new `frontend/tests/p2-report-read-safety.test.cjs` executes actual TypeScript read and composer guards using deferred Promises: out-of-order evidence results, project-switch stale exports, overlapping exports and view invalidation. It also asserts key frontend integration wiring from source. The gate runs directly affected existing P2 composer/navigation/report workflow/Explore→Deliver/A4 export Node tests, and `npm run build` (TypeScript/Vite). Synthetic isolated `PILOTODIN_HOME`; one `pilotodin-p2-report-read-*.zip` with explicit per-phase PASS/FAIL logs.

**Windows execution of THIS new batch is pending.** Successful Node + build would not prove full mounted React interaction, actual native Windows Save As race, Qwen+8GB feasibility or final release E-01–E-24. Real UI navigation smoke remains a later integration task.

## One next owner action
GitHub Desktop pull `feature/live-dev-workspace-20261023` safely, then run `Run_PilotODIN_P2_Report_Read_Safety.bat` ONCE. If red share ZIP, if green share console result. No old standalone suites, hosted Actions, Qwen download/launch, installer or real user project data changes.

## Inspected owner diagnostics and minimal repair (25 October 2026)

The owner uploaded two ZIPs, both of which were extracted and reviewed directly. Previous composer batch `pilotodin-p2-composer-batch-quomf182.zip` shows **18/18 Node PASS**, **TypeScript/Vite PASS**, overall **PASS**. First read-safety batch `pilotodin-p2-report-read-4wk1z4a1.zip` shows **24/25 Node PASS**, **TypeScript/Vite PASS**, overall **FAIL**. All **seven new read-safety tests PASS**. The only failure occurred in an existing P2 report-navigation source contract expecting mount and unmount cleanup to omit the newly implemented `readGuard.current.invalidateAll()`. This was a stale regex, not a runtime exception, and the newer implementation's requirement to invalidate evidence and export readers is preserved.

**Committed repair:** exactly two matching assertions in `frontend/tests/p2-report-navigation-contracts.test.cjs` updated to require the new read invalidation alongside project and report Open invalidations. Both expressions manually checked against the current GitHub source. Added `Run_PilotODIN_P2_Report_Read_Repair.bat` and `tools/Verify_P2_Report_Read_Repair_Local.py`: **ONLY four tests in the existing affected Node navigation-contract file**, isolated working home, one `pilotodin-p2-read-repair-*.zip`. No production code or frontend build changes and no rerun of 24 previously passing checks requested.

**Verification boundary:** New repair source reviewed and static regex matched, but owner has NOT executed repair BAT. Overall read-safety acceptance remains **pending focused repair PASS**. An eventual green repair test combines with earlier uploaded 24 green Node results and successful TypeScript/Vite to close the scoped gate only; it does not demonstrate mounted React DOM, native Save As behavior, real user data safety end-to-end, E2/Qwen or installer.

## Focused owner repair accepted, 25 October 2026

Owner screenshot of `Run_PilotODIN_P2_Report_Read_Repair.bat` shows `P2 navigation contract repair: PASS` and `P2 read-safety focused repair checks passed`. The repair ZIP path `pilotodin-p2-read-repair-dv9b6oi7.zip` appeared but was not uploaded. Prior first run ZIP was independently inspected with 24/25 Node PASS and TypeScript/Vite PASS; its one stale mount/unmount regex expectation was the only failure. Combining this earlier logged result with the screenshot of the repaired targeted four-test file supports **P2 read-safety ACCEPTED for scoped guard/controller behavior and source/compile verification**. No mounted React DOM, native Save As, or full real-project workflow was executed, so those areas remain pending integration checks.
