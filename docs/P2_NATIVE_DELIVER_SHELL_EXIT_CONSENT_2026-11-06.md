# PilotODIN P2 | Native shell-initiated Deliver workspace-exit consent

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** P2 ACTIVE / REVIEW_REQUIRED; P1 CLOSED for bounded development; P8 installed offline release NOT CERTIFIED.

## Source-confirmed WebView2 consent risk and bounded remedy

The unified shell already tracked unsaved Deliver drafts using a memory-only `editedPrimary` marker. Its ordinary main rail, workspace-tab and **New project** navigation used synchronous browser `window.confirm` to approve unmounting Deliver. Windows WebView2 does not provide a reliable general acceptance guarantee for this browser confirmation. Existing separate native **project selector** and OS **CloseRequested** Rust dialogs are not a substitute for shell workspace navigation. This was a source-confirmed risk, **not proof of a physical Windows dialog failure**.

This increment changes **only shell-initiated navigation from dirty Deliver** under Tauri:
- [Rust command `2c0d1c473312`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2c0d1c47331224315b0308afa5349c07f665cbfd) adds `confirm_native_deliver_exit` to the existing allowlisted native commands. It refuses non-`main` windows and uses a warning dialog parented to the real main Tauri window. Buttons are **Leave Deliver** and **Keep editing**; `blocking_show` runs in `tauri::async_runtime::spawn_blocking`, never on the WebView UI thread. Returning `false` never authorises a route.
- [Shell route change `cd3741d31d17`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cd3741d31d17e44c9e47d1e8028352000c38bed5) uses that native command only when the existing `needsPrimaryStudioExitApproval` guard identifies a dirty Deliver exit on Tauri. The report and URL remain unchanged while native IPC is outstanding. Duplicate actions cannot start another dialog. The result is ignored unless the exact original project, active view, route hash, dirty Deliver marker, and one-use ticket remain current. IPC error displays a truthful keep-data warning without navigating. A second approval cannot be reused by a different route.
- [Focus/import sequencing `28cc136cd768`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/28cc136cd768065647ca9dbe2300ebed11e9320f) retains the focused keyboard target when delayed navigation succeeds and opens New project's importer **only after** approved navigation. The exact route-push preapproval is staged only after the existing dock-promotion guard succeeds. Non-native Chromium retains its existing synchronous browser confirmation.

**Not rewritten:** Internal Studio `App.go` navigation and `approvePrimaryStudioNavigation`, direct hash/history route changes, tab closure, external project lifecycle, dock reset/close/replace and their existing browser confirmations. They remain separate native-review residuals. There was no framework-wide conversion to an asynchronous navigation engine. An approved native exit that subsequently hits another unsatisfied dock guard remains vetoed.

No API, backend, SQLite, source files/datasets, Quality approved versions, saved reports, PDF renderer, Noto fonts/OFL notices, model assets, installer or installed executable changed.

## Exact completed CI and regression results

- [Windows native Tauri/Rust compilation #42155933002](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42155933002): **COMPLETED SUCCESS** at Rust source commit `2c0d1c473312`. CI stages intentionally INVALID tiny compile-only placeholders, verifies packaging preflight rejects them, runs `cargo check` on `x86_64-pc-windows-msvc`, removes only the placeholders it owns and confirms nothing shippable was produced. This is compilation, not real native dialog execution.
- [Focused P2 #42156575635](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42156575635): **COMPLETED SUCCESS, 70/70 Node + TypeScript/Vite production build**, source commit `47a12169f2d6`. Includes new `frontend/tests/p2-native-deliver-exit.test.cjs` that transpiles the real production TS navigation closure, executes Stay, approve, failed IPC, pending duplicate, stale project/view/hash/dirty marker/ticket, browser fallback and the Rust command/wiring source contract.
- [Shared frontend #42156899928](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42156899928): **COMPLETED SUCCESS, 160/160 Node + TS/Vite production build + 5/5 isolated Chromium**, exact final app/test source SHA `0f93bf40f4eafafa0a6152efba1de72de12bac92`.
- [Actual synthetic backend / browser #42156900323](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42156900323): **COMPLETED SUCCESS, 4/4 Playwright** on the same exact source SHA. Existing real Uvicorn/SQLite guided Save/HTML/legacy PDF, immutable revision comparison and mounted evidence handoff remain green. **New fourth case** opens actual Deliver on a disposable project, authors a dirty narrative, then injects a **simulated** Tauri IPC bridge into Chromium only after normal app mount. It checks that native consent is called, no route/importer changes before approval, duplicate pending click does not create a second command, Stay preserves authored text, an approved stale request after explicit draft reset does not navigate, and a fresh approval opens the real importer. Browser API writes/remote origins remain blocked, and synthetic backend reports and Quality history stay unchanged.
- Historical [#42156201682](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42156201682), [#42156405532](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42156405532), [#42156554627](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42156554627) **FAILED** because two pre-existing P1 source-regex contracts assumed the old synchronous `navigateWithDockGuard=(view:View)` signature. Their assertions were updated to preserve the original safety intent under the new asynchronous parameters in [`643a70e9`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/643a70e9cd81df8e467b15f2dc0a8f43a17bbe97) and [`0e1cf774`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0e1cf774930e63d78de22e0197ea0f37ba3c6b0b). Do not relabel those intermediate failures as passes; the final green shared frontend run is authoritative.

## Still untested and exact owner-native acceptance request

**OWNER NATIVE WINDOWS WEBVIEW2 VISUAL/KEYBOARD: PENDING, NOT FAILED, NOT PASSED.** The successful simulated IPC test is not a real Rust GUI dialog observation. A developer must NOT claim a full native consent fix is visually approved from compilation or Chromium.

When an **already isolated disposable synthetic project in the full main Tauri shell** is available, the owner should verify these limited observations without loading a personal dataset or overwriting files:
1. Open **Deliver** and enter a short unsaved synthetic note. Confirm the unsaved draft warning appears.
2. Click the actual shell **Explore** rail item. The **native** modal should present **Leave Deliver / Keep editing**. Choose **Keep editing**. The report note, selected evidence, current Deliver view and route must remain unchanged.
3. Repeat with shell **New project** and choose **Keep editing**. No importer should open now or after later ordinary Home navigation.
4. Repeat a shell navigation and explicitly choose **Leave Deliver**. Only then should the requested workspace become active. Check standard keyboard focus and one-prompt-per-action behaviour.
5. Optionally repeat on an edited saved revision in the same synthetic project, again rejecting unsaved destructive navigation by default. Record observable screenshots and any native errors separately.

Do not run the older **P2 native live export-only** test window as a substitute: it mounts `ReportWorkspace` without the full `UnifiedShell`, so it cannot certify these navigation entry points. No new native QA BAT or isolated full-shell launcher was introduced here; these are owner-facing observations for the next controlled native setup. If any result fails, keep its exact failed step and diagnostic evidence in QA Issue #2.

## Remaining P2 release gates

Native routes outside the scoped shell handler remain as noted above. Normal mixed-script Unicode PDF remains **NOT_ACCEPTED**, with `RELEASE_APPROVAL_STATUS='NOT_GRANTED'`, pending independent review of the exact three original unchanged Noto binaries, their three full original SIL OFL notices, RFN/face choice and six final release SHA-256 pins. No release font copies, installer, training or service changes were authorised by this work.

**P2:** ACTIVE / REVIEW_REQUIRED. **P8:** NOT CERTIFIED.
