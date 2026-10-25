# PilotODIN Macro A4 — Deliver evidence composition and professional exports

**Development milestone:** A4-1, saved ML evidence and report composition.  
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

- High-quality chart illustrations and model graphics inside exported report pages (the existing release renders evidence tables and exhibits).
- Full Quality decision/affected-row artifact coverage where an immutable verified source record is not yet exposed.
- More advanced report narrative structure/layout design beyond the current title, interpretation, limitations and ordered evidence.
- Explicit native Windows Save As usability and install/restart recovery tests.
- 8 GB + offline bundled AI and original E-01..E-24 release gates are separate, mandatory milestones.

## Product integrity

No silent data cleaning, report model inference or automatic interpretation. Export renders only previously saved evidence plus expressly user-authored narrative. Reports may intentionally compare versions, with explicit labels. If evidence is invalid or comes from another project, the backend refuses the report.
