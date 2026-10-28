# PilotODIN Playwright browser QA — isolated pilot

**Status:** new source only. Owner Windows Playwright execution and screenshots/trace **pending**. This is not a production desktop, installer or hardware validation.

## Safety contract

- `playwright.config.ts` starts **a new frontend-only Vite server** at **127.0.0.1:5187**, with `reuseExistingServer:false`. It does **not** attach to the owner's existing live `:5173` browser.
- Each test uses a fresh Playwright browser context. The tests populate only invented in-memory profile data and temporary `localStorage` for the isolated `:5187` origin.
- Every HTTP request to the normal `127.0.0.1:8000/api` backend is intercepted and fulfilled inside the test. Every unmocked API **write is blocked** with a synthetic 403 and recorded, and unexpected API reads return a test-owned synthetic 404. All other non-frontend network origins are blocked.
- The synthetic `synthetic_upload.csv` is generated in memory using `setInputFiles({buffer:...})`. Do not import existing owner CSVs or start the actual Python backend for these tests.
- Never bypass the native unsaved-field confirmation by pressing **OK** during a test. The pilot checks **Cancel** only.
- `test-results/` and `playwright-report/` must remain gitignored; traces can reveal screen contents, so never upload traces from a live project.
- The browser test supplements existing unit/contract tests; it does **not** replace owner manual acceptance or prove native/offline release readiness.

## Installation and commands (Windows, in `frontend`)

The owner already installed `@playwright/test` and downloaded Chromium on their Windows machine. **The local edits to `frontend/package.json` and `frontend/package-lock.json` must be committed deliberately before running Playwright in CI.** These files were not modified by the GitHub source-only browser QA increment to avoid overwriting the owner's npm-generated lock.

```powershell
npx playwright test --config=playwright.config.ts
```

Expected first pilot: two tests, one for empty-catalogue onboarding and one for a synthetic Quality/Prepare dock with a **Cancel before upload** interaction. Browser assertions inspect the real mounted React UI and ensure that **zero backend writes** were attempted. A failed first run is an actionable browser fixture/flow defect, not a reason to switch to the owner's existing real project.

For a single focused test when diagnosing:

```powershell
npx playwright test e2e/isolated-workspace.spec.ts --config=playwright.config.ts
```

The dedicated port **5187 must be free**; if it is occupied, `reuseExistingServer:false` makes the test fail safely rather than connect to an unknown application. Stop only the process you actually recognise, or choose a separately reviewed test port.

## Known limitations and next gate

1. The Playwright tests have been authored against the live GitHub source, but have **not yet been executed on the owner's Windows PC**. Before calling this pilot accepted, confirm 2/2 execution and no unexpected requests; diagnose any failure from the actual trace without modifying real data.
2. Do not automatically enable GitHub Actions for Playwright until its npm dependency and lockfile are committed, the test passes locally and workflow changes have been reviewed for cost/data isolation.
3. Current tests intentionally avoid P2 PDF, ML training, quality approvals, AI calls and desktop packaging.
4. The tests use a CSS selector for the embedded target choice because the existing target `<label>` is not associated with a form control. Fix this as a separate accessibility increment if desired; then improve the locator to use the label.
