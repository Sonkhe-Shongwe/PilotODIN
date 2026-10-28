# PilotODIN Playwright browser QA — isolated pilot

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

**Bounded corrective change:** The synthetic project now returns version-0, schema-compatible, invented responses for those four read-only Explore GETs and `/explore/saved`. The real Explore workbench uses HTTP **POST** for a read-only, immutable snapshot calculation; without a precise exception, the new GET fixtures would expose a second failure. The route handler therefore allows **only** `POST /projects/playwright-synthetic-project/explore/workbench` with an exact validated synthetic payload (version 0, no filters, two allowed columns, safe chart configuration). This request is fulfilled entirely by the browser fixture, recorded in `audit.readOnlyCalculations`, and **never forwarded to the real backend**. All other POSTs (including project uploads, saved analyses, modified/malformed workbench bodies and model/Quality operations) still return synthetic 403 and enter `audit.writes`; unknown GETs or external requests remain rejected and audited. Three newly authored Node tests cover GET response shapes, approved synthetic calculation and denied variants. The existing per-browser zero-write and zero-unknown-origin assertions remain in place. No product, backend, CI, dataset, local AI, training or installer changes.

**Only next Windows acceptance gate**, after safely pulling, from the existing `frontend` folder:

```powershell
node --test tests/p1-playwright-pilot-contract.test.cjs
npx playwright test --config=playwright.config.ts -g "browser Back and Forward preserve"
```

Expect **10 authored contract tests** (previously 7 accepted and 3 new or revised; this revision's full result PENDING) and **one corrected browser-history test PENDING**. Do not repeat historical Vite build, 41/24/49 suites or three already accepted browser scenarios on unchanged application source. The first history test failure remains recorded. This validates only ordinary Back/Forward on unrelated routes; a cancelled dock-promotion history rollback and primary unsaved drafts remain separate OPEN tasks.
