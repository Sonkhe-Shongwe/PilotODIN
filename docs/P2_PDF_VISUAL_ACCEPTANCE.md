# P2 PDF Visual Acceptance: Synthetic Preview Gate

**Date:** 26 October 2026. **Status:** TEST-ONLY SOURCE COMMITTED; OWNER WINDOWS RENDER AND HUMAN INSPECTION PENDING.
**Branch:** `feature/live-dev-workspace-20261023`. Always verify live HEAD before changing it.

## Preserved acceptance

- P2 four-source mixed-evidence reporting: owner Windows **3/3 runner + 9/9 mixed PASS**, returned `REVIEW_REQUIRED` as intended.
- P2 disclosure and page-bound report QA: owner Windows **5/5 PASS**, returned `REVIEW_REQUIRED`.
- Separate synthetic native FastAPI-to-React-to-Tauri Save As exact HTML/PDF SHA gate already accepted for its development-only scope.
- No existing project, trained model, Quality approval, report revision, Tauri export or production renderer is being modified or retested in this increment.

## A. Problem, cause and the necessary visual boundary

Prior tests proved page dimensions and bounded extracted text rectangles, but cannot prove that a recipient can actually read the exported PDF, that glyphs appear correctly, or that lines/tables/charts are not visually overlapping or cut off. The current ReportLab built-in typefaces and vector chart labels are a source-level *font/geometry watch item*, not a reproduced defect until a PDF is rendered and inspected.

The smallest useful acceptance step is an offline, synthetic-only PDF and page-image generator using **the existing production `backend.reports.render_pdf`**. It must never read a real dataset or issue a training/API request. The result must remain `REVIEW_REQUIRED` until a human/assistant inspects rendered pages.

## B. Risk-first design review

| Risk | Prevention and acceptance boundary |
|---|---|
| Real data accidentally included in uploaded diagnostics | Generator imports the already accepted in-memory synthetic fixture only; no project import or live API; status ZIP remains only `result.json` and `manifest.json` |
| Test-only previews confused with real customer reports | Every report title has a `SYNTHETIC P2 VISUAL DEVQA` marker; preview ZIP has synthetic-only instructions and its own provenance manifest |
| Hidden links or redirected QA output | Fresh `%LOCALAPPDATA%\PilotODIN\DevQA\runs\P2-PDF-VISUAL-...` via `qa_foundation.create_run`; reject existing redirected runs/archive paths and linked workspace/exports/manifest |
| Altered application home or startup behavior | Only worker child gets isolated `PILOTODIN_HOME` before any `backend` import; existing `.venv-live`, no package install |
| Unbounded memory, pages or preview size | Three named PDFs only, max 64 A4 pages and 8 MB per PDF, max 30 MB packaged preview, 1.5x raster scale on first/middle/last pages |
| User perceives geometric check as visual PASS | Scenario state `STRUCTURAL_PASS` only, overall `REVIEW_REQUIRED`. Text bounding boxes and output presence are insufficient for glyph, collision, aesthetics or print certification |
| Failures mask other failures | Parent reads a dedicated worker status file, archives only synthetic-safe status fields, classifies a scenario render exception as FAIL and import/workspace/diagnostics issues as BLOCKED |
| Preview uploaded without confirming provenance | Separate ZIP includes PDF/PNG SHA-256 manifest and fixed scenario names. Inspect archive member names, digests and source labels before accepting images |
| False security from accepted earlier tests | Do not rerun accepted 12/12 and 5/5 gates without a demonstrated impacted seam; full P2 product/P8 installed release still open |

## C. New files and generated scenarios

- `tools/p2_pdf_visual_devqa.py`, one fresh-run parent/child with safe file protocol.
- `Run_PilotODIN_P2_PDF_Visual_DevQA.bat`, uses already-installed `.venv-live\Scripts\python.exe`.
- Reuses `tests/test_p2_report_display_disclosure.py::report_fixture` without adding test methods or altering the accepted fixture.
- `standard.pdf`: four evidence exhibits, bounded chart and summary/row/finding/comparison notices, ordinary pagination.
- `dense.pdf`: twelve repeated synthetic exhibits, longer narrative and objectives, table/pagination stress.
- `unicode.pdf`: unusual character examples (`café`, `São Paulo`, `R²`, `Δ`, `Москва`, `漢字`, `₹`, `📈`), long labels, wrapping and finding text; report glyph-presence observations do NOT certify support.
- At most three sampled page PNGs per PDF (first/middle/last). **Full PDFs are included** in the preview ZIP for page-by-page review of all pages, not just sampled PNGs.

## D. Output contracts

The runner prints two distinct archive paths:

1. `P2-PDF-VISUAL-<run-id>.zip`: **status-only** diagnostics with exactly `result.json` and `manifest.json`. No PDF, PNG, original rows, user documents or worker raw logs.
2. `P2-PDF-VISUAL-<run-id>-visual-preview.zip`: explicitly **synthetic-only** offline review artifacts, including `standard.pdf`, `dense.pdf`, `unicode.pdf`, selected PNG pages, `preview-manifest.json` (filenames + digests) and `REVIEW_INSTRUCTIONS.txt`. Do not publish/attach this as customer evidence.

A structurally completed run returns `P2 PDF VISUAL DEVQA: REVIEW_REQUIRED`, not final acceptance. If a named report cannot render, PDF bounds fail or a fixture mutates, the relevant scenario is `FAIL`. If dependency/environment/provenance/ZIP creation fails, report `BLOCKED` and do not treat a partially generated preview as accepted.

## E. Acceptance method after the owner runs

1. Verify the uploaded **visual preview ZIP**, archive safety, allowed filenames and manifest SHA-256 values.
2. Render the original PDFs to images using a PDF renderer and inspect at least the first, representative interior and last pages of each. Inspect **every page** if issues or the page count warrant it.
3. Check: visually complete table rows, headers repeated sensibly, kept headings, warning visibility, paragraph wrapping, no content under footer, chart labels/captions not collided, no cut-off glyphs, reasonable contrast/legibility, and missing/substituted glyphs in the Unicode scenario.
4. Cross-check the PDF text extraction only as an aid, **not** the substitute for visual inspection; include screenshots or annotated failing page references if a defect is found.
5. Record findings as VISUAL_PASS, VISUAL_FAIL or VISUAL_REVIEW_REQUIRED **only for the three synthetic samples**. If a defect appears, identify whether it is font, paragraph, table or chart related. Plan one narrow, regression-protected renderer fix rather than changing unrelated reporting behavior.
6. Keep full native installed-app, real datasets and comprehensive 8 GB/P8 release assurances separate.

## F. Exactly one next owner action

Preserve any GitHub Desktop local changes, pull `feature/live-dev-workspace-20261023` and run **`Run_PilotODIN_P2_PDF_Visual_DevQA.bat` once**. If the run is `REVIEW_REQUIRED`, upload the **`-visual-preview.zip`** here so the PDFs can be inspected visually. If it reports `FAIL` or `BLOCKED`, provide the **status-only ZIP** and console screenshot; do not rerun blindly. Do NOT repeat the earlier 12-case, five-case or native Save As BATs.

## G. Final pre-execution source review (26 October 2026)

The test-only generator source was re-fetched following the initial commits. Two narrow, preventative checks were added before any owner execution: require the manifest run ID to match its fresh run directory, and require exactly the three PDF files plus the first/middle/last PNG filenames calculated from each PDF's recorded page count. The package refuses a missing, duplicate, unexpected or non-string filename before archiving; it cannot return a nominal review-ready result with an incomplete visual sample set. Malformed worker status is treated as incomplete/BLOCKED and both archive types have integrity checks. Worker phases and visual generation were reviewed statically, **not executed** in the owner's Windows environment. Final code refinements: `85e4a50c9bd5401443c3dafd5b82e0ba966fbec5` and `a7af5a60ce36baaf053a4286e9e1012cb6ed7ff4`. Those code changes do not touch the product renderer, previously accepted test packages or user data.
