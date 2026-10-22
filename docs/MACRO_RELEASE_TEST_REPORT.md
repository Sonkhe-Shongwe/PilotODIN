# PilotODIN v0.3 Macro Beta | Test report

## Scope

This release combines the prior v0.2B cleaning engine with interactive quality controls, exploratory visualisations, local facts assistant, cleaned-data ML integration, multiclass classification, feature risk screening, meaningful target-named prediction labels, version-aware experiment protection, and a Windows launcher.

## Verified in authoring environment

- **57 Python backend tests passed** using `python -m pytest -q` on 20 October 2026.
- Existing data-quality API tests remain passing: safe autopilot, approval, undo, restore, audit records, conflict protection, date-like fuzzy matching safeguards and overlapping issue suppression.
- New integration tests cover read-only chart endpoint variants, invalid chart requests, feature-risk screening, local assistant source labeling, corrections propagating into charts, clean-source integrity, model version pinning, staleness and rejection of outdated prediction requests, multiclass classification and cross-version restoration.
- Python module compile checks succeeded.
- All TypeScript/JSX source files passed TypeScript transpile **syntax checks**.
- TypeScript `tsc --noEmit` completed using temporary minimal type stubs because the npm registry was inaccessible. These stubs were removed from the release, and **this is not equivalent to a normal React/Vite production build**.

## Synthetic large-data benchmark

- Data: **100,000 rows x 50 numeric columns** containing integers in `[0,99]`.
- Generated CSV: ~14.5 MB.
- Upload: HTTP 201, ~1.1 seconds in this container.
- Quality endpoint: HTTP 200, ~1.12 seconds.
- Explore overview: HTTP 200, ~0.38 seconds.
- Histogram endpoint: HTTP 200, ~0.28 seconds.
- Insights endpoint: HTTP 200, ~0.42 seconds.
- These are one-run measurements on synthetic data in the authoring environment. They **do not prove performance for arbitrary CSV/XLSX datasets**, long text, categoricals, storage hardware, or ML training at that scale.

## Must still test on user Windows computer

1. `cd frontend && npm.cmd run build` with your installed React dependencies.
2. Launch with `Start_PilotODIN.bat` and confirm `http://localhost:5173` opens successfully.
3. Upload `examples/demo_quality_issues.csv` and inspect Data Quality, Explore and Ask ODIN.
4. Review, approve and undo a correction through the actual UI.
5. Train on the cleaned version, select a model, generate a context-named prediction.
6. Change data-quality version and confirm old model is shown as stale.
7. Verify existing saved v0.2B projects and model artifacts survived the patch.
8. Repeat representative smoke tests on real-world datasets.

## Known limitations

- No Windows executable installer. Launcher needs existing Python and Node.js.
- No connected LLM; Ask ODIN is deterministic and limited.
- No automatic domain-semantic data repair or validated feature-importance search yet.
- Training can be expensive for 100k×50; only upload, scan and EDA were benchmarked.
- Only random split currently supported, with explicit acknowledgment.
