# PilotODIN P2 | Project import entry and unsaved Deliver navigation safety
**Date:** 5 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** P2 ACTIVE / REVIEW_REQUIRED. P1 CLOSED for development; P8 offline installed Windows release NOT CERTIFIED.

## Source-confirmed P2 risk
The legacy Studio sidebar's **New dataset** button executed `setUploadOpen(true)` before `go('overview')`. If a dirty Deliver draft denied the existing shell navigation consent, the upload flag could still hide/unmount the report despite remaining on its former route. If navigation succeeded, `go` explicitly cleared `uploadOpen` after it had been set, so the import form might not open.

Separately, the main UnifiedShell header's **New project** button set `newProjectOpen=true` before calling the unguarded `navigate('overview')`. A refused dirty-Deliver transition could therefore retain a pending importer intent, which might appear after an unrelated later Home visit.

These were source-confirmed ordering defects, not owner-reported installed-app failures.

## Production correction (unchanged data and APIs)
- [`d91b67100533`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d91b67100533c8d123c5b9619a598aaab075c955): `frontend/src/App.tsx` routes legacy New dataset through `requestNewDataset()`. It first requires successful `go('overview')`, then clears only the selected input File and opens the importer. If navigation is vetoed, nothing changes.
- [`a4968032e58a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a4968032e58a78caf065d0982be365e58420c7f7): `frontend/src/UnifiedShell.tsx` uses its existing `navigateWithDockGuard('overview')` and sets `newProjectOpen` only on approval. This preserves existing dock and edited-primary policies.
- No backend, SQLite, approved Quality versions, original uploads, models, font assets, report renderer, installed app files, `Cargo.lock`, or `gen` resources changed.

## Production-equivalent and contract verification
- [Focused P2 safety #42104984296](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42104984296), exact source SHA [`4bb7aa9f5cc9`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/4bb7aa9f5cc96c331186a9f4bbb9afdf367335ef): **COMPLETED SUCCESS, 61/61 Node tests, TS/Vite build PASS**. Added contracts check that both import actions stage the flag only after approved navigation. Legacy Studio sidebar entry is not visible within the unified shell, so that entry is a focused source-level contract, not a real click assertion.
- [Final full frontend #42105977065](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42105977065), exact tested SHA [`75f40f26ba3d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/75f40f26ba3dd7a8da3a9154c77bc0a56ebf5deb): **COMPLETED SUCCESS, 160/160 Node, TypeScript/Vite production build, 5/5 isolated Chromium**.
- [Final P2 real HTTP #42105977115](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42105977115), same exact tested SHA: **COMPLETED SUCCESS, 2/2 Playwright**. Real disposable FastAPI/Uvicorn/SQLite plus Chromium verifies (a) guided Save/reload/normal legacy HTML/PDF parity, and (b) the real visible shell-header New project action opens the import card with consent, dirty Deliver refuses New project without losing authored text, refused intent does not reappear on later normal Home navigation, existing Leave/Keep consent still protects Explore exit, and genuine saved Explore evidence still reaches Deliver. Original synthetic report list and Quality state unchanged.

### Intermediate failed verification retained
- [#42104389528](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42104389528) **FAIL**: the first new browser test tried to click a hidden legacy Studio sidebar button; that was an invalid visible-control assumption.
- [#42104942661](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42104942661) and [#42105275963](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42105275963) **FAIL**: the new test assumed the conditional Cancel upload button would appear in the synthetic initial-hydration state.
- [#42105632156](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42105632156) **FAIL**, diagnostic confirmed `homeSelected=page`, `importCardCount=1`, `cancelButtonCount=0`, no Deliver heading. The importer WAS visible; the conditional Cancel control assertion was wrong. No private values were printed.
- Tests corrected, and only completed successful final CI counted as acceptance. Historical CI outcomes are not relabelled.

## Acceptance scope and remaining gates
**HOSTED REAL-HTTP/CHROMIUM PASS, scoped** for native-shell-equivalent visible header navigation on the existing development UI; **legacy Studio sidebar SOURCE-CONTRACT PASS**. No direct owner physical Tauri/WebView2, Narrator/keyboard native confirmation, 8 GB combined AI+ML, full offline installer or real user project tested. Normal mixed-script Unicode PDF release remains gated by independently approved exact original Noto font/OFL/face and final six SHA-256 identities: `NOT_GRANTED`.

**Next P2 action:** one bounded native Windows Deliver navigation consent check when the existing Live Dev window is available, or the independent six-file font/OFL distribution decision. In-place mounted dirty Deliver incoming evidence preselection still lacks a dedicated real browser prop-change test. Avoid rerunning accepted P1 cases or font experiments without a new affected source change.
