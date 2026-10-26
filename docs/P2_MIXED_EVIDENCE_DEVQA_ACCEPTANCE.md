# P2 Mixed-Evidence DevQA Gate, Source and Acceptance Boundary

**Date:** 26 October 2026. **Development status:** TEST-ONLY SOURCE COMMITTED, owner Windows execution PENDING.  
**Branch:** `feature/live-dev-workspace-20261023`.  
**Source baseline:** `ac4fa2382e852db947302acda6b84afc9e322a92` before this documentation-only commit.

## Scope and what exists

A new independent P2 test-only launch path `Run_PilotODIN_P2_Mixed_Report_DevQA.bat` uses the existing `.venv-live\Scripts\python.exe`, `tools/p2_mixed_report_devqa.py`, **3 standalone runner contract cases** and **9 scoped synthetic reporting test cases** in `tests/test_p2_mixed_report_devqa.py`. It creates a new `%LOCALAPPDATA%\PilotODIN\DevQA\runs\P2-MIXED-REPORT-...` with its own `workspace` and disposable SQLite/projects. It never opens Rust/Tauri, contacts actual user projects, trains real ML, downloads packages or accesses Qwen/installer.

The real API is called via FastAPI `TestClient` after child process `PILOTODIN_HOME` is set to that run's disposable `workspace`, with real Quality capture, saved Explore, Investigation overview, synthetic-seeded selected evaluated-model projection, saved report revisions and actual HTML/PDF renderers. The synthetic model data are inserted using the existing stored-evaluation test contract. This is explicitly NOT evidence of actual model fit, inference or prediction quality.

## Focused acceptance cases currently implemented

| Case | Assertion and independent expected outcome | Acceptance scope |
|---|---|---|
| MR-01 | Four eligible project-scoped evidence types in declared order; 6-row independent oracle North 400, South 540, total 940; source SHA unchanged | API and snapshot integrity |
| MR-02 | Create report v1/v2; unchanged v1 SHA/content/order/HTML+PDF semantic texts after v2 | Revision immutability |
| MR-03 | Both formats show four types, essential regional numbers, selected-model fixture metrics and evidence IDs/limitations | Semantic parity, not separate PDF-byte digest |
| MR-04 | Private synthetic canary/holdout row marker absent from JSON/HTML/PDF; user-entered hostile narrative escaped | Basic report-data minimization |
| MR-05 | Cross-project, missing, duplicate and unselected/uncompleted model evidence rejected; no new saved report | Negative scoping |
| MR-05b | Corrupted saved Explore configuration is rejected; no report created | Bound source configuration |
| MR-06 | Unsupported scatter/invalid numerical visual not fabricated; 40-row table and 12-bar visual caps applied | Bounded mechanics; **reader-facing omitted-row disclosure NOT YET CERTIFIED** |
| MR-07 | Actual persisted report PDF opens as A4 and four evidence classes/important figures extract | Basic PDF integration, **not geometry** |
| MR-07b | Synthetic rendering-only 12-exhibit long mixed report produces multiple A4 pages with essential headings | Dense-pagination smoke, **not proof of no clipping** |

Three additional standard-library runner contract cases verify worker-count mismatch, missing, duplicate, errors/skips and real test-failure status cannot incorrectly become PASS. The outer runner enforces one current DevQA run, rejects linked QA run/archive roots, refuses a synthetic dataset outside `workspace/datasets`, does read-only Python compile preflight, and writes **one status-only ZIP** with result and manifest JSON. No source CSV, rendered HTML/PDF, prediction rows, customer data or test-generated dataset files are zipped. It captures per-case names/states, not potentially private assertion text.

## Final-state rules

- **REVIEW_REQUIRED:** all **9** real synthetic cases and all **3** runner-contract cases pass. This does **not** certify omission disclosure, visually proven zero-clipping, actual installed P8 or full P2 product acceptance.
- **FAIL:** one or more scoped tests fail with a real test assertion and diagnostic status.
- **BLOCKED:** worker discovery, fixture setup, missing dependencies, run/provenance checks, failure collection, test-count disagreement, or preflight fails. Do not claim product regression on setup failure without evidence.
- **Diagnostic archive failure:** show BLOCKED and the run folder / reason. Never promote a partially run test.
- **Testing limitation:** No dynamic Windows results yet at the point this source batch was committed. GitHub re-fetch and structural source checks are not equivalent to running a Python test.

## One owner action, only after pulling

On GitHub Desktop preserve untracked `Cargo.lock` and schema files; pull `feature/live-dev-workspace-20261023`. Run **`Run_PilotODIN_P2_Mixed_Report_DevQA.bat`** once.

No Save As dialogs should appear, no native app should be launched and no real project should be opened. The launcher creates a fresh DevQA run; if successful console prints `P2 MIXED-REPORT DEVQA: REVIEW_REQUIRED`, contract and mixed test counts and a single local ZIP. Send a console screenshot. If FAIL/BLOCKED upload the indicated ZIP (or screenshot if no ZIP). **Do not run earlier native Tauri export BAT** or old broad suites for this gate.

## Next engineering decision based on evidence

If a real MR failure occurs, distinguish a malformed fixture from a product defect and repair the smallest causal seam. Reader-facing truncation disclosure and dense PDF geometry remain on the P2 reporting plan even after green tests; only add a limited renderer fix on a reproduced test. Preserve all prior successes and historical failures in Master QA Issue #2.

## 26 October 2026: Pre-Windows source audit and diagnostic repair

**Status: source patch committed; no Windows test execution observed.** The four-source fixture was checked against the live `backend/main.py`, `backend/reports.py`, `backend/storage.py`, `backend/report_charts.py`, and `tools/qa_foundation.py` contracts. Confirmed compatible in source: FastAPI Quality capture, saved Explore sums and stored configuration binding, the investigation overview artifact, selected-model seeded projection through `storage.new_experiment/mark/select_model`, evidence resolution, revision save/read and HTML/PDF routes. The dataset oracle is independent of those API calculations (North 400, South 540, total 940); the 30 held-out observations and model metrics are intentionally synthetic seeded metadata, **not** real training on the six-row dataset.

**Confirmed runner defect, now narrowly corrected (test infrastructure only):** Previous `tools/p2_mixed_report_devqa.py` wrote a `REVIEW_REQUIRED` or `FAIL` status JSON and manifest *before* attempting the ZIP. If archive creation failed, the console reported `BLOCKED` but those on-disk records could still retain the earlier status, and a partial ZIP could remain. The runner now stages the status-only archive as `.partial`, publishes it only after completion, attempts to remove incomplete archives, and rewrites both status JSON and manifest to `BLOCKED` on a diagnostic failure. If disk I/O also prevents that rewrite, the console still clearly reports `BLOCKED` with a persistence-failure code; no successful archive is claimed. No production renderer, report API, dataset, model or release changes.

**Contract regression:** The existing three-test `tests/test_p2_mixed_runner_contract.py` suite now also simulates archive I/O failure with a temporary standard-library fixture and checks that both manifest and status JSON finish as `BLOCKED`, with no ZIP or partial archive. **This regression test is written but NOT YET EXECUTED in the owner's Windows `.venv-live`.** The number of test methods remains 3 contract + 9 mixed.

**Residual gaps and failure interpretation:** A missing `fitz`/FastAPI or other test prerequisite, a changed API, import/setup failure, inaccessible `LOCALAPPDATA`, workspace overlap or archive I/O failure is `BLOCKED`, not an assertion that reporting computations regressed. Even 12 green scoped cases give `REVIEW_REQUIRED`: omission counts/reader-facing truncated tables, true PDF glyph clipping and longer/odd text, full numerical/semantic parity beyond essential markers, native installed-app behavior, actual training and complete E-01 through E-24 acceptance remain open. The `report_charts.visual_spec` projection is reapplied during render and may lose the internal `limited` flag even while retaining a truncation note; this is a **source-level watch item**, not an executed product failure or permission to change reporting code without reproduction.

**Exact next action:** Pull the latest feature-branch HEAD preserving any local untracked changes, and run `Run_PilotODIN_P2_Mixed_Report_DevQA.bat` once using the existing `.venv-live`. Share the console result; if `FAIL` or `BLOCKED`, provide the status-only ZIP or the screenshot/run folder when archiving itself failed. Treat any genuine product regression separately from a fixture or diagnostic failure. No existing native Save As retest is needed.
