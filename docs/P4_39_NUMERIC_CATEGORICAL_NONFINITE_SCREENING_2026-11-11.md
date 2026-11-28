# PilotODIN 1.0 | P4-39 Numeric categorical non-finite screening safety

**Date:** 11 November 2026. **Status:** P4 ACTIVE, source-fixed and CI verified; owner-native NOT RETESTED. **Scope:** Read-only Target Intelligence P4 screening and synthetic tests, not training, Quality edits, installer packaging or release.

## Confirmed defect in current source

At starting branch HEAD `314f57f67ea66ce250347359ffd0ecba56297b2a`, Target Intelligence inferred numeric safety from `pd.api.types.is_numeric_dtype(series)`. pandas reports `False` when a Series has `CategoricalDtype`, even if its underlying categories are floating-point numbers. Therefore the existing finite checks at the target and predictor read-only screening paths were skipped for numeric categoricals. For example, two categorical numeric target labels `+inf` and `-inf` can each occur 40 times and falsely qualify as distinct nonmissing classes; numeric categorical predictors alternating such values can falsely satisfy variation. A categorical numeric field containing a single finite number plus infinity exhibits the same predictor issue.

The failure mode was verified through source inspection and disposable pandas probes. It is a **source/synthetic defect**, not observed corruption or an incident on owner data. Existing ordinary numeric screening from P4-26/P4-37 is retained.

## Bounded change and regression cases

[Implementation commit `8a77452128126f8a0f333d641ff5beb6f449f17d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8a77452128126f8a0f333d641ff5beb6f449f17d), parent `314f57f67ea66ce250347359ffd0ecba56297b2a`, changed only:
- `backend/target_opportunities.py`: new read-only `_value_dtype` returns category-value dtype for categorical Series and existing Series dtype otherwise. Finite numeric target guard, complex target guard, high-cardinality numeric detection, and predictor finite-variation guard now use this dtype where appropriate. Existing labelled-row masking and no-training policy remain.
- `tests/test_p4_target_opportunities.py`: eight synthetic variants: three non-finite numeric categorical targets; three invalid-only/one-finite numeric categorical predictors; one finite numeric categorical target and genuine finite predictor control; one complex categorical target rejection. They assert fail-closed queue and manual inspection, no automatic training, and preservation of original frame; finite-control case asserts reviewable only.

No original files, user categories, Quality versions, history, dataset paths, model weights, training endpoints, workflows or dependencies changed. No installed application tests and no installer generation.

## Exact-source verification and limitations

| Evidence | Verified outcome | Limitation |
| --- | --- | --- |
| [P4 Actions #43088605156](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43088605156), implementation SHA `8a774521`, attempt 1 | **COMPLETED SUCCESS, 3/3 jobs** | CI only |
| P4 Python test run | **144 pytest tests passed** | Disposable synthetic data |
| P4 Node contracts, including A3 Prepare source regression | **40 passed, 0 failed** | No installed native UI |
| TypeScript and Vite | **Build passed** | No Tauri/NSIS packaging |
| Disposable real-HTTP Chromium | **9 tests passed** | CI localhost browser/backend only |
| Windows 2022 synthetic storage and WebView checks | **PASS**, including PowerShell 7.6.9 and Windows PowerShell 5.1 | Does not exercise owner data or historical app-data differences |
| Current-source physical Windows UI and true offline 8 GB inference | **NOT RETESTED** | Explicit P4–P7 intermediate installer freeze |
| Independent real-world business Gate C | **UNVERIFIED** | True outcome provenance, predictor availability/timing, group/time independence, baseline utility, fair/lawful use require genuine evidence |

A documentation-only follow-up does not receive a fresh application CI claim.

## Preserved owner policies and next task

- The owner explicitly refused the residual-risk closure deferral and forbids P4–P7 installer builds, downloads and installation. P8 final packaging requires separate explicit approval.
- Historical original EXE/independent backup hashes matched, and the original source-defined critical `data/` subtree had 0 detected differences. **Strict complete original app-data tree preservation remains FAIL:** 320 baseline files vs 346 current; 74 WebView/cache *candidates*, historic writer UNKNOWN. Neither the regression test nor disposable CI can close the actual owner-data gate. No original file cleanup or baseline reset permitted.
- Current owner hardware/native parity, offline 8 GB Qwen load and independent Gate C remain unverified, P4-R01–R06 open. **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**

**Next:** Target concrete P4 acceptance blockers/negative tests only if a current source defect or evidence gap can be demonstrated. Native release hardware and owner business gates require genuine owner evidence, not synthetic certification or another intermediate installer.
