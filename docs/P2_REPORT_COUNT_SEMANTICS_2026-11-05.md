# PilotODIN P2 | Saved chart count semantics correction

**Date:** 5 November 2026  
**Phase:** P2 ACTIVE; NOT CLOSED  
**Branch:** `feature/live-dev-workspace-20261023`

## Confirmed problem and bounded requirement
GitHub QA Issue #2, historical BE-009, identifies that charts with `count` aggregation and a selected Y/measure may be interpreted as unconditional X-category record counts. The actual `backend/analytics.py::chart` count-with-Y path aggregates the numeric-coerced Y column by X and excludes absent/invalid converted Y values, while count-without-Y counts records by X. The saved Deliver chart previously labelled the former `Count of Y by X`, which did not expose the denominator distinction. This increment corrects the **saved report presentation boundary only**, not the interactive Explore chart title or numeric engine.

## Production implementation
- [Source commit `b5e82f93716d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b5e82f93716d3b9f9f4d5078a552334035b46cc2): `backend/report_charts.py::measure_caption` now says `Count of non-missing Y by X` when Y is selected and `Record count by X` when Y is absent. Histogram frequency and median/other aggregations keep their original captions.
- `html_chart` uses this caption consistently in its escaped SVG `<title>`, inline heading and figure caption. `pdf_chart` uses the same caption for its vector title. Existing full saved point values, chart geometry, HTML/PDF rendering policy and evidence hashes are untouched.
- [New regression source `73fa0d3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/73fa0d3dc499312db96f9cd242110d23d4ca0aa9), regex correction [`f70df38`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f70df389ed3cc0b5a537e4444f87408438b8a39c): six direct production chart behavioural tests with synthetic in-memory aggregates, covering Y-present, Y-absent, HTML/SVG and PDF captions, non-count/histogram preservation, escaping, no numerical mutation.
- Scoped CI [`06fcb167`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/06fcb1671e90006080c9220bee33f5a5dc601f19) adds a trusted-feature-branch workflow. No installer, fonts, models or real report export are invoked.

## Actual verification (not extrapolated)
- [GitHub Actions run #42060836775](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42060836775), tested commit `06fcb1671e90006080c9220bee33f5a5dc601f19`: **COMPLETED SUCCESS** on Ubuntu 24.04 / Python 3.11.
- New `tests/test_p2_report_count_semantics.py` plus previously accepted `tests/test_p2_saved_html_chart_header.py`: **12 passed, 3 subtests passed**; production `backend/report_charts.py` Python compilation **PASS**.
- This is actual production-function execution inside CI, not source-string assertions. No owner Windows/WebView2 interaction, true PDF file visual inspection, real project-data comparison or offline installer was performed for this change. A nonblocking GitHub Actions checkout Node 20 deprecation warning appeared; no test/build failed.

## Remaining limitations and next task
- **BE-009 is not globally closed:** interactive Explore chart labels remain a separately scoped interface issue. This P2 correction only addresses saved Deliver HTML/PDF captions.
- Production Unicode PDF remains **NOT ACCEPTED**: actual single-synthetic-report Unicode renderer DevQA previously passed, but normal authenticated PDF activation remains gated by independent owner approval of exact font/OFL release identities, safe bundled resources, concurrency and visual acceptance.
- Next P2 decision: review [font release owner decision](./P2_PDF_FONT_RELEASE_OWNER_DECISION.md) and [PDF production integration gate](./P2_PDF_UNICODE_PRODUCTION_INTEGRATION_GATE.md). Continue only source-safe, synthetic reporting work pending explicit final font distribution approval. No new P0/P1 work, P8 installer, data migrations or source assets were authorised by this increment.

**P2 status:** ACTIVE / REVIEW_REQUIRED. **P1:** CLOSED development scope. **P8 release:** NOT CERTIFIED.
