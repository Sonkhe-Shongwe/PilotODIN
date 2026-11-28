# P2 mounted React report composer integration, browser-only and isolated

**25 October 2026 — initial real browser test FAIL (4/5, harness polling error); test-only repair committed, owner rerun pending.**

## Why this is the correct next gate
Earlier P2 controlled Save/Quality and Read Safety batches passed scoped TypeScript guard behavioral + Node source-contract + TypeScript/Vite tests. The latest read-safety repair BAT owner screenshot reports `P2 navigation contract repair: PASS`; its local ZIP is not uploaded, while the earlier initial ZIP has 24/25 Node PASS (the one stale regex repaired) and TypeScript/Vite PASS. **P2 read safety is scoped ACCEPTED**, not React DOM, full backend API/native Tauri, or offline release certification.

Accumulating more regex source assertions is not a substitute for testing actual UI behavior. This increment adds only a browser integration test surface, no production frontend/backend logic and no new npm/Python libraries.

## Exact isolated browser setup
- `frontend/p2_report_dom_test.html` with `frontend/src/p2ReportUITestHarness.tsx` mounts the **real** `ReportWorkspace` using `react-dom/client` in Chrome/Edge.
- The harness replaces page `window.fetch` with a fail-closed **synthetic local API** handler BEFORE rendering. It allows only mock requests targeting 127.0.0.1:8000; no actual API/real dataset/report request is issued. It returns static fake report, evidence and Quality state objects with controllable delayed `Response` values.
- `tools/Verify_P2_React_Integration_Local.py` uses existing local Node/npm/Vite and Chromium-based Chrome/Edge, not Playwright or Selenium and no `npm install`/`pip install`. Builds TypeScript/Vite first. Then selects an unused loopback port, starts Vite in a child process, runs Chrome/Edge **headless with a disposable temporary user-data profile**, `--disable-background-networking`, `--no-proxy-server`, and dumps the resulting DOM. It parses the page result and requires explicit **5/5** scenario PASS; nonzero browser exit, missing browser, timeout, missing DOM PASS, missing dependencies or failed build all produce FAIL rather than inferred success. Vite is terminated after test and files/logs live under one disposable temp directory.
- Existing PilotODIN backend (if already running) is **not** used or stopped. No source data is imported and no local user reports are saved. Fake API outputs are deterministic fixtures. Browser download anchor is spied on in the test, and stale exports must launch **zero** browser downloads.

## Five mounted React interaction scenarios
1. Open a saved report slowly, edit the title while its read is pending, resolve stale request, ensure the newer input survives.
2. Save a frozen report payload while title changes later; simulate post-commit report-list GET failure; verify newer input survives, API payload remains original, user sees that Save succeeded but refresh failed.
3. Capture a Quality audit while user edits evidence selection; verify newly recorded audit is **not** silently checked and shows a clear notice.
4. Resolve older project evidence GET after newer captured-audit refresh; verify captured audit remains in the displayed evidence list.
5. Start HTML export from saved report, switch project before binary GET resolves; verify no browser download click for superseded report.

## One focused Windows gate
`Run_PilotODIN_P2_React_Integration.bat` runs `tools/Verify_P2_React_Integration_Local.py`. Two clearly reported phases: TypeScript/Vite build, then **real mounted React DOM test in a local Chrome/Edge headless browser**. One `pilotodin-p2-mounted-react-*.zip` contains `result.json`, build log, Vite log, browser log and browser DOM test result (all synthetic). No previous P0/P1/P3/P4/P5 or standalone P2 tests rerun.

**Caveats and constraints:** Source/code inspection is NOT evidence this browser gate passes. Actual headless browser behavior and interaction reliability are currently PENDING Windows execution. An ordinary headless browser does not verify Rust/Tauri native Save As dialogs, real customer dataset import, real FastAPI error paths, offline licensed Qwen generation, combined 8 GB RAM or the final E-01–E-24 installer release. If Chrome/Edge automation fails due environment or test-harness timing, diagnose the ZIP before changing production code. Source changes in this increment are **test-only**, so do not modify production application to satisfy a faulty test.

**Next owner action:** Safely fetch/pull the feature branch, run `Run_PilotODIN_P2_React_Integration.bat` once; on red upload the one diagnostic ZIP, on green provide screenshot/ZIP for reliable observed acceptance. No downloads, hosted Actions, installer or high-RAM AI.

## First owner browser run and narrow harness correction (25 October 2026)

Owner supplied `pilotodin-p2-mounted-react-k_566u6b.zip` and a console screenshot. Actual ZIP `result.json` and four logs/DOM were inspected. Initial **TypeScript/Vite PASS**, isolated Vite up, browser exit 0, **mounted React 4/5 PASS**, overall **FAIL**. Four pass: Save/edit/refresh messaging; Quality capture after manual selection change; old evidence GET not replacing new audit; export after project change no browser download. The only failing test “Editing while older Open is pending” raised `report title input not mounted` immediately: its `until` callback called strict `titleInput()` *before* React's first mount, so the readiness condition threw rather than polling. **No evidence of a production Open race failure can be derived from that thrown test helper.**

**Committed test-only change** to `frontend/src/p2ReportUITestHarness.tsx`: first initial hydrated-title wait now uses optional `document.querySelector(...)? .value` lookup inside the existing poller (actual source uses `?.value` without whitespace). This allows React's asynchronous mount and initial report load to complete, while still failing on timeout if they never complete. No product source changed. **Corrected gate NOT RUN yet**. Owner must pull and rerun the existing `Run_PilotODIN_P2_React_Integration.bat` once; it builds TypeScript/Vite and runs five actual mounted browser scenarios. 5/5 plus build PASS would support the bounded synthetic-browser acceptance, not native Tauri/export or final release QA.

## Corrected owner-observed P2 browser acceptance, 25 October 2026

After the test-only readiness polling fix, owner screenshot clearly shows `frontend-typescript-vite: PASS`, `p2-mounted-react-dom: PASS`, `P2 mounted React integration gate: PASS`, and final success. Local diagnostic ZIP `pilotodin-p2-mounted-react-ll89w_k5.zip` was shown but not uploaded or independently read. This establishes **focused synthetic mocked-API mounted React browser acceptance**, not actual backend HTTP integration, native Tauri Save As, Qwen, RAM coexistence or installer QA. The subsequent test-only gate is specified in `docs/P2_REAL_API_INTEGRATION_ACCEPTANCE.md` and is not yet owner-executed.
