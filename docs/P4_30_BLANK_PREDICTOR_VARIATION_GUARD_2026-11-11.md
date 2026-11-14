# PilotODIN 1.0 | P4-30 Blank predictor variation guard

**Date:** 11 November 2026. **Scope:** P4 read-only Target Intelligence structural screening, not preprocessing or training.

## Confirmed defect and resolution

After P4-29 blocked blank-text **target labels**, the predictor variation check in `backend/target_opportunities.py::_candidate` still called `notna()` and `nunique(dropna=True)` directly on predictors. Thus distinct text entries `" "` and `"\\t"` were counted as two non-empty predictor values when **neither is useful**. On synthetic `churn=["Y","N"]*40`, `feature=[" ","\\t"]*40`, the previous predicate was true even though there was no meaningful predictor. This is a code-and-synthetic confirmed screening defect, not evidence of a failure using owner records.

[Source commit `f268a9a1cf5c0b7e82fafa89dd61d354fe04b55a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f268a9a1cf5c0b7e82fafa89dd61d354fe04b55a) updates exactly `backend/target_opportunities.py` and `tests/test_p4_target_opportunities.py`. In the labelled-row subset already used for screening, the bounded helper `has_observed_variation` creates a local masked view for blank/whitespace-only strings in text/object predictor columns, then requires more than one nonblank distinct observed value. It does not normalize other strings, silently clean Quality, change the original DataFrame, or modify the model training endpoint. P4 recommendation and manual selection share this source check.

## Synthetic cases and verified CI

- **Previously false positive now blocked:** 80 labelled target rows with predictor alternating between space/tab or between empty string/space.
- **Previously false positive now blocked:** predictor alternating one actual text category with blank text. One observed actual category is constant.
- **Control remains reviewable:** predictor with two real categories alongside some blank text. This is only a structural hypothesis, never business approval.
- For blocked cases, explicit manual inspection and the shortlist both return blocked, no inferred task and no automatic training approval, with the original DataFrame unchanged.

[P4 workflow #43062653304](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43062653304) was independently inspected and finished **COMPLETED SUCCESS at exact source `f268a9a`**, all three jobs: P4 Python synthetic and Node contracts, frontend TS/Vite, disposable real-HTTP Chromium, and Windows-2022 synthetic preservation/WebView2 tests including Windows PowerShell 5.1. This is **not** a physical Windows P4-30 user-interface test and does not certify a real predictive objective, training data quality, or user file preservation. This subsequent documentation-only commit is not credited with fresh application CI.

## Unchanged release and phase restrictions

The verified independent original backup and installed original EXE matched baseline and the critical original project `data/` subtree had zero detected changes. The entire original app-data directory **still fails** the strict equality gate (320 baseline files, 346 current; 74 browser/cache *candidates*, process responsible for their historical writes unknown). The owner P4-28 process-profile snapshot (26 observed, 6 QA, 0 original, 20 other) does not prove historical write isolation. Native source-fixed UI parity, offline Qwen/8 GB, true business-label/provenance/timing/group validation/benefit/fairness Gate C and P4-R01–R06 remain pending. No waiver, installer, deletion, baseline change or P5/P8 authorisation.

**Disposition: P4-30 SOURCE FIXED / CI VERIFIED; OWNER-NATIVE NOT TESTED. P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**
