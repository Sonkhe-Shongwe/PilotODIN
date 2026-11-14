# PilotODIN 1.0 | P4-20 Labelled-Row Predictor Overlap Safety Audit

**Evidence date:** 9 November 2026  
**Owner instruction:** `next`, continuing bounded P4 correctness and isolation review after P4-19. The owner's explicit decision **not to close P4 by waiving or deferring unresolved safety gates** remains binding. No approval to train, use real datasets, rebuild/install a Windows app, close P4 or start P5.  
**Repository/branch:** `Sonkhe-Shongwe/PilotODIN` / `feature/live-dev-workspace-20261023`  
**Exact tested application source:** [`1d8e4b8d18e21c3d2508f42f53632c2f09644e2f`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1d8e4b8d18e21c3d2508f42f53632c2f09644e2f)  
**Exact verified CI:** [P4 Target Review Queue #42693382629](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42693382629) **COMPLETED SUCCESS**. **108/108 Python**, **28/28 Node**, TypeScript/Vite production bundle **PASS**, **8/8 disposable real-HTTP Chromium/Uvicorn browser** tests **PASS**.  
**Owner's installed physical Windows QA app:** remains at older `bca3c57b94a425cd9ef489726e721328d12c2ead`, NOT rebuilt or native-retested at this SHA.

## Source-confirmed P4 structural screening error

Before this increment, `backend/target_opportunities.py::_candidate` decided whether any candidate predictor remains from each **entire** column's `notna().any()` and `nunique(dropna=True) > 1`. It did not restrict that screen to **records with an observed target label**.

A deterministic 80-row synthetic example has `churn` observed for 40 rows (20 `Y`, 20 `N`) and missing for the other 40, plus only `feature` as an input. `feature` can be entirely missing or constant on all 40 labelled rows, yet vary on the 40 **unlabelled** rows. The old P4 code saw global variation, met the numeric label minimum and 6-minority support, and could classify `churn` as `structurally reviewable`. However, no varying predictor is observed among the actual supervised examples. This was a **source-confirmed false structural-readiness assessment**; no actual model was trained and no owner dataset was involved.

## Minimal corrective scope and tests

**Fix at `1d8e4b8d18e21c3d2508f42f53632c2f09644e2f`:** Use the bounded `labelled_frame = frame.loc[series.notna()]` in `_candidate`, and count non-empty, varying candidate predictors **only within those labelled records**. Existing two-axis warnings and separate business gate remain unchanged. Both `recommend` and `inspect_manual_target` share this corrected `_candidate`, so they fail closed consistently. No change to Quality dataset content, project storage, training endpoints, local inference, Tauri or installer. The normal queue and manual inspections already bound candidate row/column inspection work; this fix does not claim to cap full-dataset loading, peak memory or future training.

**Four synthetic pytest cases** added to `tests/test_p4_target_opportunities.py`:
- `test_predictors_varying_only_outside_labelled_records_are_blocked[unlabelled_only]`: predictor exists/varies exclusively on rows with missing `churn`; queue **abstains**, `churn` **blocked**, no training authorisation; input DataFrame unchanged.
- Same test `[constant_when_labelled]`: predictor value constant within labelled records, varying only elsewhere; **blocked** despite global variation.
- `test_manual_inspection_blocks_unlabelled_only_predictor_variation`: direct manual inspection returns **blocked**, no task hypothesis or training approval; input unchanged.
- `test_partly_missing_labels_with_varying_labelled_predictor_stay_reviewable`: valid variation in the 40 actually labelled records still permits **structural review only**, retains missing-label warning and refuses automatic training.

## Evidence matrix and risk boundary

| Assertion | Verified outcome |
| --- | --- |
| Labelled-row predictor support for regular review queue | **SOURCE-FIXED; synthetic Python PASS** |
| Same support for explicit manual inspection | **SOURCE-FIXED; synthetic Python PASS** |
| Valid partially labelled classification remains reviewable | **SOURCE PYTHON PASS; no automatic training approval** |
| Existing P4 negative, project/Quality-version, origin/isolation, bounds suites | **CI 108 Python / 28 Node / 8 real HTTP browser PASS**, not a universal correctness proof |
| Physical owner Tauri/WebView2 at new source SHA | **NOT TESTED**; older installed QA binary still present |
| True predictor availability before decision, real entity grouping, label provenance, measured value, lawful/fair use (Gate C) | **UNVERIFIED, NOT WAIVED** |
| Native negative/version/no-user-write checks, restored original backup, full offline/8 GB resource gate | **OPEN / PARTIAL / NOT TESTED** |

**Defect status:** Medium scoped P4 **structural-correctness defect source-fixed and green CI**, with Windows retest pending for a **single later independently authorised consolidated native candidate**. A feature varying in labelled records can still be a post-outcome leak, sensitive, identifier-like, non-causal or operationally unavailable. This fix is **not** independent evidence of predictive value, group/time validation or suitability.

**Phase status:** P4 **ACTIVE** with original Gate C intact and original owner risk-refusal decision unchanged. P4-R01–R06 unresolved, Master QA Issue #2 and P4 evidence Issue #9 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED. No owner project, existing desktop app, model, training experiment, release artifact, or Windows install was modified.

**Next meaningful gate:** Focus engineering effort on production-facing data-integrity/security failures with reproducible evidence, and plan the separate **one-milestone native verification and actual 8 GB/offline measurement** once enough source fixes justify it. Independent real operational decision evidence remains a prerequisite for original Gate C; do not substitute more synthetic examples for missing business proof or endlessly expand routine P4 edge cases.
