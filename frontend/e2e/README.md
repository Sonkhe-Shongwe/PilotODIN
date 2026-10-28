# PilotODIN Playwright browser QA — isolated pilot

**OWNER WINDOWS PRIMARY PREPARE UNSAVED DRAFT CANCEL GATE ACCEPTED (28 OCT 2026) — 42/42 NODE + BUILD + 1/1 CHROMIUM PASS:** Owner screenshots from the correct `frontend` PowerShell directory show focused `node --test tests/p1-primary-draft-switch-safety.test.cjs tests/p1-primary-project-load-approval.test.cjs tests/p1-external-project-transition-guard.test.cjs` **42 tests, 42 PASS, 0 fail, 0 skipped/cancelled, 512.9502ms**. `npm run build` (`tsc --noEmit && vite build`) **PASS**: Vite 6.4.5, 1,636 modules, built **3.69s**, main JS **535.34 kB** with existing nonfatal chunk advisory. Focused `npx playwright test --config=playwright.config.ts -g "primary Prepare unsaved target"` **1/1 PASS** using 1 worker (**4.8s** total; case **1.3s**, `isolated-workspace.spec.ts:434:1`). This closes **only** the synthetic two-project Cancel-before-switch regression for the primary Prepare target, keeping current selected project/URL/unsaved target with no unapproved writes or unexpected requests. The earlier first browser **0/1 FAIL (no native prompt)** remains documented as historical before-fix evidence. Application source fix `95297a4050cc2481b3aef162d0bb6d4e650a38c0` and seven focused Node tests are now accepted for this narrow behavior. **Do not infer all primary draft controls, cross-tab change, failed global project fetch, reload/close, WebView2 or other forms are certified**. Previously accepted P1 12/12 fake API, five other browser scenarios and route guard remain closed at their source checkpoints. **Next P1 family:** cross-tab/external project selection while *primary* Prepare/Model has unsaved edits, including Cancel without rewriting another tab's storage; avoid per-feature distractions or repeat accepted tests on unchanged source. No owner datasets, backend, AI/ML, fonts, CI, installer or other phases changed. P1 is still OPEN under owner one-phase policy.

**P1 PRIMARY PREPARE DRAFT SWITCH DEFECT: OWNER WINDOWS 12/12 FIXTURE CONTRACTS PASS, NEW BROWSER 0/1 FAIL; SOURCE PATCH PENDING ACCEPTANCE (28 OCT 2026).** Screenshot: `node --test tests/p1-playwright-pilot-contract.test.cjs` **12 tests/12 PASS, 0 fail/skipped/cancelled**, 548.3904ms; `npx playwright test --config=playwright.config.ts -g "primary Prepare unsaved target"` **1 FAILED** at `e2e/isolated-workspace.spec.ts:460`, `expect.poll(()=>prompts.length).toBe(1)` timed out after 8s, actual 0 prompts. Confirms missing **primary Prepare draft consent** before global project switch, not an unmocked API or a proven actual erase (later assertions were not reached). Production patch `95297a4050cc2481b3aef162d0bb6d4e650a38c0` adds a project-scoped in-memory primary draft indicator for native Prepare/Model/Predict form edits and chosen target suggestions, with **no form values persisted/transmitted**. Shell now combines primary and existing secondary-dock project-switch warnings into **one prompt** for global selector, direct Studio project load and pre-upload gating; Cancel returns before switching/upload, and direct Studio successful project read retires the primary marker only after fetch, preserving it on read failure. It intentionally does not claim all click-driven model controls, external cross-tab primary selection, window close/reload or invalid global-project fetch safety. Four pre-existing source-contract test files patched as needed; seven fresh targeted Node cases in `frontend/tests/p1-primary-draft-switch-safety.test.cjs` (UNRUN) cover guard semantics, single consent, no stale cross-project marker and source wiring. **Exact new-source Windows gates**, from `frontend` after safely pulling: `node --test tests/p1-primary-draft-switch-safety.test.cjs tests/p1-primary-project-load-approval.test.cjs tests/p1-external-project-transition-guard.test.cjs` then `npm run build` then `npx playwright test --config=playwright.config.ts -g "primary Prepare unsaved target"`. These revised-source results **ALL PENDING**. Earlier 12/12 Playwright fixture contracts and five accepted browser tests are separately CLOSED and must not be rerun without changed dependencies. No backend/dataset/ML/AI/CSP/installer/CI/package lock changes; P1 remains the single active phase until closure.

**OWNER WINDOWS P1 cancelled-promotion regression ACCEPTED (28 Oct 2026).** `node --test tests/p1-external-route-activation-guard.test.cjs`: **27/27 PASS**, 463.3798ms; `npm run build`: TypeScript/Vite **PASS**, Vite 6.4.5, 1,636 modules, built 5.45s, main JS 534.39kB with nonfatal chunk advisory; `npx playwright test --config=playwright.config.ts -g "cancelled dock promotion leaves"`: **1/1 PASS (8.9s, one Chromium worker)**. The focused test accepted the fix for the duplicate Explore history entry after native Cancel, including ordinary Back/Forward and a preserved edited Prepare dock in the synthetic project. The historical 0/1 failed run remains recorded below. Do not extend this scoped pass to Tauri/WebView2, non-cancelable traversal or older Navigation API browsers. The previous four Playwright tests, 11 Node isolation contracts and previous acceptance suites remain CLOSED without replay.

**Owner Windows fifth browser test: FAILED 0/1 (28 Oct 2026), real duplicate-history defect confirmed.** Attempting to promote edited Prepare by changing the location hash, then dismissing the native dialog, left a duplicated Explore entry: the first browser Back did not reach prior Quality. Root cause: `history.replaceState` after a committed hash push does not remove its entry. A **production shell fix** (commit `afc9258361753fc8b6440cc9e2745f2f57ab9b34`) now blocks a rejected, cancelable Navigation API hash **push before commit**, with a memory-only, one-shot consent token for approved pushes. Four new source-contract cases added (27 total). The older hashchange rollback remains protective when precommit cancellation is unavailable, but **older browser and history traversal behavior are not yet certified**. This source increment needs Windows **27 Node test**, **TypeScript/Vite build**, and **one focused fifth Playwright browser test**. None of these new-source gates are verified yet. Other accepted browser/Node suites remain closed.

**Owner Windows ordinary-history gate ACCEPTED (28 Oct 2026):** The corrected Explore fixture's 11 Node contracts passed **11/11 (543.7358ms)** and its fourth, focused Chromium ordinary Back/Forward test passed **1/1 (8.4s, one worker)**. This covers unrelated Quality/Explore hash history with an edited Prepare dock, not a cancelled dock-promotion or its history rollback. Historical first 0/1 fixture failure is retained below. Do not rerun these unchanged suites.

**Status for browser-history extension (28 October 2026): OWNER FIRST RUN FAILED 0/1** at the final unexpected-API-read audit because the Explore synthetic fixture lacked four metadata GET responses (and source review identified a fifth `/saved` request plus a read-only POST workbench calculation). Three source commits add version-consistent, invented responses for these five GET endpoints, a strictly validated synthetic read-only workbench POST, a narrowly scoped content-type CORS preflight and a browser wait for the resulting `2 of 2 records` readout. All requests remain trapped locally, and other POSTs/OPTIONS are blocked and audited. **New execution pending:** 11 authored Node contracts and the single corrected history browser test; the original three browser cases remain accepted. This is not a verified browser fix yet.

**Status (28 Oct 2026): OWNER WINDOWS ACCEPTED, scoped pilot CLOSED.**

**Responsive edited-dock pilot (28 Oct 2026): OWNER WINDOWS PASS, scoped gate CLOSED.** One new targeted Chromium scenario at `isolated-workspace.spec.ts:190` passed **1/1, 5.8s, one worker**. It verified edited Prepare target retention on narrowing to 680px and widening to 1440px with test-only API/network audit empty. This supplements the earlier accepted 2/2 Chromium scenarios and 7/7 Node contracts; it does not certify native desktop resizing or full P1. Direct Windows PowerShell screenshot confirms **7/7 targeted Node contracts PASS** (380.7562ms) and **2/2 Playwright Chromium tests PASS** (7.3s, one worker) with the exact isolated font CSS stub. Previous first browser run **0/2 FAIL** on blocked Google Fonts CSS is preserved as historical fixture evidence, now corrected and validated. The existing TypeScript/Vite build PASS (Vite 6.4.5, 1,636 modules, 2.60s and nonfatal 533.61kB advisory) remains accepted because only test-harness/docs changed afterward. This does not certify desktop, real imports, fonts for P8, offline AI or hardware performance.

## Safety contract

- `playwright.config.ts` starts **a new frontend-only Vite server** at **127.0.0.1:5187**, with `reuseExistingServer:false`. It does **not** attach to the owner's existing live `:5173` browser.
- Each test uses a fresh Playwright browser context. The tests populate only invented in-memory profile data and temporary `localStorage` for the isolated `:5187` origin.
- Every request to `127.0.0.1:8000/api` is intercepted. All attempted writes return synthetic 403 and are recorded; unexpected GETs return 404 and are recorded. Unexpected origins/paths are blocked **and recorded**, as are non-GET/HEAD requests to the Vite UI origin. Both browser cases assert zero attempted writes, unknown reads and unexpected-origin traffic. Blocking alone is not counted as a pass.
- **Known, narrowly stubbed font request:** `studio.css` imports Google Fonts Inter/Manrope. The browser harness fulfills only an exact `GET https://fonts.googleapis.com/css2` query for those existing weights and `display=swap` with an **empty local test-owned CSS response**. Thus no Google request actually leaves the browser; rendering falls back to installed fonts during E2E. The stub is recorded in `stubbedFontStylesheets`. Other Google/font endpoints, altered families, POSTs and all unrelated external requests remain blocked and audited. This does **not** solve the separate offline-production typography/font-licensing readiness gap for P8.
- The synthetic `synthetic_upload.csv` is generated in memory using `setInputFiles({buffer:...})`. Do not import existing owner CSVs or start the actual Python backend for these tests.
- Never bypass the native unsaved-field confirmation by pressing **OK** during a test. The pilot checks **Cancel** only.
- `test-results/` and `playwright-report/` must remain gitignored; traces can reveal screen contents, so never upload traces from a live project.
- The browser test supplements existing unit/contract tests; it does **not** replace owner manual acceptance or prove native/offline release readiness.

## Installation and commands (Windows, in `frontend`)

The owner already installed `@playwright/test` and downloaded Chromium on their Windows machine. **The local edits to `frontend/package.json` and `frontend/package-lock.json` must be committed deliberately before running Playwright in CI.** These files were not modified by the GitHub source-only browser QA increment to avoid overwriting the owner's npm-generated lock.

```powershell
npx playwright test --config=playwright.config.ts
```

Expected corrected pilot: two tests, one for empty-catalogue onboarding and one for a synthetic Quality/Prepare dock with a **Cancel before upload** interaction. Browser assertions inspect the real mounted React UI and ensure **zero backend writes** were attempted. The previous run's only visible browser assertion failure was the expected Google Fonts CSS request; the new local font CSS stub does not relax other isolation rules. A failure is actionable fixture/flow evidence, not a reason to use the owner's actual projects.

For a single focused test when diagnosing:

```powershell
npx playwright test e2e/isolated-workspace.spec.ts --config=playwright.config.ts
```

The dedicated port **5187 must be free**; if it is occupied, `reuseExistingServer:false` makes the test fail safely rather than connect to an unknown application. Stop only the process you actually recognise, or choose a separately reviewed test port.

## Known limitations and next gate

1. The first browser run was **0/2 FAIL** on the blocked Google Fonts CSS import; after the isolated synthetic stylesheet stub, the owner ran the corrected suite **2/2 PASS** and the targeted contract tests **7/7 PASS** on Windows. Both cases assert an empty audit for attempted backend writes, unexpected API reads and unapproved external origins. These are two synthetic frontend flows only, not comprehensive P1 or native/offline testing.
2. Do not automatically enable GitHub Actions for Playwright until its npm dependency and lockfile are committed, the test passes locally and workflow changes have been reviewed for cost/data isolation.
3. Current tests intentionally avoid P2 PDF, ML training, quality approvals, AI calls and desktop packaging.
4. A React `useId`-backed visible label now identifies the target control in primary and embedded Prepare views; the test selects it by accessible role/name scoped to the dock, not its CSS class. This does not constitute a full Issue #7 accessibility audit.
5. `tests/p1-playwright-pilot-contract.test.cjs` now contains seven cases (five previously Windows-green; two newly authored for the precise font exception and denial of all other font requests). Its mocked request checks do not substitute for real Playwright browser execution.
6. **Next dependency-custody task:** Owner reviews and commits together the actual Windows npm-generated `frontend/package.json` and `frontend/package-lock.json` containing `@playwright/test`, via GitHub Desktop. The remote repository versions still lack that dependency. Do not fabricate or replace the lockfile, do not enable CI yet, and do not repeat the now-accepted 7/7 and 2/2 gates on unchanged code.

## Next new browser acceptance: responsive edited dock

The two original scenarios and seven isolation Node contracts are already **owner Windows PASS**, and must not be rerun on unchanged source. The **third synthetic Chromium scenario is owner-verified PASS (1/1, 5.8s)**. It begins with Quality primary and Prepare edited to `fraud_reported`, narrows the viewport to 680px, verifies the edited dock is hidden but still mounted and the preservation notice is visible, widens to 1440px, and requires the target/project/Quality primary to remain unchanged with zero attempted backend writes or unexpected network traffic. This is a targeted test of the already implemented `ResizeObserver`/responsive layout; it changes no product code and stores no draft field values.

From the existing Windows `frontend` directory after a safe feature-branch pull, run **only**:

```powershell
npx playwright test --config=playwright.config.ts -g "edited Prepare dock pauses"
```

**Historical acceptance command only.** This new scenario is **accepted** from owner Windows evidence; do not rerun on unchanged code. If it fails, diagnose its test-owned trace and exact narrow-width behavior, not real projects. The previously green 2/2 Playwright pilot, 7/7 Node and Vite build remain closed.

**CI status:** GitHub remote HEAD `632ae1f09c740e8dbd68861061ff9dc2e1f1949d` contains the owner-reviewed Playwright dependency `@playwright/test ^1.64.1` and npm lockfile. The existing `.github/workflows/frontend-compile.yml` is only on the active feature branch; `main` currently has only `live-dev-backend-tests.yml`. GitHub's usual `workflow_dispatch` UI requires a workflow on the default branch, so a new manual browser workflow added only to this feature branch would not yet be runnable through that UI. Do not modify `main`, enable CI triggers, run installers, or assert cloud CI acceptance without separate authorization and workflow review.

## New P1 browser-history discovery gate (authored, not executed)

A **fourth Playwright browser test**, `browser Back and Forward preserve an edited dock across unrelated routes`, now tests ordinary real Chromium hash history with an edited secondary Prepare target. It begins on Quality primary, selects synthetic `fraud_reported`, navigates to unrelated Explore through `window.location.hash`, performs actual browser **Back** to Quality then **Forward** to Explore, and checks the rendered primary heading, original dock field, same project, and strict no-write/no-unknown-network audits at each stage. Only synthetic `:5187` storage/projects are used, and all backend calls remain intercepted.

**Exact new Windows gate** after safely pulling the feature branch, from the existing `frontend` directory:

```powershell
npx playwright test --config=playwright.config.ts -g "browser Back and Forward preserve"
```

**Expected: one authored test; outcome PENDING.** The accepted earlier 3 Chromium scenarios, 7 Node contracts and production build do not need repeating on unchanged source. If this test fails, review its test-owned trace and determine whether the issue is route rendering, browser history, or a fixture assumption before making any production change. **Important limitation:** this tests ordinary Back/Forward for unrelated routes only. History behavior specifically *after a rejected navigation rolled back with `history.replaceState`* remains a distinct OPEN regression to design and verify; no claim that it is solved.

## 28 October 2026: Explore history fixture correction (pending owner rerun)

**Observed first Windows run of the fourth browser-history scenario: FAILED 0/1**, specifically the final `audit.unexpectedReads` check. Owner screenshot lists missing GET fixtures for `/explore/overview`, `/explore/insights`, `/explore/recommended`, and `/explore/filter-options`. Earlier route/headings/target assertions were not shown failing, but the screenshot does not independently certify their behavior. The error is consistent with synthetic fixture incompleteness; it does **not** establish a product navigation defect.

**Bounded corrective change:** The synthetic project now returns version-0, schema-compatible, invented responses for those four read-only Explore GETs and `/explore/saved`. The real Explore workbench uses HTTP **POST** for a read-only, immutable snapshot calculation; without a precise exception, the new GET fixtures would expose a second failure. The route handler therefore allows **only** `POST /projects/playwright-synthetic-project/explore/workbench` with an exact validated synthetic payload (version 0, no filters, two allowed columns, safe chart configuration). This request is fulfilled entirely by the browser fixture, recorded in `audit.readOnlyCalculations`, and **never forwarded to the real backend**. All other POSTs (including project uploads, saved analyses, modified/malformed workbench bodies and model/Quality operations) still return synthetic 403 and enter `audit.writes`; unknown GETs or external requests remain rejected and audited. Four newly authored Node tests cover GET response shapes, approved synthetic calculation, denied variants and exact JSON CORS preflight. No other preflight or POST is allowed. The existing per-browser zero-write and zero-unknown-origin assertions remain in place. No product, backend, CI, dataset, local AI, training or installer changes.

**Only next Windows acceptance gate**, after safely pulling, from the existing `frontend` folder:

```powershell
node --test tests/p1-playwright-pilot-contract.test.cjs
npx playwright test --config=playwright.config.ts -g "browser Back and Forward preserve"
```

Expect **11 authored contract tests** (previously 7 accepted and 3 new or revised; this revision's full result PENDING) and **one corrected browser-history test PENDING**. Do not repeat historical Vite build, 41/24/49 suites or three already accepted browser scenarios on unchanged application source. The first history test failure remains recorded. This validates only ordinary Back/Forward on unrelated routes; a cancelled dock-promotion history rollback and primary unsaved drafts remain separate OPEN tasks.

## Next separate P1 E2E gate: cancelled dock promotion and real Back/Forward

**Status: new test authored, NO Windows browser result yet.** The original four synthetic browser cases are owner-accepted (initial pilot 2/2, responsive 1/1, ordinary Back/Forward 1/1); the network isolation/Explore contracts have passed 11/11 on Windows. A fifth, distinct case `cancelled dock promotion leaves no duplicate browser Back Forward history` uses only the synthetic `:5187` project and mock API. Starting from Quality → Explore with an edited Prepare dock, it attempts to promote Prepare via the real browser hash, **dismisses** the native confirmation, then checks the URL and primary view reverted, edited secondary target survived, and browser Back goes directly to the previously accepted Quality entry (not a duplicate Explore entry) while Forward returns to Explore without another prompt. All unapproved writes, unknown reads and external origins must remain zero. This is a **regression/discovery test**, not a claim that current production history logic passes. It may expose an extra-history-entry defect in the current `history.replaceState` cancellation implementation; inspect the specific failing assertion before altering app behavior.

Only the new test should be run on Windows, after safe GitHub Desktop pull, from `frontend`:

```powershell
npx playwright test --config=playwright.config.ts -g "cancelled dock promotion leaves"
```

**Expected: one new browser case; result PENDING.** Do not repeat the four accepted Chromium cases, 11/11 Node contracts, production build or unrelated historical suites when source is otherwise unchanged. On failure, use the test-owned trace. Do not navigate or import the owner's actual projects, accept the dialog, create real training runs or enable CI.

## First P1 phase-focus development increment: primary draft switch discovery

One new **unexecuted** isolated Chromium case, `primary Prepare unsaved target requires Cancel protection before project switching`, now creates two fully synthetic project records in the mock-only `:5187` context. On the first primary Prepare form, it selects `fraud_reported`, then attempts to select the second project from the global selector. **Expected contract:** a native prompt is shown before discarding the primary form, the test always dismisses it, the original project and unsaved target survive, the URL stays on Prepare, and zero real API writes/unexpected requests occur. One additional Node case checks the *opt-in* second-project mock responses and the absence of any real project access.

**QA status:** Existing five Chromium scenarios and the earlier 11/11 isolation contracts remain historically accepted; the new sixth browser test and revised **12-case** Node contract suite are **AUTHORED ONLY, not executed**. The current shell's edit marker is secondary-dock-specific, so this browser scenario may intentionally expose an actual missing **primary** draft safeguard. Do not mark any product defect confirmed until Windows execution; if it fails, fix the real primary draft handling and verify the new-source TypeScript/Vite build and focused browser gate, not the owner's projects. No real dataset, backend, release fonts, ML/AI, CI or installer touched.

After safely pulling the feature branch while retaining local generated Tauri files, from `frontend` run only:

```powershell
node --test tests/p1-playwright-pilot-contract.test.cjs
npx playwright test --config=playwright.config.ts -g "primary Prepare unsaved target"
```

Expect 12 Node contracts and one new browser test, **outcomes PENDING**. Because production application code did not change, the previously accepted Vite build need not be repeated for this discovery. If the browser test fails, inspect its synthetic trace and distinguish missing consent from fixture failure.
