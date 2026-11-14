# P2 Report Display Disclosure and PDF Geometry: Focused Development Gate

**Date:** 26 October 2026 (South Africa). **Status:** IMPLEMENTED IN SOURCE; OWNER WINDOWS EXECUTION PENDING.
**Working branch:** `feature/live-dev-workspace-20261023`. Re-fetch live HEAD before more changes.
**Predecessor:** `docs/P2_MIXED_EVIDENCE_DEVQA_ACCEPTANCE.md`, owner-observed and ZIP-verified **3/3 runner + 9/9 mixed-report PASS** (the final scoped gate correctly returned `REVIEW_REQUIRED`). Do not rerun it.

## 1. The established source gap and narrow correction

The old `backend/reports.py::_exhibit` rendered at most 24 fact labels, 40 ordinary observation rows, 50 comparison rows or 30 quality findings, but did not systematically tell the exported HTML/PDF reader the *number omitted from this displayed exhibit*. That is a reader-facing completeness weakness even when the underlying frozen evidence is correct. The change does not assert that source datasets are truncated or that omitted items are necessarily business errors.

A new `_exhibit_with_disclosure` makes the **same** display table/fact projection and returns factual count-only notices for saved evidence items excluded by the exhibit caps. `_exhibit` remains a three-tuple wrapper so accepted callers and the nine P2 mixed tests retain their contract. Both HTML and PDF now show a **Display limits** section when there is an actual omission. Notice counts derive from the saved, already-bound report artifact, never from a live dataset or untrusted browser-supplied counts. Wording distinguishes a saved report's evidence projection from broader upstream Explore/Quality snapshots.

Examples used by the synthetic gate:
- 30 stored summary facts -> 24 shown, 6 omitted.
- 45 stored observation entries -> 40 shown, 5 omitted.
- 35 stored finding entries -> 30 shown, 5 omitted.
- 53 stored comparison entries -> 50 shown, 3 omitted.

Existing evidence ordering, report revision SHA calculation/storage, underlying analytics arithmetic, model projections, identifiers, original data and accepted native Save As remain unchanged. Charts retain their existing bounded visual note; this package does **not** change `report_charts.py` or introduce unsupported chart types.

## 2. Five isolated synthetic checks

`tests/test_p2_report_display_disclosure.py` defines exactly five focused `unittest` methods:

1. Fact/ordinary-row cap and precise omitted counts; legacy three-return `_exhibit` still works.
2. Quality findings and comparison display count disclosure at their respective caps.
3. HTML/PDF text parity for the four notices and pre-existing bounded-chart caveat, with synthetic original report object unchanged.
4. No fabricated omission note when saved evidence is fully displayed.
5. Dense 12-exhibit, multipage A4 PDF generated **directly from synthetic in-memory frozen-looking artifacts**; PyMuPDF checks page size and extracted text-block bounding boxes lie within the A4 page.

**Visual boundary:** PyMuPDF text-block geometry is a smoke check. It cannot certify glyph-by-glyph clipping, overlapping glyphs, missing non-Latin fonts, subtle kerning, visual aesthetics, real printer behaviour or HTML browser layout. These remain separately reviewed; the overall runner reports `REVIEW_REQUIRED` if all five tests pass.

## 3. One Windows verification package

- `Run_PilotODIN_P2_Report_Display_DevQA.bat` uses only existing `.venv-live\Scripts\python.exe`, no installation.
- `tools/p2_report_display_devqa.py` creates one fresh `%LOCALAPPDATA%\PilotODIN\DevQA\runs\P2-REPORT-DISPLAY-...\workspace`; verifies path boundaries and source syntax; child process sets isolated `PILOTODIN_HOME` **before importing backend reports/storage**. It uses dedicated status-only worker file instead of stdout.
- The test module does not import datasets through FastAPI or run an ML fit. The report/store imports may create only the disposable SQLite workspace.
- One archived `P2-REPORT-DISPLAY-....zip` contains **only `result.json` and `manifest.json`**, not PDF/HTML/source rows/tracebacks/user data. Failure records contain test IDs and stages.
- Final state: **REVIEW_REQUIRED** if all five tests complete PASS; **FAIL** for assertions; **BLOCKED** for setup/import/timeouts/partial, unexpected counts or diagnostic failure.

## 4. Predictive risk review and remaining gates

- Existing consumer compatibility: `_exhibit` retains its original return shape; old suites unchanged.
- Inaccurate counts: upstream captures may already be bounded. Notices say *saved* evidence entries and *this export*, retaining upstream limitations.
- Privacy: notices expose counts only, not individual rows; exported HTML escapes notices; QA archives status only.
- Layout: notices add paragraphs and page breaks. The PDF groups short limit notices using `KeepTogether` and the synthetic 12-exhibit geometry test checks A4 bounds.
- Windows failures: existing venv, explicit QA home, no native processes, fail-closed archive and preserved error classifications.
- Interaction/upgrade: existing report APIs/revision contracts unchanged and no database migration.
- Still unaccepted: exhaustive glyph clipping and unusual fonts, human print review, arbitrary real datasets, installed/offline E-01–E-24 and combined 8 GB release feasibility.

## 5. Exact next owner action

Pull the current feature branch while preserving local modified and untracked files. Run **`Run_PilotODIN_P2_Report_Display_DevQA.bat` once**. Share a console screenshot; if FAIL or BLOCKED, upload the printed status-only ZIP for focused root-cause analysis. **Do not rerun** the accepted 12-case mixed-evidence BAT, native Save As BAT or unrelated broad suites. After a green gate, decide whether separate human PDF preview inspection on disposable synthetic artifacts is needed to close the remaining P2 visual boundary. This batch does not authorize moving to P3 or a final installer.

## 26 October 2026: Owner Windows focused acceptance result

**Actual observed result:** Owner provided screenshot and uploaded the original status-only archive `P2-REPORT-DISPLAY-20261026T130557Z-71ae4c1550.zip`. Archive integrity was checked and it contains **only `result.json` (1058 bytes) and `manifest.json` (1627 bytes)**. Both record the matching run ID, `state=REVIEW_REQUIRED` and `product_acceptance=NOT_TESTED`. Run manifest records `created_utc=2026-10-26T13:05:57.967797+00:00`. Source preflight found **zero blockers and zero findings**. The worker returned **exit code 0** with expected `count=5`, actual `executed=5`, and **zero failures, zero errors and zero skipped cases**.

**Accepted evidence:** This targeted development-only five-test Windows gate **PASSED**. It verifies synthetic display-limit arithmetic for saved evidence facts, rows, findings and comparisons; preservation of the old three-value `_exhibit` contract; HTML/PDF notice-presence parity; truthful absence of notices when none are required; unchanged in-memory synthetic report; and bounded multipage A4 extracted-text geometry smoke. Earlier owner-accepted **3+9 mixed-report synthetic** and separate **native HTML/PDF Save As exact SHA** results remain valid and should not be repeated.

**Do not over-interpret:** The diagnostic ZIP contains no PDF pages or images of rendered pages. The PDF check observes extracted text-block bounds, not actual glyph clipping, overlapping shapes, missing font coverage or human/printed readability. No arbitrary customer data, installed native release or full P2 product acceptance was checked. `product_acceptance=NOT_TESTED` and the generic manifest risk-register `NOT_TESTED` fields are expected for this focused DevQA run, not failed scoped tests.

**Next bounded engineering gate:** Do not repeat accepted test suites. Plan an isolated synthetic PDF *visual* inspection with a distinct acceptance record for long labels, unusual characters, dense tables, page breaks, notices, chart captions, collision/clipping and legibility. Do not claim human visual acceptance from the status-only ZIP. If an actual rendering defect is reproducible, fix only that layout seam and target affected tests. No installer, real datasets, Qwen, or unrelated scope expansion.
