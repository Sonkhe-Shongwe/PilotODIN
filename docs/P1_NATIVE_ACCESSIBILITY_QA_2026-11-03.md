# P1 native Windows keyboard, focus and scaling QA

**3 November 2026. Status: isolated Windows Chromium automation SCOPED PASS; actual native manual matrix NOT RUN. Phase P1 only.** The native window, not a packaged release, is the manual subject.

## Setup and safety

- Use only the DEV ONLY Tauri smoke window on local port 5174, with one trusted Live Dev backend on 127.0.0.1:8000 already confirmed to store its data in the repository's .pilotodin-dev-data directory. Do not launch duplicates.
- Use a disposable project, not an original dataset. No transformations, exports, project deletion or AI workload.
- Preserve untracked frontend/src-tauri/Cargo.lock and frontend/src-tauri/gen/ and all local work. Do not run an installer or download a sidecar.
- Record each check as PASS, FAIL, BLOCKED/UNSUPPORTED or NOT RUN with the actual display scale. A visible default target does not establish an unsaved edit.

## Isolated Chromium automation, NOT native certification

Test-only commit 6be3a4cd54221ab7daea94170ae3cd03e0223ae3 adds three scenarios to frontend/e2e/isolated-workspace.spec.ts and a source contract in frontend/tests/p1-playwright-pilot-contract.test.cjs. They use only invented projects in an isolated Playwright context on :5187, intercept the entire network, reject and audit any unexpected API writes/reads and any external origins, and do not access the owner's browser or backend.

In frontend, after a safe branch update, run:
  node --test tests/p1-playwright-pilot-contract.test.cjs
  npx playwright test --config=playwright.config.ts -g "keyboard Tab Shift-Tab|keyboard dock resize|simulated 150 percent"

Expected scope: 19 authored Node contracts and three new Chromium scenarios. **Owner-executed 3 November Windows acceptance at branch HEAD `819440d93b`:** `node --test tests/p1-playwright-pilot-contract.test.cjs` **19/19 PASS**, 0 failed/skipped/cancelled/todo, 403.3099 ms; the named `npx --no-install playwright test ... -g` **3/3 PASS**, ~10.2 s. Screenshot-observed results, not native WebView2 runs. Native matrix below is still NOT RUN. A simulated 1.5 device pixel ratio is not real Windows 150% scaling or WebView2 acceptance. No production code changed.

## Windows native manual matrix

With Quality primary and Prepare docked on the disposable project, start at the current display scale (record what it is, do not assume 100%). Prefer keyboard keys over mouse when testing focus.

| ID | Action | Acceptance criterion | Current result |
| --- | --- | --- | --- |
| WIN-K1 | Tab from project switcher to New project and sidebar control; Shift+Tab backwards | Visible focus, no trap or inaccessible control | NOT RUN |
| WIN-K2 | Enter on expand/collapse sidebar; use arrow keys between Quality and Explore | Sidebar responds, current view and focus agree, no unexpected project change | NOT RUN |
| WIN-K3 | Keyboard-focus dock separator; press ArrowLeft, ArrowRight, Home, End, then Tab into dock | Resize within limits, visible focus, current target retained | NOT RUN |
| WIN-K4 | Temporarily narrow and widen native window with edited dock | Paused message or usable dock, hidden controls not tab-reachable, edit restored | NOT RUN |
| WIN-S1 | At original Windows display scale, inspect header/project controls and Quality/Prepare split | No clipped commands, unreadable text or broken keyboard focus | NOT RUN |
| WIN-S2 | Windows Settings > System > Display > Scale: try 125% if supported | Same controls usable, record actual resolution/scale | NOT RUN |
| WIN-S3 | Try 150% if supported, then RESTORE ORIGINAL SCALE | Same controls usable, record actual resolution/scale | NOT RUN |
| WIN-S4 | Try Win+Left or Win+Right snap | Content usable or explicitly report unsupported due to minimum window width | NOT RUN |
| WIN-A1 | With Windows animations off/reduced motion (only if available), inspect navigation and focus | No unnecessary motion or lost focus; record if unavailable | NOT RUN |

A development window may enforce a minimum width of approximately 1010 px, making half-screen snap impossible on some monitors. Report as unsupported, not PASS or FAIL. Do not claim Narrator or installed-app accessibility validation without a separate screen-reader test.

If automation fails, preserve exact failure summary and Playwright trace. Fix the underlying issue instead of weakening network, draft, or focus checks. Update the P1 closure register and Issue #2 only from observed evidence.
