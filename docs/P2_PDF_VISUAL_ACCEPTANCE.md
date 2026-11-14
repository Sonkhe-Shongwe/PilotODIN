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

## H. First owner Windows generation run (26 October 2026): structural pass, visual inspection awaits preview

**Owner screenshot and uploaded diagnostic archive read directly:** Run `P2-PDF-VISUAL-20261026T133301Z-1585d963d1`. The uploaded file is `P2-PDF-VISUAL-20261026T133301Z-1585d963d1.zip`, the **status-only ZIP**, not the visual-preview ZIP. It passed ZIP CRC checks and contains exactly `result.json` and `manifest.json`. Manifest status is `REVIEW_REQUIRED` and `product_acceptance=NOT_TESTED`. Preflight: **0 blockers, 0 findings**; worker exit code **0**. Three scenarios returned **STRUCTURAL_PASS**: standard **8 pages**, dense **22 pages**, Unicode **7 pages** (37 pages total). Report remains `visual_acceptance=NOT_REVIEWED`.

**Important new watch item derived from the uploaded status JSON:** PyMuPDF extraction reported `unicode_preserved` true for `café`, `São Paulo` and `R²`, but **false** for `Δ`, `Москва`, `漢字`, `₹` and `📈`. This is evidence that these five exact strings were absent from extracted text, **not proof yet of exactly how the glyphs appeared on the rendered page**. The source uses ReportLab's default PDF font styles, so font coverage/substitution deserves a focused inspection. Do not modify fonts or claim a visual defect before seeing the actual generated PDF.

**Artifact still needed:** The diagnostic JSON records the separately created `P2-PDF-VISUAL-20261026T133301Z-1585d963d1-visual-preview.zip` and its SHA-256 `383f5a73c283604bd4de2cd3c705317fbd2abe44644bc17b395ec0f97b76a3b4`. That archive was **not uploaded**, so rendered pages, glyph appearance, chart/paragraph layout, table collisions and actual visual quality have **not** been inspected or accepted. The next owner action is to upload this **already generated** preview ZIP from the same DevQA archive directory, without rerunning any BAT. If the exact preview ZIP cannot be provided, do not claim review. Previously accepted 12/12 and 5/5 scoped suites remain accepted.

## I. Actual visual-preview ZIP received and rendered: VISUAL_FAIL (26 October 2026)

**Evidence verified independently, not inferred from text extraction:** Original uploaded `P2-PDF-VISUAL-20261026T133301Z-1585d963d1-visual-preview.zip` SHA-256 `383f5a73c283604bd4de2cd3c705317fbd2abe44644bc17b395ec0f97b76a3b4` matches the status-only diagnostic; ZIP CRC test passed. It holds the three complete synthetic PDFs, nine representative PNGs, preview-manifest and instructions. Every one of the 12 PDF/PNG member SHA-256 hashes matched the signed-off synthetic manifest entry. Actual PDFs were rendered and visually inspected across **all 8 standard, 22 dense, and 7 Unicode pages** using page contact sheets and detailed page views. Structural generation remains **3/3 STRUCTURAL_PASS**, but **visual acceptance is VISUAL_FAIL** due to the two concrete defects below. No customer data is present.

**Confirmed visual defect #1, Unicode replacement/substitution (open):** On page **1** of `unicode.pdf`, Greek source `Δ Ω` appears in the extracted text as `∆ Ω` (different code points); Cyrillic `Москва`, CJK `漢字`, rupee `₹` and emoji `📈` visibly show black squares or incorrect placeholder glyphs in narrative and table output. This is independently observable in rendered page 1, not merely a text extraction issue. The PDF uses ReportLab Type1 Helvetica, Symbol and ZapfDingbats fonts (WinAnsiEncoding), which do not provide full script and emoji coverage. Latin samples `café`, `São Paulo`, and `R²` visibly survive. **No Unicode production font fix has been committed:** the repository currently includes no font assets. A controlled decision on open-licensed bundled Unicode TTF/OTF assets, script fallback, deterministic embedding and emoji/unsupported-glyph behavior is required before changing fonts; avoid machine-dependent Windows Fonts paths or shipping font assets without reviewed licenses. The title and disclosure text are otherwise legible.

**Confirmed visual defect #2, chart heading orphan (narrow production repair committed, Windows rerun pending):** In `standard.pdf`, page **2** contains `Saved chart visualization` but the actual chart `Sum of Revenue by Region` and its limitations are on page **3**. The same separation occurs in `unicode.pdf` pages **2/3**. Three dense chart instances at pages **3, 10, 17** already keep title, drawing and limitations together. This is a real poor page-break result caused by adding the title paragraph separately from the fixed-height vector drawing. In `backend/reports.py::render_pdf` the chart heading, chart and limitations are now grouped within one `KeepTogether` (commits `9c35d0991e5909fb45fc2f43db6ac0b10c212098` then `736fcfbd9dcaaea1bd430fa401d6af8c715fd60a`). No chart values, saved evidence, revision schema, HTML renderer, font or user data has changed. The isolated `tools/p2_pdf_visual_devqa.py` now requires chart heading, `Sum of Revenue by Region` caption and `Chart limitations:` to be on the **same page** for the expected 1/3/1 synthetic chart instances (commits `697cd09669138f727054537383c0186555161b61` and `c2449d5e285984988f49fadfdcf5c3aaeaaeef18`). These changes are **source committed only; not yet verified on Windows**.

**Other actual visual observations:** Across the preview contact sheets the 30-row finding/40-row observation/50-row comparison tables continue coherently across pages; display-limit notices appear within page content; the A4 footer remains visibly outside report body. No general page-bound clipping, repeated content collision or invisible chart was apparent at contact-sheet and selected full-page resolution. This is a scoped synthetic observation, not exhaustive customer-data or print-printer validation. The standard layout has substantial blank space where the chart moved to the following page; the targeted keep-together layout intentionally prioritizes non-orphaned headings over dense pagination.

**Exact next acceptance action:** Keep overall P2 at `REVIEW_REQUIRED` and the *current actual* PDF visual sample at `VISUAL_FAIL`. After pulling the latest feature-branch code, run only `Run_PilotODIN_P2_PDF_Visual_DevQA.bat` once to validate the changed pagination seam and provide the new synthetic `-visual-preview.zip` for visual confirmation. It is appropriate to repeat this **affected visual generator only** because its renderer and acceptance assertion changed. Do **not** repeat the previously accepted 12/12 mixed-evidence or 5/5 disclosure suites unless a specific wider regression emerges. The Unicode font issue will remain open until properly designed, implemented and visually accepted; a green structure check alone cannot close P2.

## J. Owner Windows chart-pagination rerun and independent visual inspection (26 October 2026)

**Uploaded artifacts validated:** `P2-PDF-VISUAL-20261026T135824Z-c71f56fbf0.zip` is valid and contains only diagnostic `result.json` + `manifest.json`; `P2-PDF-VISUAL-20261026T135824Z-c71f56fbf0-visual-preview.zip` has SHA-256 `042143349dc00eae6dd179b73fb55a21f57a61f3e2dbdca34a6037e0f6102233`, exactly as recorded in `result.json`. Both ZIP CRC checks passed. The preview contains 3 PDFs, 9 PNG pages, instructions and its manifest; all **12 PDF/PNG member hashes** match that manifest. Preflight 0 blockers/0 findings; worker return code 0; standard **8**, dense **22**, Unicode **7** pages with **3/3 STRUCTURAL_PASS**. Status remains `REVIEW_REQUIRED` and `visual_acceptance=NOT_REVIEWED` until interpreted using this review.

**Scoped chart-pagination fix: VISUALLY VERIFIED:** Independently extracted and rendered the *new* three source PDFs, inspected all 37 pages in contact sheets and the specific chart/Unicode pages in detailed views. The page-text location check and actual rendered pages agree: `Saved chart visualization`, `Sum of Revenue by Region` vector chart, and `Chart limitations` now remain together on **standard p3, dense p3/p10/p17, Unicode p3**. The earlier `standard` and `unicode` orphaned-heading issue has been corrected on the tested Windows generated report. No obvious chart overlap, missing disclosure notices or A4 page-edge clipping was seen in these scoped previews. **Pagination defect B can be closed for the synthetic visual gate**; that does not certify arbitrary printer output.

**Unicode defect A: VISUAL_FAIL remains OPEN:** `unicode.pdf` p1 still contains visible black-square/misrendered placeholders for source strings `Δ Ω`, `Москва`, `漢字`, `₹` and `📈`. Exact-text extraction fails on those originals, while `café`, `São Paulo` and `R²` remain extractable. The prior font-replacement issue was not part of the chart fix and should not be marked passed. Full visual gate is thus **PARTIAL: pagination PASS; Unicode FAIL**, and P2 remains overall `REVIEW_REQUIRED`.

**Planning next, no speculative font patch:** A separate `docs/P2_PDF_UNICODE_FONT_REMEDIATION_PLAN.md` now lays out pinned SIL OFL asset selection, ReportLab TTFont compatibility, reusable glyph fallback for PDF paragraphs/charts, CJK and emoji constraints, packaging/licensing, fail-closed unsupported-glyph handling, and isolated Windows/visual acceptance. This font plan is not a committed production font change and no new owner BAT run is warranted until that seam has an evidence-based implementation.
