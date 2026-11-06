# PilotODIN P2 | Native dirty Deliver tab-close consent

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** P2 ACTIVE / REVIEW_REQUIRED; P1 CLOSED for bounded development; P8 installed offline Windows release NOT CERTIFIED.

## Source-confirmed inconsistency

The full `UnifiedShell` already routes dirty Deliver exits initiated by the shell rail, header New project, direct Studio commands and external same-document URL changes through the one-use `confirm_native_deliver_exit` Tauri command. However, the **Close Deliver tab** button called `close(view)`, whose active dirty primary Deliver branch still required synchronous browser `window.confirm`. The browser prompt is not accepted as reliable physical Windows WebView2 native consent; tab close could remove the active report and its authored draft after a mismatched prompt.

This is a confirmed code-path discrepancy, **not** a demonstrated owner Windows data-loss incident.

## Bounded implementation

- [Production source `d8b08bbfcb23`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d8b08bbfcb230c7535acd02d72fde8a98d5724cf) changes `frontend/src/UnifiedShell.tsx` only. Closing the **active dirty Deliver tab** with another fallback tab available now requests the existing native main-window Rust `confirm_native_deliver_exit` command, `Leave Deliver / Keep editing`, instead of `window.confirm`. No Rust code or new native command.
- The tab list, view, saved report, focus and route remain unchanged while native IPC is pending. A second tab click while a native Deliver dialog is open is ignored. A Keep reply or IPC error keeps the draft and gives a visible warning on failure.
- An approval can be used **once** and is ignored if the Tauri window unmounts, project ID, active view, URL hash, dirty Deliver marker, tab signature, dock target or ticket changes while the dialog is open. The native-approved continuation **reruns** the existing dock dismissal/promotion guards before changing the tab list, staging next-route preapproval or navigating. The existing focus-restoration plan remains.
- A clean Deliver close, closing an inactive tab and non-Tauri/browser confirmation retain previous behaviour. This is not a wholesale conversion of unrelated dock prompts or project-switching logic.
- No user or synthetic report revision was saved/deleted by this change. No backend/SQLite API, Quality history, model resource, Unicode PDF or font/OFL asset, installed app or installer modified.

## Exact verification

- [New focused behavioral tests `8c309ba4f4db`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8c309ba4f4dbc08bf5a59a1aae381d0b2f2b20cf) in `frontend/tests/p2-native-deliver-tab-close.test.cjs` transpile and execute the **actual production `close` callback**. They verify native Stay, explicit Leave tab/focus plan, duplicate pending click, stale project/view/hash/dirty marker/tab signature/dock/ticket, failed IPC, clean/inactive tab, nonnative browser fallback, and the independent edited-dock veto. They contain no storage or backend mutation.
- [P2 focused CI #42186129345](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42186129345): **COMPLETED SUCCESS, 97/97 Node tests and TypeScript/Vite production build**, tested source/workflow SHA `decbf5aab3151decd5d25539a59726ff50bd9901`.
- [New real browser test `8517ef9a462f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8517ef9a462fb17906db7e00846658ce12dd1bb7) adds a seventh disposable FastAPI/SQLite + Chromium scenario. It mounts the real full-shell Deliver with two saved workspace tabs and an authored synthetic unsaved note, injects **simulated native IPC after React mount**, clicks the rendered **Close Deliver tab** button, verifies repeated click cannot bypass the pending prompt, Keep preserves report and route, and a later fresh Leave closes Deliver and opens Explore. Synthetic reports/Quality history remain unchanged; browser writes and remote origins are prohibited.
- [Final shared frontend #42186216164](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42186216164): **COMPLETED SUCCESS, 160/160 Node, production TS/Vite build, 5/5 isolated Chromium**, exact application/test SHA `8517ef9a462fb17906db7e00846658ce12dd1bb7`.
- [Final P2 real HTTP #42186216068](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42186216068): **COMPLETED SUCCESS, 7/7 Playwright** against a disposable owned FastAPI+SQLite backend with Chromium, same SHA `8517ef9a462fb17906db7e00846658ce12dd1bb7`. The prior six real P2 routes remained green.
- [Cross-phase isolated frontend before test-only browser addition #42186076939](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42186076939) and [initial real HTTP 6/6 #42185935034](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42185935034) were also completed successfully at earlier application code. The final tests above supersede their acceptance for this increment.

## Owner-native requirement remains open

Linux Chromium simulating a Tauri IPC callback and a successful Rust compile do not demonstrate a real Windows dialog, keyboard focus, accessibility or Narrator behaviour. The isolated full-shell Windows owner QA entrypoint remains `Run_PilotODIN_P2_Native_Deliver_Consent.bat` with its original five mandatory owner-observed items in [the owner acceptance guide](./P2_NATIVE_DELIVER_OWNER_FULL_SHELL_QA_2026-11-06.md). An **optional sixth** observation now documents Close Deliver tab Keep/Leave; it does not change the five-item QA questionnaire or imply a physical pass.

Dock-specific confirmation and other outstanding native acceptance remain separately tracked. Unicode PDF release status remains `NOT_GRANTED/NOT_ACCEPTED` pending independent exact approval of three original unchanged Noto fonts, three complete OFL notices, six final SHA-256 pins, RFN/face and distribution-notices treatment. P8 installed release remains **NOT CERTIFIED**.

**Next:** Run the existing isolated owner Windows native launcher once and provide actual modal/focus evidence; do not replace this with more mock-only passes. If owner hardware/evidence is unavailable, choose a genuinely remaining in-phase requirement with a real acceptance path, without invoking unapproved fonts or broadening scope.
