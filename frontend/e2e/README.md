# PilotODIN Playwright browser QA — isolated pilot

**Status (28 Oct 2026): OWNER WINDOWS ACCEPTED, scoped pilot CLOSED.** Direct Windows PowerShell screenshot confirms **7/7 targeted Node contracts PASS** (380.7562ms) and **2/2 Playwright Chromium tests PASS** (7.3s, one worker) with the exact isolated font CSS stub. Previous first browser run **0/2 FAIL** on blocked Google Fonts CSS is preserved as historical fixture evidence, now corrected and validated. The existing TypeScript/Vite build PASS (Vite 6.4.5, 1,636 modules, 2.60s and nonfatal 533.61kB advisory) remains accepted because only test-harness/docs changed afterward. This does not certify desktop, real imports, fonts for P8, offline AI or hardware performance.

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
