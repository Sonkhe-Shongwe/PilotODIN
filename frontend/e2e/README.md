# PilotODIN Playwright browser QA — isolated pilot

**Status (28 Oct 2026):** The owner's Windows screenshot confirms **5/5 previous isolation Node tests PASS** and **TypeScript/Vite build PASS** (Vite 6.4.5, 1,636 modules, 2.60s; familiar nonfatal 533.61kB warning). The first two Playwright browser cases **both executed and FAILED** only on their final network audit: `GET https://fonts.googleapis.com/css2` was correctly blocked and recorded. This fixture-only patch is newly authored, with two additional Node cases; the corrected browser suite and new Node tests are **not yet executed**. No desktop, installer or hardware validation is implied.

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

1. The owner executed both Playwright tests on Windows: **0/2 PASS** in their first run due to the blocked Google Fonts CSS import. The new synthetic stylesheet stub and added Node safety regressions have **not yet been executed**. Before calling this pilot accepted, confirm corrected **2/2 browser PASS**, and no unexpected requests or writes. Diagnose remaining failures from test-owned traces only, without modifying real data.
2. Do not automatically enable GitHub Actions for Playwright until its npm dependency and lockfile are committed, the test passes locally and workflow changes have been reviewed for cost/data isolation.
3. Current tests intentionally avoid P2 PDF, ML training, quality approvals, AI calls and desktop packaging.
4. A React `useId`-backed visible label now identifies the target control in primary and embedded Prepare views; the test selects it by accessible role/name scoped to the dock, not its CSS class. This does not constitute a full Issue #7 accessibility audit.
5. `tests/p1-playwright-pilot-contract.test.cjs` now contains seven cases (five previously Windows-green; two newly authored for the precise font exception and denial of all other font requests). Its mocked request checks do not substitute for real Playwright browser execution.
6. Exact next commands from `frontend` after safely pulling: `node --test tests/p1-playwright-pilot-contract.test.cjs` then `npx playwright test --config=playwright.config.ts`. The existing production build was already Windows-green for unchanged application code, so **do not repeat it for this test-fixture-only revision**.
