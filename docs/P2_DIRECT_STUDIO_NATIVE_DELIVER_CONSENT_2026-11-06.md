# PilotODIN P2 | Direct Studio commands share native Deliver-exit consent

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Current phase:** P2 ACTIVE / REVIEW_REQUIRED. P1 CLOSED bounded development, P8 installed/offline release NOT CERTIFIED.

## Source-confirmed remaining entry point

The previous P2 work implemented main-shell Tauri-native **Leave Deliver / Keep editing** via the one-use Rust command `confirm_native_deliver_exit`, but `UnifiedShell.approvePrimaryStudioNavigation` still used synchronous browser `window.confirm` even when primary Studio was itself calling `App.go(next)`. That entry point remains reachable from Studio's **Ctrl+K command palette** while a Deliver report is dirty, even though the nested Studio sidebar and top bar are hidden by the unified shell's layout.

Consequently shell rail/header actions and a Studio command for the same dirty Deliver report used different consent mechanisms. The code also required an after-approval continuation to ensure optional New dataset importer intent, quality/evidence focus, UI notice/error reset and the command palette were not changed before native consent or forgotten after native consent. This was a **source-confirmed inconsistency**, not an observed physical Windows dialog incident.

## Bounded production fix

- [`2f330c3ec106`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2f330c3ec106cdff222bc6391c806aa093248479): `App` extends the primary navigation callback with an optional post-navigation action. Its legacy **New dataset** path requests the overview route and stages `setFile(null);setUploadOpen(true)` only in the approved continuation, never on a declined exit.
- [`7437aefe4a37`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7437aefe4a3715c8eabb7b67c64d0626d5c83247): `UnifiedShell.approvePrimaryStudioNavigation(view,afterNavigate)` delegates dirty Deliver transitions on Tauri to the **existing** `navigateWithDockGuard` native one-use route/IPC guard and immediately returns false to the synchronous Studio `go()` caller. Only the native consent continuation may commit the exact route, and non-native browser confirmation remains unchanged. Existing dock-promotion checks still apply.
- [`44907ac1a822`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/44907ac1a8226b1d65d44b356d3f263148562cd1): `App.go` performs Studio-local cleanup through the same `complete()` callback after approval (quality focus, consumed Deliver handoff, prior scroll, notice/error, upload flag, mobile navigation, Ctrl+K command palette, query). On Stay the callback is never run, so edited Deliver and its command palette remain intact. A fresh accepted New dataset navigation stages the importer after `go`'s clear, avoiding the old ordering problem.

This is **not** a global replacement of browser prompts. Direct URL/history changes, Studio's standalone unguarded `location.hash='#/canvas'` trigger, tab close and dock-specific confirmations remain separate P2 native-review residuals. No native Rust change was needed for this integration.

**No backend, SQLite/report revisions, datasets, Quality snapshots, LLM/model resources, Unicode font binaries, OFL notices, native installed application or Windows installer were modified.**

## Tests actually completed

- [Focused P2 `#42177747250`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42177747250): **COMPLETED SUCCESS, 82/82 Node tests and TypeScript/Vite production build** at exact source/test SHA [`a535bdd6ffa8`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a535bdd6ffa89325c794a320b4285f6f7cff7d5b). New `frontend/tests/p2-direct-studio-native-exit.test.cjs` transpiles and executes actual `App.go`, `App.requestNewDataset`, and the primary shell approval callback, verifies native delegation without browser confirm, no early importer/palette/field state mutation, approved one-use callback, correct post-consent cleanup and browser fallback. Prior Explore handoff source contracts were updated to match the new optional continuation without skipping their intent.
- [Shared frontend `#42177721738`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42177721738): **COMPLETED SUCCESS, 160/160 Node + TypeScript/Vite production build + 5/5 isolated Chromium** at exact production/test SHA [`9e8403f83aa6`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9e8403f83aa6b74c3fe6ec5375af5ac1270e44f2).
- [Disposable owned FastAPI/SQLite + Chromium `#42177721759`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42177721759): **COMPLETED SUCCESS, 5/5 Playwright** at the same exact source SHA. New fifth test uses Ctrl+K while real Deliver is mounted with an unsaved synthetic narrative, injects a **simulated** native Tauri IPC only after app mount, verifies Overview via command palette requests the same one-use native command, Keep preserves the draft/route and leaves palette intact, and an explicitly approved retry navigates to Home, closes the palette and **does not** arm an importer. It confirms report list and Quality history unchanged and browser API mutation/remote audit empty. The prior four real P2 backend/browser cases remained passing, including Save/legacy HTML/PDF parity, saved revisions, mounted handoffs and shell-header simulated consent.
- Earlier intermediate P2 focused failures during this change [`#42177092811`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42177092811) and [`#42177302349`](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42177302349) were **not successes**; old source-level expectations were updated and CI rerun to the final green source/test state. No intermediate failure was reclassified as passed.

## Next acceptance gate remains physical Windows

No owner Windows WebView2 dialog or Narrator/keyboard acceptance is established by simulated native IPC, hosted Chromium, or earlier `cargo check`.

A ready, isolated full-shell native owner QA launcher and five mandatory steps exist: [P2 native Deliver owner full-shell QA](./P2_NATIVE_DELIVER_OWNER_FULL_SHELL_QA_2026-11-06.md), run via `Run_PilotODIN_P2_Native_Deliver_Consent.bat`. On that genuine test's **same disposable project**, an **optional additional** non-release observation is to type a new Deliver note, press **Ctrl+K**, choose **Overview**, then verify native **Keep editing** preserves both the report and palette; on a fresh request, **Leave Deliver** must reach Home and close the palette. This optional sixth observation is not counted automatically by the existing five-prompt runner.

Unicode PDF normal product release remains **NOT_ACCEPTED / NOT_GRANTED** pending separate independent signoff for three original unchanged Noto font files, three complete original SIL OFL notices, RFN/face choice and six exact SHA-256 pins. **P2 remains ACTIVE / REVIEW_REQUIRED**, P8 NOT CERTIFIED.
