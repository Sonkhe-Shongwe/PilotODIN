# PilotODIN 1.0 | P4-37 Non-finite numeric predictor structural safety

**Date:** 11 November 2026. **P4:** ACTIVE. **Scope:** Source-only read-only Target Intelligence screening. No model training, owner data, installer or phase change.

## Defect proven from source and synthetic data

The `_candidate` method of `backend/target_opportunities.py` used `Series.nunique(dropna=True)>1` to decide whether a predictor varied among labelled records. Numeric `+inf` and `-inf` are distinct and not considered missing by pandas, yet neither represents a finite numeric predictor value. A synthetic 80-row `churn` target with 40 `Y`, 40 `N` and one feature alternating `+inf`, `-inf` could therefore appear to have a valid predictor. The same problem arose for a feature alternating one valid finite number with infinity. This is a **source and synthetic reproduction**, not a claimed incident on owner records.

The target-side P4-26 check already rejected nonfinite numeric **labels**. This new check addresses predictor-only variation within the capped screening pathway. It remains structural evidence, not fitness for training or verified operational usefulness.

## Minimal source and tests

[Exact source change `3b36626b30f302d02e1edc965478fa72a5eecca4`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3b36626b30f302d02e1edc965478fa72a5eecca4) changed exactly `backend/target_opportunities.py` and `tests/test_p4_target_opportunities.py`.

- Within `has_observed_variation` and the existing **labelled-row-only, bounded predictor sample**, numeric columns are masked in a **temporary Series** where nonmissing values fail `numpy.isfinite`, before counting distinct values.
- The target becomes **structurally blocked** if no other usable varying predictor remains. Both normal queue recommendations and explicit manual single-target inspection share the protection. No input DataFrame, Quality revision, model preprocessing or trainer changes.
- Three parameterized synthetic cases cover infinity-only and one finite number with positive/negative infinity; another covers `NaN` mixed with infinities and one valid numeric value. All must abstain, return no automatic training permission, and preserve original frames.
- A control with two real finite values alongside infinity remains **structurally reviewable only**, with automatic training disallowed and no inference of cleared predictor data quality.
- No raw label values, source rows, credentials or private owner project details were saved in GitHub.

## Verified exact-source CI

| Evidence | Result | Limitation |
| --- | --- | --- |
| [P4 workflow #43085745069](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43085745069) at `3b36626b` | **COMPLETED SUCCESS, all 3 jobs** | Synthetic/disposable CI only |
| Focused Python P4 suite, including new finite-predictor cases | **PASS** | No owner data used |
| Focused P4 Node contracts and real TS/Vite build | **PASS** | Source frontend, not installed Windows native |
| P4 disposable real-HTTP Chromium | **PASS** | CI-only localhost backend/browser |
| Windows 2022 fake-file original-storage and PowerShell 5.1 guards | **PASS** | No actual owner data or native acceptance |
| Current-source owner physical Windows QA | **NOT RETESTED** | Installer freeze governs |

## Explicit boundaries and next work

A structural **reviewable** target may still have unusable feature values, leakage, bad chronology, proxy labels or nonexistent decision benefit. This guard addresses **only** invalid numeric variation and cannot be represented as end-to-end Quality or model-training acceptance. Independent lawful and real-business Gate C still needs a true label source, prediction-time inputs, entity/time validation, nonmodel baseline and assessed decision benefit. A no-objective disposition is valid.

The original installed production EXE and independent pre-QA backup matched their baselines; the protected source-defined original project `data/` subtree showed 0 detected differences. Yet **strict original entire app-data tree preservation remains FAIL** (320 baseline files versus 346 current, 74 browser/cache *candidates*, historic process writer UNKNOWN). Do not rename, clean, reset, waive or silently classify these as safe. Owner-native source parity, physically offline 8 GB Qwen and Gate C remain open, P4-R01–R06 OPEN. The owner's **no more intermediate installers until final P8** rule is active and supported by branch-scoped job guards. Final packaging requires separate explicit owner consent.

**Disposition:** P4-37 SOURCE FIXED + exact-source synthetic CI SUCCESS; owner-native NOT RETESTED; **P4 ACTIVE; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**
