# PilotODIN Macro A4 — Deliver evidence composition and professional exports

**Development milestone:** A4-1 selected-model evidence, A4-2 aggregate illustrations, A4-3 Quality audit and export-integrity safeguards.  
**Current status:** SOURCE IMPLEMENTED, LOCAL TEST EXECUTION PENDING. Do not call A4 complete or the Windows installed application release-ready.

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
