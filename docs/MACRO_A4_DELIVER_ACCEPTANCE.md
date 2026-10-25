# PilotODIN Macro A4 — Deliver evidence composition and professional exports

**Development milestone:** A4-1 selected-model evidence, A4-2 aggregate illustrations, A4-3 Quality audit/export integrity, A4-4 native Save As source implementation.  
**Current status:** FULL A2/A3/A4 AUTOMATED INTEGRATION PASS on clean commit `4b555d93`: 106/106 frontend, 167/167 backend, frontend build and syntax checks. A4 INTERACTIVE/DESKTOP ACCEPTANCE REMAINS OPEN.

## Post-fix full A4 consolidated Windows automated verification: PASS (25 October 2026, approximately 11:06 SAST)

The owner supplied the second, post-fix single diagnostic ZIP (`pilotodin-p0-a4-readiness-mrmk7kls.zip`) and its `result.json`, all four phase logs and Pytest JUnit XML were examined.

- **Exact tested code:** clean `feature/live-dev-workspace-20261023` checkout at `4b555d934ba7f6d3012141e1e3b53138590fb863`; `uncommitted_changes=false`; no missing prerequisites.
- **All four phases PASS:** 106 of 106 frontend Node behavioural tests, TypeScript/Vite production build, Python syntax compilation, 167 of 167 combined A2/A3/A4 backend regression tests (0 failed, 0 errored, 0 skipped).
- Pytest reports `167 passed` on the post-fix run. The earlier Quality audit privacy wording false-positive has been corrected and now passes as part of the suite.
- `automated_status=PASS`, `preflight_blockers=[]`, with isolated `PILOTODIN_HOME`. This closes the **automated A4-1/A4-2/A4-3 integration gate** at this specific commit, superseding the earlier 166/167 result.
- **Scope boundary:** These runs are not independent visual QA, real user Prepare→Train→Predict, on-screen PDF pagination inspection, Tauri native Save As, bundled Qwen/offline operation, real 8 GB stress test, installer or the original E-01 through E-24 release acceptance. Those remain open and must be evaluated separately.
- **Decision:** Do not ask the owner to rerun unchanged tests. Proceed to one short combined A2/A3/A4 functional/visual acceptance session, prioritizing report composition, model/Quality/Explore evidence, saved revisions and readable HTML/PDF. Native Save As is still a separate known implementation/verification gap.

## Owner's first complete A4 consolidated Windows run (25 October 2026)

**Executed against clean checkout `f9c122448e01af61f4aacf31c4229c27bb54ea6e`.** Owner supplied the generated single diagnostics ZIP `pilotodin-p0-a4-readiness-s_9yn_ur.zip`, including `result.json`, phase logs and pytest JUnit XML.

- **Frontend:** 106/106 Node tests passed; TypeScript typecheck and Vite production build passed.
- **Backend:** Python compile passed; 167 collected Pytest cases: **166 passed, 1 failed, 0 errors, 0 skipped**.
- **Only failure:** `tests/test_a4_quality_audit_reporting.py::test_explicit_quality_capture_is_read_only_and_reportable`, which asserted the substring `preview` was absent from the string representation of all report evidence. The correct privacy disclaimer literally says "No record-level values, row identifiers, source previews ... are exported," triggering a **false-positive assertion** even though the preceding checks verified absence of synthetic private category strings and actual `preview` fields in the persisted audit. PDF/HTML checks later in that same test did not execute because the assertion stopped the test.
- **Fix committed:** `53db533921ac2b4c5b08bd8056cf6e9f6d851c93` changes the test to assert absence of an actual `preview` result field and `row_values` key, not the harmless word in an explanatory sentence. No product or source-data change was necessary.
- **Status:** Previous A4 source has been executed, with 166 cases passing. Full green A4 automated verification remains **PENDING one post-fix execution**; do not claim the edited test or full suite passed on the new commit. Native Windows Save As, physical 8 GB, bundled inference and complete manual PDF/UI acceptance are still untested.

## Combined report revision 3 — real HTML/PDF review (25 October 2026)

Owner supplied `pilotodin_report (1)(1).html` and `pilotodin_report_e598f981d064_rev3.pdf` from insurance project `insurance_claims_CLEANED`. Report ID `e598f981d06446968e98df1db8a2fe40`, **revision 3**, content SHA-256 `9fc5f6ab39c65ec21a7e1ac791af4020fb2505ac8ac40b39b5aecbbd17cdb97c`.

**Verified against the actual artifacts:** Both formats include the three distinct ordered v0 exhibits Quality Audit → Model Evaluation (`logistic_regression`, target `fraud_reported`) → saved Explore Snapshot. Quality evidence records 1,000 rows/39 columns/9 findings/0 active corrections. Selected-model held-out metrics match across formats: accuracy 0.82, macro F1 0.73776, ROC AUC 0.81619, 200 observations. Class `Y` recall **0.53061** is a material qualification, not a production guarantee. The chart's seven values (MD 60540, PhD 60145, Masters 58200, JD 57505, High School 57300, College 56080, Associate 54200) and figure render in HTML SVG and PDF vector output; no obvious clipping was observed. PDF is **5 pages** with awkward heading/table splits.

**Semantics issue discovered:** saved Explore objective/title is `Claims by region` but recorded chart parameters are `aggregation=median`, `x=insured_education_level`, `y=total_claim_amount`. This is NOT claims by geographic region and NOT a sum. The exported chart is numerically sourced correctly but must explicitly state its aggregation and true grouping field.

**Immutability:** The old captured Quality audit includes the legacy 'first 35 findings' disclaimer despite having only 9 findings; it was already frozen before the later conditional wording fix. Do not mutate the original saved audit or revision to hide historical wording. A fresh explicit audit capture is needed if current wording is desired.

**Source fixes committed after inspecting rev3:**
- `backend/report_charts.py` derives `measure_caption` from the existing immutable chart settings, so the HTML SVG figure caption/y heading and PDF chart heading show **Median of total_claim_amount by insured_education_level** (and histogram always states Frequency).
- `backend/reports.py` now uses `KeepTogether` on compact exhibit headings+metric tables and compact verified observation tables, avoiding orphaned Model/Explore section headings and one-row fragments.
- New regression `tests/test_a4_mixed_report_pagination.py` exercises a synthetic three-exhibit PDF/HTML; `tests/test_a4_frozen_chart_visuals.py` asserts median/grouping and histogram labelling. New test included in `tools/Verify_P0_A4_Readiness.py`.

**QA boundary:** The provided real rev3 HTML/PDF predates the last targeted code refinements, and there has been **no new executable local 106/167 suite run or post-change PDF render**. Thus mixed evidence presence/value parity is a **functional PASS**, but final A4 visual/pagination acceptance and native Tauri Save As remain OPEN. No changes to uploaded data or pre-existing saved revisions. User-authored generic report title and empty narrative should be improved for a professional final report.

## A4-4: Tauri native Windows Save As — SOURCE IMPLEMENTED, COMPILATION AND WINDOW TEST PENDING (25 October 2026)

**Environment distinction:** The owner has so far tested the browser dev workspace at `http://127.0.0.1:5173` using Chrome. A Chrome browser download is not the native desktop Save As workflow. The native path below is selected only when the React view is hosted inside a Tauri desktop WebView.

- `frontend/src-tauri/Cargo.toml` adds official Tauri 2 `tauri-plugin-dialog` on the Rust side only. Registered plugin and custom `save_report_as` command in `frontend/src-tauri/src/lib.rs`. No JS dialog/fs plugin permission was added to `capabilities/default.json` (still `core:default`).
- On the desktop path, the existing authenticated local API first returns a previously saved, validated report revision as HTML or PDF. The frontend passes the bounded blob to the native command. The command checks a maximum size of **12 MiB**, safe filename, declared format and HTML/PDF signature before opening an OS-native Save As dialog.
- The native dialog runs in a blocking worker instead of the UI event loop. A user **Cancel** results in explicit `cancelled` state, with no file written. If a path is chosen, only that dialog-selected path may be written; no arbitrary path is accepted from JavaScript. Filename extensions must match the actual report format.
- The Rust command verifies written file length **and SHA-256** against original bytes before returning `saved`. Filesystem/write/digest errors return an explicit error, not a success notice. Browser mode retains existing authenticated blob download behavior.
- Rust unit tests cover accepted PDF/HTML signatures, rejected format/extension combinations, unsafe relative path and filename characters, blank/oversized contents. Node static integration gates added in `frontend/tests/a4-native-report-save-contract.test.cjs` and updated browser/native split checks in `frontend/tests/a4-quality-export-gates.test.cjs`.
- **Verification limit:** The official Tauri dialog method has been checked against upstream documentation, but this session has **not compiled Rust on Windows**, launched a Tauri desktop WebView, opened the native dialog, cancelled it, written an actual PDF, or tested overwrite/disk-denied behavior. The repo has no tracked `Cargo.lock` in `frontend/src-tauri`; the first native Cargo run may require resolving packages. The existing browser-only Node/Pytest automated gate does NOT compile Tauri/Rust.
- **Native acceptance:** In an actual running Windows Tauri development build (not Chrome), choose an existing saved report, click Export PDF and Export HTML, confirm native Save As opens, save under chosen names/locations and compare file bytes/figures; repeat Cancel and observe no file creation; verify failed permissions or incorrect extension give an error. Then separately inspect the latest page-break/chart fixes and reopen/reorder saved revisions.
- Installer creation, bundled AI, real 8 GB hardware testing and release certification remain out of scope of this A4-4 source implementation.

## A4-5: One-pass native Windows feasibility/acceptance launcher — SOURCE READY (25 October 2026)

- **One-click entry:** `Run_PilotODIN_A4_Native_Smoke.bat`, launching `tools/Verify_A4_Native_Windows.ps1`. A transparent preflight stops early on missing Windows Rust MSVC 1.90+/Cargo/npm, unavailable local `/api/health`, wrong feature branch or occupied development port 5174. Official Tauri Windows development also needs C++ Build Tools/SDK and WebView2. The runner does not auto-install tools.
- **Development shell only:** `frontend/src-tauri/tauri.native-a4-smoke.conf.json` overrides normal bundling, sidecars, bundled GGUF/resources and app identifier for a **non-release** Tauri window. Native frontend runs at localhost 5174; current live backend is localhost 8000; Chrome localhost 5173 remains usable.
- **Explicit debug switch:** `frontend/src/desktopBootstrap.ts::isNativeA4SmokeMode` requires both Vite DEV and `VITE_PILOTODIN_NATIVE_SMOKE=1`, allowing only this test window to use the already-running dev backend instead of an unavailable packaged sidecar. Normal production session-authenticated backend behavior is unmodified.
- **Automation:** run the entire existing A2/A3/A4 local regression suite on a clean isolated test home before Tauri compilation. If green, run `npm run desktop:dev -- --config src-tauri/tauri.native-a4-smoke.conf.json`; the user actually exercises native PDF, HTML and cancel behavior and records observed results after closing the window. Collect logs, test JUnit/results and manual notes in one `pilotodin-a4-native-*.zip`, excluding all datasets and model files.
- **Node static gates:** `frontend/tests/a4-native-smoke-runner.test.cjs` checks that the bypass is DEV-only, bundle override cannot silently replace release config, and runner does not invoke installer or AI staging.
- **Status boundary:** New runner, overlay and debug switch were committed and read back from the repository, but **have NOT been executed** in Windows, nor has a Rust build/UI/dialog been observed. Even if native dev compilation passes, this does not validate production packaging, offline AI or integrated 8 GB runtime.
- **Instructions:** [Native one-pass validation](./A4_NATIVE_WINDOWS_ONE_PASS.md). The owner should run this **once**; if blocked on prerequisites or compilation, share the same diagnostic ZIP, allowing code or environment triage without repeat manual report generation.

## Baseline preserved

- Existing reports, reports_v1/report_revisions_v1, version-scoped Explore and investigation evidence, and immutable HTML/PDF exports remain in place.
- Approved immutable dataset version rules, guarded Quality approvals and A3 train/evaluate/held-out selection are unchanged.
- Source files and user projects remain untouched. No new Windows installer or bundled inference changes.

## A4-1 additions

1. Completed A3 model evaluation becomes a project-scoped selectable report source **only after** a ready model has been selected and its held-out evaluation was durably recorded.
2. A model exhibit freezes target, task, selected model, split, development metric context, held-out aggregate metrics and bounded class diagnostics. **It never embeds individual held-out evaluation rows, model binary, source files or raw feature data.** Regression MAE/RMSE/R² remain distinct from classification accuracy/F1.
3. Existing reports can combine model evidence, saved Explore snapshots and investigation evidence from different dataset versions. Selected exhibit order is preserved in immutable revisions.
4. Report editor adds up/down ordering controls, disabled export while the saved draft has unsaved changes and a warning about historical versions.
5. HTML and PDF both provide an evidence register and per-artifact limitations/interpretation notes. Renderers use the same saved revision and `_exhibit` representation; actual numerical parity still requires executable regression evidence.

## A4-2: Frozen Explore visuals in PDF and HTML (source implemented, not yet runtime-tested)

- New `backend/report_charts.py` builds bounded, presentation-only **bar, histogram and line** vector illustrations from saved Explore `chart.data` aggregates. It does **not** query the dataset, rerun filtering/statistics, or infer a new finding. Scatter/box remain table-only pending a carefully scoped release design; row-level scatter pairs are **not visualised by this feature**.
- `backend/reports.py::_explore_evidence` stores a compact chart visual projection **inside the immutable report revision** only after validating the saved Explore snapshot SHA-256 and its configuration binding. HTML and PDF both render from that same frozen projection.
- Chart scales include zero with a visible negative/positive baseline where necessary. Histogram counts are read from the original saved bins, not re-binned, and no percentages or invented trendlines are added. Original numeric exhibit tables and SHA-256 provenance remain visible.
- To keep PDF pages readable, charts are limited to 12 bars, 24 histogram bins or 18 line categories, with explicit 'bounded subset' disclosure where truncated or sampled. Visual labels are abbreviated for legibility; the saved evidence table remains the numeric reference. Source-label HTML is escaped and no scripts/networks are used.
- The A4 HTML/CSS report adds print-friendly vector chart figures and per-chart captions. PDF drawings are vector objects rather than raster screenshots.
- New `tests/test_a4_frozen_chart_visuals.py` validates bar, histogram and line source parity, unsupported plots, nonfinite rejection, markup escaping, bounded-data notices, and old report immutability after a source snapshot is altered. Included in unified local verification.
- **QA status:** GitHub source committed and re-fetch review pending/ongoing. No A4-2 Python/PDF renderer tests or end-user Windows visual validation has yet been executed.

## A4-3: Explicit Quality audit, revision integrity and export safety (source implemented, runtime pending)

- `POST /api/projects/{project_id}/report-quality` accepts `expected_version` and **only reads** the pinned approved working dataset. A button in Deliver explicitly captures the audit; viewing reports never silently creates one. The backend returns 409 if the working version changed.
- Each capture freezes a bounded SHA-256 verified snapshot in `report_quality_audits_v1` containing dataset/issue counts, currently active approved corrections, short approved-version event, and up to 35 finding summaries. Fields are limited to issue kind, column name, severity, affected-row count, review status, and **fixed explanatory phrasing**.
- No source rows, preview rows, individual identifier values, user category examples, proposed replacement values, or raw approval receipts enter the snapshot. Capturing the audit **never approves, changes, undoes, or restores working data**. Existing Quality approval receipts and explicit human review rules are untouched.
- Only audits belonging to the active project and passing stored SHA-256+version binding can become report evidence. Historical captures stay attached to their original dataset version and are flagged when the project advances.
- Saved **report revisions themselves** now have SHA-256 integrity validation before any reload or HTML/PDF export. Tampered saved data returns 409 rather than being presented as verified.
- Report download helper checks HTTP Content-Type, PDF/HTML file signatures and safe extension before triggering browser download; it reports download **started**, not confirmed written. A native Windows Save As dialog is **still untested and not claimed implemented**.
- Added `tests/test_a4_quality_audit_reporting.py`: explicit capture, unchanged source bytes/version, category-example privacy, cross-project rejection, altered audit exclusion, historical-v0 retention and altered-report rejection. Added `frontend/tests/a4-quality-export-gates.test.cjs`. The unified local verification runner includes the new backend module.
- **Status:** source committed to development branch; no new A4-3 or earlier A4-1/A4-2 executable tests have yet run on the owner's Windows system.

## Consolidation source audit and single-owner-run gate (25 October 2026)

- Strengthened `reports.load`: a correct SHA-256 is **necessary but insufficient**; the frozen snapshot must also belong to the owning project and preserve the expected bounded evidence/version structure before it can reopen or export. Added a regression proving even a validly hashed foreign-project revision is refused (409).
- Upgraded `Run_PilotODIN_P0_A4_Verification.bat` to keep its terminal open after a double-click. `tools/Verify_P0_A4_Readiness.py` now emits one shareable ZIP with JSON/JUnit/phase logs only, intentionally omitting the isolated data and model directories. The ZIP path is printed at both PASS and FAIL.
- **A4-1/2/3 source is frozen for the initial consolidated automated Windows check.** Every A4 regression module is in the single-pass runner; existing A2/A3 regression checks and TypeScript/Vite compilation remain in the same run.
- **Unverified:** Neither the new code, PDF figures nor native browser/desktop export behaviour has passed the owner's local executable suite. First run is required before final A4 feature claims.
- **Still a blocker to full A4 acceptance:** Native Windows Save As remains unimplemented/unverified in this source checkpoint. Browser download checks do not solve native shell integration; keep that explicit instead of calling A4 released. PDF pagination and final functional UI validation also remain open.
- One owner action: pull the latest development branch once, run the one-click BAT, send the generated **single diagnostics ZIP**, inspect failures and fix code before considering any repeated manual clicking. Windows manual QA should follow only after the automated regression set passes.

## Test inventory and gate

- **New:** `tests/test_a4_model_evidence_reports.py`: incomplete model exclusion, project access control, safe aggregate metrics, HTML/PDF parity, frozen revisions after experiment mutation, correct regression metric labelling, ordered evidence and reliability notes.
- **Existing:** `tests/test_build_e_persistent_reports.py`, `tests/test_report_exhibit_render.py`, `tests/test_explore_to_report_evidence.py`, `tests/test_build_e_cleaned_exports.py`, `tests/test_build_e_approval_receipts.py` plus relevant A2/A3 suites.
- **Single local runner:** `Run_PilotODIN_P0_A4_Verification.bat` includes the new A4 regression module, frontend Node tests and TS/Vite compilation with isolated `PILOTODIN_HOME`.
- **Do not use historical 99/149 pass results to claim new A4-1 source tests passed.** They predate this implementation.

## Acceptance criteria for the consolidated owner Windows session

Use disposable test data, and one pull/checkpoint **after a coherent A4 development batch**, not after each code commit:

- One selected, evaluated classification model shows up in Deliver evidence; pending/unselected/foreign model does not.
- Report with model + saved Explore + investigation shows exact dataset versions and selected ordering; create revision, reload and verify original revisions remain unchanged.
- Validate accuracy/F1 as fractions and per-class support; ensure source row-level predictions do **not** appear in either export.
- On regression, report MAE/RMSE/R² by their true meanings, not false accuracy.
- Preview professional HTML/PDF for narrative, line breaks, table readability, evidence register, actual numbers, provenance, reliable page breaks and safe special characters.
- Check saving altered exhibit order creates a new revision and export buttons stay disabled until unsaved changes are committed.
- Native Save As, accurate filename and cancel/error behaviour need explicit desktop-shell acceptance; development-browser downloads are not equivalent.
- A3 functional valid prediction/reopen and remaining A2 UI checks can be included in the same final owner session.

## Deferred A4 improvements before final macro signoff

- Beyond the initial saved aggregate graphics: scatter/box visuals, accessible long-category layouts, additional advanced analytical and model figures, and print-pagination refinements.
- Optional deeper Quality decision timelines and affected-row investigations as separate, explicitly approved, privacy-reviewed report evidence. The new Quality audit deliberately contains only aggregate findings.
- More advanced report narrative structure/layout design beyond the current title, interpretation, limitations and ordered evidence.
- True native Windows Save As implementation/verification, cancel and disk-write errors, and install/restart recovery tests. Browser download validation is not equivalent to a native Save As dialog.
- 8 GB + offline bundled AI and original E-01..E-24 release gates are separate, mandatory milestones.

## Product integrity

No silent data cleaning, report model inference or automatic interpretation. Export renders only previously saved evidence plus expressly user-authored narrative. Reports may intentionally compare versions, with explicit labels. If evidence is invalid or comes from another project, the backend refuses the report.
