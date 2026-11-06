# PilotODIN P2 | Truthful unsaved warning for new Deliver reports

**Date:** 5 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** P2 ACTIVE / REVIEW_REQUIRED. P1 closed for bounded development. P8 installed Windows release NOT CERTIFIED.

## Source-confirmed reporting UX inconsistency

`frontend/src/ReportWorkspace.tsx` already detected unsaved new reports using `hasUnsavedReportDraft` for New/Open/Explore handoff consent and shell navigation. Its visible warning, however, was gated by `hasDraftChanges`, which deliberately required a loaded `opened` report. Consequently a brand-new report with edited narrative/title/selected evidence received no unsaved warning, while an edited saved revision did.

This did not establish an actual loss of persisted user data or a bypass of the existing navigation guard. It was an inconsistent, user-facing indication of whether current work was saved.

## Bounded production correction

- [Source commit `9981567a010b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9981567a010bc5e51c592778947b9b13315177b0) changes **only** the top-level report editor warning to use the existing `hasUnsavedWork` comparison. It displays `Unsaved report draft. Save a revision before exporting.` for new unsaved reports and retains `Unsaved changes. Exports remain linked to the saved revision until you save again.` for modifications to opened saved reports.
- An untouched default new report remains clean and displays no warning. Resetting an edited report to a clean draft clears the warning. The saved-preview notice and `hasDraftChanges` logic for an already saved revision are intentionally unchanged.
- No backend/SQLite/report-content/revisions, verification permissions, HTML/PDF export logic, Quality history, model data, license fonts, native code or installed files were changed.

## Actual verification

- [Real-browser test source `815938171f19`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/815938171f1941446cdac33181138df5fd521864) adds assertions to the existing real FastAPI/SQLite `p2-real-http-report-comparison.spec.ts` fixture. It verifies untouched new report has no warning; choosing a guided outline immediately marks the *new* draft unsaved; opening a saved report removes the warning; editing a saved interpretation shows the correct saved-revision warning; and explicitly resetting to a new clean report clears it.
- [Final full real HTTP + Chromium CI #42110528060](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42110528060) **COMPLETED SUCCESS, 3/3 Playwright** at exact tested application/test SHA `815938171f1941446cdac33181138df5fd521864`. The other two real-backend scenarios, including actual mounted Explore-to-Deliver prop handoff and guided report Save/reload/legacy HTML/PDF, stayed green. Synthetic CI-owned backend and data only.
- [Source-contract test commit `03405e2dc310`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/03405e2dc31061c677f98fb94c01426903c46530) adds one Node check that the warning and navigation consent share the same `hasUnsavedWork` guard.
- [Final focused P2 #42110568424](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42110568424): **COMPLETED SUCCESS, 62/62 Node, TypeScript/Vite production build PASS** at source SHA `03405e2dc310`.
- [Final shared frontend #42110567949](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42110567949): **COMPLETED SUCCESS, 160/160 Node, TypeScript/Vite build, 5/5 isolated Chromium** at SHA `03405e2dc310`. Only a Node test was added after the real-HTTP app/test SHA, so production app code and real-browser scenario were unchanged.
- Previous shared frontend #42108851036 was still stuck installing Chromium before newer source commits; GitHub marked it **CANCELLED**, not passed. Its earlier successful contracts and build remain historical partial results only, and the new final green frontend run supersedes its incomplete acceptance. Other newer intermediate workflow runs superseded by path-triggered commits were cancelled. No failed intermediate production changes were hidden.

## Residual acceptance boundaries

The accepted browser tests run on Linux Chromium with disposable FastAPI/SQLite. They are **not** owner Windows Tauri/WebView2, Narrator/screen-reader, physical scaling, native Save As or offline-installer acceptance. The Unicode PDF release font distribution gate remains `NOT_GRANTED`: three exact unmodified Noto binaries, three complete OFL notices, release file SHA-256 pins, variable-face/RFN review and public Third-Party Notices placement still require independent authorization. Nothing in this increment enables the gated Unicode renderer.

**P1:** CLOSED bounded development. **P2:** ACTIVE / REVIEW_REQUIRED. **P8:** NOT CERTIFIED.

**Next justified task:** Owner-native bounded Windows Deliver navigation/accessibility acceptance, or independent six-file original-font/OFL approval followed by normal product PDF-route verification. No new AI model/training/export format/installer phase authorized.
