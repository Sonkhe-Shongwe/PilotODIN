# P2 controlled batch 2 — report read and navigation safety

**25 October 2026. Source committed; focused owner Windows QA PENDING.**

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
