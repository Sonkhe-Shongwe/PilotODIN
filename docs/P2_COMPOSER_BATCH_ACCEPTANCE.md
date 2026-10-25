# P2 controlled batch 1 — Save, Quality audit, and refresh integrity

**25 October 2026. Implementation committed, owner Windows gate PENDING.**

## Prior accepted scope
P2 Report Open request ordering previously passed owner-observed Node source-contract and TypeScript/Vite checks. Its diagnostic ZIP was not independently inspected and no direct mounted React DOM race was demonstrated. P1 atomic upload staging and four P4 increments retain their accepted focused scopes.

## Three related source-derived async risks
1. A delayed Save POST previously updated saved-report metadata without distinguishing newer title, narrative, or evidence edits made during the request. A new user draft should not be mistaken for the submitted revision.
2. A delayed Quality audit capture previously appended audit evidence after later manual evidence changes, potentially modifying a newer user selection.
3. An error reloading the report library *after* a successful Save, or reloading evidence *after* an audit was captured, previously looked like a failure to save/capture. These are different states and must be reported accurately.

## Bounded implementation
- New `frontend/src/reportComposerGate.ts`: per-component view and draft generations, single write admission, current-view/current-draft checks and project-switch invalidation. Pure deterministic logic. It cannot cancel a POST, roll back a committed report or prevent power loss.
- `frontend/src/ReportWorkspace.tsx`: freezes the submitted Save payload. When the POST returns, updates current saved metadata but leaves user-edited fields untouched; if the draft changed, warns the latest edits were not part of the saved revision. A failed list GET is explicitly reported as a *successful Save followed by failed refresh*.
- Quality audit checks view scope before issuing POST after asynchronous version GET, only automatically selects captured evidence when user has not changed the draft. Otherwise it says the audit was captured but evidence was left for manual selection. Post-capture evidence refresh errors are not misreported as failed capture.
- Concurrent Save/Quality POSTs are serialized; report navigation/new draft is blocked during writes while project change and Explore→Deliver handoff invalidate pending results. The prior report Open ticket and report-library GET also respect newer user navigation or more recent refresh.
- No new FastAPI API, schema, Quality approval, native Save As change, model operation or external dependency. Uploaded source originals remain immutable. A successfully submitted report can persist even if a user switches projects before its response.

## Focused behavioral and regression acceptance
`Run_PilotODIN_P2_Composer_Batch.bat` executes `tools/Verify_P2_Composer_Batch_Local.py` using existing local Python to run:
1. `frontend/tests/p2-report-composer-behavior.test.cjs`: actual new TypeScript guard transpiled through the already-installed `typescript` package in Node, with deferred requests, changed drafts, project invalidation and write serialization. Also includes scoped source-integration assertions.
2. Directly affected existing `p2-report-navigation-contracts`, `report-workflow-gates`, `explore-deliver-evidence`, and `a4-native-report-save-contract` Node tests (legacy navigation assertions updated for the new guard).
3. TypeScript `tsc --noEmit` and Vite build via `npm run build`.

One `pilotodin-p2-composer-batch-*.zip` preserves result JSON and both phase logs. No repeated P0/P1/P3/P4/P5 suites.

**Evidence limits:** Source is committed and reviewed, but these NEW tests have not yet been observed on the owner's Windows installation. Node behavioral tests execute the pure guard, NOT the mounted React component or a live FastAPI/desktop UI. A future manual/browser integration gate is still needed before full UX acceptance; do not claim the reporting module or Build F final release is certified.

## Next owner action
Pull `feature/live-dev-workspace-20261023` in GitHub Desktop, keeping local uncommitted work safe. Run `Run_PilotODIN_P2_Composer_Batch.bat` once. If red, provide `pilotodin-p2-composer-batch-*.zip`; if green, provide the PASS result. No installer, cloud Actions, Qwen/8 GB spike or real project edits during this gate.
