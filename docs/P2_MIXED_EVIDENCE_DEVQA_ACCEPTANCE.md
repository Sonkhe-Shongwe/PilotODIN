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

## 26 October 2026: Owner BLOCKED ZIP, protocol diagnosis, and targeted repair

**Actual owner Windows run (NOT a product test pass):** `P2-MIXED-REPORT-20261026T115010Z-1b54e4ad95`. Uploaded status-only ZIP was independently inspected: exactly `result.json` and `manifest.json`. The archive is valid and both states are `BLOCKED` / `product_acceptance=NOT_TESTED`. Source preflight: zero findings, zero blockers. Contract stage: **3/3 PASS**. Mixed stage: **0 executed, count 0, no error or failed cases in the outer record**. The nine mixed cases were NOT executed. This does not invalidate the earlier accepted synthetic native Save As proof.

**Root-cause boundary established from the actual ZIP plus source:** The original parent read `json.loads(completed.stdout.strip())`. A malformed or absent single-JSON stdout result triggered a fallback dict `{state:BLOCKED,count:0,tests_run:0}`, discarding the child stdout/stderr and thus its error reason. The uploaded stage tuple matches that fallback. **We know the transport failed; we do NOT know from the archive whether the child exited unexpectedly, printed other stdout, failed to import, or failed to report.** Do not assert a report engine defect or install missing packages without further evidence.

**Focused test-tool correction (production files untouched):**
- Child workers now validate the fresh DevQA manifest/workspace and write a compact status-only `diagnostics/worker-contract.json` or `worker-mixed.json`. This is the authoritative parent protocol; stdout/stack/data bytes remain excluded from the diagnostic ZIP. Test discovery/import/fixture startup phases are classified using fixed labels, with the only persisted per-test details being test IDs, counts and states.
- Parent reads the dedicated file, fails closed when missing, corrupt, inconsistent with process exit or incomplete, records a bounded reason plus numeric return code and prints safe reason/test-case identifiers on BLOCKED. A genuine assertion failure remains FAIL; setup/discovery/import/skips remain BLOCKED. The final ZIP still contains ONLY `result.json` and `manifest.json`. No unreviewed raw standard output, traceback, row value or model result is archived.
- Existing 3 runner-contract test methods now verify the file protocol against missing/invalid/valid JSON and preserve archive-failure regression. Both mock temporary-fixture areas use `PILOTODIN_DEVQA_RUN/fixtures` when launched under the approved workspace; direct standalone pure-unit usage without DevQA environment retains ordinary OS temp for non-product fixtures.
- The existing 9 real mixed-report methods, `EXPECTED={"contract":3,"mixed":9}`, launcher `.venv-live` selection, source fixture and all application code are unchanged.

**Code commits:** `1667444c737dbd25989cc2d5a9db7eb6156b0f3e` worker status-file protocol; `def77b11f4a9c7b4d2a0713644cd2a505b774906` protocol regression; `8bc149b984b3a352ace7caa67b92b1176eff0095` contract temporary-fixture confinement; `8d2ff700844e6af9f715e5b278455eb8dc5ada5b` readable safe failure classification.

**Verification truthfulness:** Source changes were committed and re-review is required; **the repaired code has not been executed in the owner's Windows `.venv-live`**. No new mixed test PASS or P2 acceptance can be claimed. The next action is one pull of the existing feature branch preserving local uncommitted files, followed by one run of the SAME `Run_PilotODIN_P2_Mixed_Report_DevQA.bat`. On red, share the new status-only ZIP; the safe `MIXED REASON` and `ERROR CASES` printed in the console help without exposing private rows. On green, the scoped result is still `REVIEW_REQUIRED` because omission disclosure, PDF clipping and full release remain open.

## 26 October 2026: Second owner Windows run and contract fixture repair

**Owner evidence, independently inspected:** The uploaded `P2-MIXED-REPORT-20261026T120633Z-3e6996cd0d.zip` has a valid status-only `result.json` and `manifest.json`; status `BLOCKED`, `product_acceptance=NOT_TESTED`, source preflight zero blockers and zero findings. This time the improved per-worker protocol succeeded and isolated **contract stage 3 executed, 1 error**: `test_p2_mixed_runner_contract.RunnerContract.test_bad_counts_and_empty_are_blocked`. The mixed reporting stage did **not** start; none of the 9 report tests have passed or failed in this run. The ZIP records case IDs but no traceback.

**Narrow source diagnosis, locally reproduced:** In the first runner-contract method, the new status-file protocol test calls `worker_status_path(Path(tmp), "mixed")`, which resolves to `tmp/diagnostics/worker-mixed.json`. Its `TemporaryDirectory` provides only `tmp`, not the `diagnostics` subdirectory. After deliberately checking the missing-file condition, `status.write_text(...)` therefore raises `FileNotFoundError` before the remaining protocol assertions. This missing-directory behavior was independently reproduced in a disposable local Python temporary folder. Because the Windows ZIP intentionally carries no traceback, the exception type is independently source-proven rather than claimed directly from the uploaded artifact.

**Exact correction:** In `tests/test_p2_mixed_runner_contract.py`, immediately after the deliberate missing-file assertion, call `status.parent.mkdir(parents=True, exist_ok=False)` before writing the malformed and valid status samples. This changes **only the synthetic test setup**, preserving three runner-contract test methods and nine mixed-report methods. No runner, launcher, product API/renderer, environment, model, source data or release artifact was altered. Repair commit `051848075ef471974f7bc15af3b53fb3e411a0a5`.

**Validation boundary:** A standalone local temporary-path reproduction demonstrated the pre-fix `FileNotFoundError` and post-fix missing → invalid → valid file sequence. The **actual new Windows 3+9 suite has not been rerun**, so no PASS is claimed. Archive creation and source checks do not establish report acceptance.

**Next owner action:** Preserve GitHub Desktop uncommitted changes, pull the same feature branch, run `Run_PilotODIN_P2_Mixed_Report_DevQA.bat` **once**. If `BLOCKED`/`FAIL`, provide its fresh status-only ZIP for targeted correction. If both stages pass, expected overall state remains `REVIEW_REQUIRED` pending disclosure and PDF visual acceptance. Do not rerun previously accepted native Save As or expand scope.
