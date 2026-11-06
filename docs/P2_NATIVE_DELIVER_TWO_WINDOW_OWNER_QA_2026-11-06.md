# PilotODIN P2 | Native two-window external project selection QA

**Created:** 6 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**State:** TEST-ONLY SOURCE READY / WINDOWS NATIVE OWNER ACCEPTANCE **PENDING**.  
**Phase:** P2 ACTIVE / REVIEW_REQUIRED. P1 CLOSED bounded development. P8 release NOT CERTIFIED.

## Why this is separate from the completed five-step Deliver consent QA

The [five-item native Deliver shell consent](./P2_NATIVE_DELIVER_OWNER_FULL_SHELL_QA_2026-11-06.md) is **SCOPED CLOSED** based on owner screenshots and the final all-five `OWNER_REPORTED_PASS` PowerShell outcome. **Do not rerun it.**

The remaining P2 native cross-window question is narrower: when a *different* native window changes `pilotodin-current` while window A has an unsaved Deliver draft, A must keep its note and project and display a warning, without relying on browser `window.confirm` or treating B's selection as consent. The [source correction](./P2_NATIVE_DELIVER_CROSS_WINDOW_STORAGE_GUARD_2026-11-06.md) and eight actual owner Windows Node regression tests are already passed; **two real Windows WebView2 windows have not been observed** for that change. Tauri's documented multi-window configuration supports a separate URL per window, but native WebView storage/event delivery must still be measured rather than assumed.

## Added QA-only implementation (no production application changes)

- `Run_PilotODIN_P2_Native_Two_Window.bat` launches **only** `tools/Run_P2_Native_Two_Window_Local.ps1`. This is a non-installable, separately identified QA application.
- The PowerShell runner uses existing offline Python, npm/node_modules and Cargo; checks the correct feature branch, refuses occupied ports **8000 and 5177**, records the local Git HEAD/worktree status (if available), never resets owner changes, and uses a fresh `qa_foundation.py init` run.
- `tools/Seed_P2_Native_Two_Window_Local.py` uses only a newly allocated `P2-NATIVE-TWO-WINDOW-DELIVER-...` DevQA home to create exactly **two distinct, fixed four-row synthetic CSV projects**, A and B, with independent source SHA-256 checks. Never point it at your installed PilotODIN data.
- `frontend/src-tauri/tauri.p2-native-two-window.conf.json` uses a **distinct `com.pilotodin.p2twowindowqa`** app identity, no installer, no external binaries/resources, and two native windows on the same local Vite origin: `main` (actual existing read-only full UnifiedShell Deliver QA) and `qapeer` (one-button synthetic project selection). Normal production Tauri config is untouched.
- `frontend/p2_native_two_window_peer.html` and `frontend/src/p2NativeTwoWindowPeer.ts` mount only the peer. The button changes `localStorage['pilotodin-current']` to pre-seeded B **on explicit owner click**. There is no fake `StorageEvent`, no API write and no application state override. Native identity, localhost, development flags and exact A/B IDs are required.
- The original A QA entrypoint still prohibits browser mutations and remote network requests; only GET/HEAD to owned local FastAPI are permitted. Source integrity and backend access logs are checked after the native session. A **status-only ZIP** contains result/DevQA/fixture metadata, no source CSVs, narrative, logs, originals, images or model weights.
- New `frontend/tests/p2-native-two-window-devqa.test.cjs` contains five source contracts. **Local Linux Node v22.16.0 five/five PASS** on the newly committed helper/config/runner files (exact Git blob SHAs matched individually) and Python `py_compile` of the new seeder **PASS**. This is source validation, not integrated frontend `tsc`/Vite, a Windows PowerShell AST parser, two-window Tauri startup or evidence of real `storage` delivery. **No new CI was dispatched**.

## Owner procedure (single isolated run)

Close any older PilotODIN development QA sessions first. Use an updated local checkout of `feature/live-dev-workspace-20261023` while preserving any uncommitted owner work. From the repository root, launch **`Run_PilotODIN_P2_Native_Two_Window.bat`** once. It should compile with existing dependencies and open two windows: **A Dirty Deliver** (actual PilotODIN report workspace) and **B Selection Only** (small peer with a single button). If startup fails, stop and share the red console and printed status-only ZIP. Do not install anything, modify original datasets or turn off safety checks.

1. In window **A**, verify the synthetic project A is open in Deliver. Type a short distinctive disposable note in *Interpretation and limitations* and verify the unsaved warning.
2. In window **B**, click **Select synthetic project B in this window** once. Without clicking anything in A, verify A retains the **identical report text, Deliver route and synthetic A project**, shows the cross-window warning and does **not** display a browser/native consent dialog or switch projects. If A shows no warning at all, record **NO**; do not infer delivery just because the text stayed.
3. In A, intentionally choose synthetic **project B** from the normal **Switch project** dropdown. Confirm the separate **Switch project / Stay** native modal appears. Select **Stay** and verify project A and the unsaved text are still intact.
4. Again select B in A, this time approve **Switch project**. A must load only synthetic B after approval. The deliberately discarded unsaved A report is no longer mounted.
5. Close **B first**, then **A** (approve any ordinary native window-close prompt if needed). Answer all three truthful PowerShell prompts. Share the final console showing `dirty_external_veto`, `explicit_switch_stay`, `explicit_switch_approve`, and a screenshot of the cross-window warning if practical. The generated archive is status-only, and its presence does **not** certify an installed release.

## Acceptance gate and unresolved risk

- **Native two-window acceptance:** PENDING until actual physical Windows WebView2 observation, console outcomes and final process state. A source-level eight-test pass cannot replace this.
- If Windows WebView2 does not propagate this localStorage `storage` change across these windows, **record failure / not observed**; do not synthesize an event or edit project state to force a green result.
- This is an **additional** native project-selection safeguard, not a new product two-window feature, installer or release. Existing accepted five-step Deliver observation remains closed and is not reopened by test setup work.
- Optional dirty Deliver tab-close detailed acceptance, instrumented Narrator, original 3 Noto font binaries + 3 full original OFL notices + exact 6 SHA-256/RFN redistribution approval **NOT_GRANTED**, normal Unicode PDF **NOT_ACCEPTED**, and P8 offline installed product **NOT CERTIFIED** remain independently open.

**Next:** Observe this one narrowly scoped native two-window scenario on the owner's Windows system and document the actual result in this file, both authoritative handoffs and Issue #2. Avoid broad new feature work while acceptance is pending.
