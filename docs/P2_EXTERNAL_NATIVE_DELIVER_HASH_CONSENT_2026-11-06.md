# PilotODIN P2 | External hash/history Deliver native exit consent

**Date:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Status:** P2 ACTIVE / REVIEW_REQUIRED. P1 CLOSED for bounded development. P8 installed offline Windows release NOT CERTIFIED.

## Source-confirmed gap

The accepted shell rail and direct Studio `App.go` P2 changes route dirty Deliver exits through the Tauri native `confirm_native_deliver_exit` consent. However `UnifiedShell`'s external same-document Navigation API `beforeRoutePush` and hashchange/history `reviewRoute` handlers continued to use synchronous `window.confirm`. A URL hash assignment, link or history traversal could therefore bypass the new **native** consent path or rely on an unreliable browser modal in WebView2.

This is a source-confirmed consistency and data-protection risk, **not** an owner-observed physical Windows loss incident. Existing external route safeguards for edited docks and non-Deliver forms must remain intact.

## Scoped production correction

- [`98a075b9699a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/98a075b9699aa596427748b8188de406353728d1) extends **only** two existing external route entry points in `frontend/src/UnifiedShell.tsx`.
  - On a cancelable same-origin Navigation API `push` from dirty Deliver, the handler cancels insertion of the unapproved history entry and invokes the existing one-use `navigateWithDockGuard(requested)`, which uses the native main-window Rust command. The route, report data and importer remain untouched until explicit Leave.
  - On a `hashchange`/history route event that has already changed the URL, the handler immediately restores the last accepted hash with `history.replaceState` and dispatches `pilotodin:route-reverted` to restore the primary Studio stage. It then invokes the same native guard for the requested workspace. A Keep/error/stale approval cannot unmount the dirty report. A fresh Leave uses the existing exact-route preapproval token and commits the intended route once.
  - Non-Tauri browser confirmations, edited-dock promotion, normal P1 route rollback and exact-hash duplicate-delivery logic remain. The nonnative Deliver fallback message now accurately uses `primaryExitMessage(active)` rather than the unrelated Prepare/Model/Predict Canvas warning.
- [`b4d237be3d47`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b4d237be3d47f0deb08c84e91ea60c14f7dbfc35) fixes a TypeScript-only narrowing error in the Deliver-specific fallback expression. This change does not alter the intended consent path.
- No Rust command, backend, database, model, PDF exporter, font file, licence, original project, Quality approval, existing report revision, OS installed app or installer was altered.

**Not addressed by this bounded route change:** external project selection or browser refresh/OS close, tab-close and dock input confirmation. They retain separate reviewed safeguards and distinct native acceptance requirements; this does not declare all navigation paths Windows certified.

## Actual test execution (source and hosted browser)

- New `frontend/tests/p2-external-native-deliver-route.test.cjs`, with actual TypeScript handler transpilation, verifies external URL navigation precommit cancellation and native delegation, postcommit URL rollback plus sync event and native delegation, one-use preapproved return without duplicate prompts, clean/unchanged route bypass, unchanged nonnative browser fallback and no data/network operations.
- New sixth `frontend/e2e/p2-real-http-report-comparison.spec.ts` scenario seeds exactly one disposable synthetic FastAPI/SQLite project and mounts the actual unified React Deliver UI. With a simulated native Tauri IPC bridge injected **after hydration** and strictly read-only browser API gate, it changes `window.location.hash` directly to Explore. It verifies that the native request is made while the URL stays/restores Deliver, the authored unsaved note remains, Stay never navigates, and a new direct hash to Overview followed by Leave reaches Home. Original synthetic reports and Quality history remain unchanged, without browser writes or remote requests.

**Exact final production/tested SHA:** [`b4d237be3d47f0deb08c84e91ea60c14f7dbfc35`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b4d237be3d47f0deb08c84e91ea60c14f7dbfc35).

| CI execution | Completed result |
| --- | --- |
| [P2 focused #42184235882](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42184235882) | **SUCCESS**, 88/88 Node and TS/Vite production build |
| [Shared frontend #42184235780](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42184235780) | **SUCCESS**, 160/160 Node, build and 5/5 isolated Chromium |
| [P2 real disposable FastAPI/SQLite+Chromium #42184235811](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42184235811) | **SUCCESS**, 6/6 Playwright, including new direct external hash case; previous five real P2 cases stayed green |
| [P1 cross-phase disposable backend+browser #42184235870](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42184235870) | **SUCCESS**, independent core P1 regression suite; does not reopen P1 scope |

**Intermediate CI truth:** [#42183845487](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42183845487), [#42183845474](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42183845474), [#42184057210](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42184057210), [#42184022520](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42184022520) and early source #42184133606 **FAILED**, due to TypeScript error TS2367 in a literal Deliver-only fallback comparison despite source behavior tests passing. The exact fallback was corrected, after which all four named final workflows passed. Those historical failures are retained as failures and must never be described as passes.

## Remaining real owner acceptance

This does **not** mean a real native Windows WebView2 dialog was displayed. The real-browser test injects a fake IPC bridge on Linux Chromium; it never runs Rust GUI. Owner-native main-shell **Leave Deliver / Keep editing** still requires deliberate visual and keyboard tests on a disposable synthetic project. The existing [full-shell owner BAT and five-step test](./P2_NATIVE_DELIVER_OWNER_FULL_SHELL_QA_2026-11-06.md) remains the primary gate. On that same QA project an optional additional test is to open dirty Deliver, type a synthetic note, then change the hash using a local same-origin dev link or browser navigation. Never navigate to arbitrary remote websites or use real data merely to exercise this guard.

Normal mixed-script Unicode PDF release remains **NOT_ACCEPTED / RELEASE_APPROVAL_STATUS=NOT_GRANTED**, pending independently approved unchanged original three Noto font files, three complete original OFL notices, exact six SHA-256 pins and face/RFN/distribution notice decision. P2 **ACTIVE / REVIEW_REQUIRED**, P8 **NOT CERTIFIED**.
