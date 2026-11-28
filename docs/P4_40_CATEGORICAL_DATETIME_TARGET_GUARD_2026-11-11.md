# PilotODIN 1.0 | P4-40 Categorical datetime targets fail closed

**Date:** 11 November 2026. **Phase:** P4 ACTIVE. **Disposition:** SOURCE FIXED / EXACT-SOURCE CI PASS / OWNER-NATIVE NOT RETESTED.

## Reproducer and root cause

Before [`0387412e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0387412e8d0789144edcffe49c62b5ac496bc2ac), `backend/target_opportunities.py::_is_date` checked `pd.api.types.is_datetime64_any_dtype(series)`. pandas reports `False` for a `CategoricalDtype` Series containing datetime64 values (including timezone-aware timestamps), even though `series.cat.categories.dtype` is datetime. A synthetic 80-row `outcome` column with two timestamp categories and a varying numeric predictor could consequently pass the target screen as a classification hypothesis. This is **source inspection and isolated synthetic evidence**, not a defect demonstrated on original owner records.

## Bounded fix and tests

Implementation parent `d73cc9f106d2e5dd230e7704ef88563e6bfadf7e`, source commit [`0387412e8d0789144edcffe49c62b5ac496bc2ac`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0387412e8d0789144edcffe49c62b5ac496bc2ac). Exactly two files changed:
- `backend/target_opportunities.py`: reuse read-only `_value_dtype(series)` for the datetime predicate in `_is_date`. This corrects categorical-wrapper datetime inspection while retaining existing name-based timestamp blocks.
- `tests/test_p4_target_opportunities.py`: two distinct timestamp categorical cases (naive and timezone-aware) require both ranked queue and manual inspection to block, report date/time evidence, prohibit training, and preserve the frame. A separate positive test confirms ordinary categorical `Y/N` outcomes and numerical `time_to_resolution` remain reviewable *only as structural hypotheses*.

No stored data, categorical values, Quality versions/history, model weights, API contracts, network assets or owner machine were touched. No model fitting or packaging.

## Actual exact-source verification

| Check | Observed result | Limit |
| --- | --- | --- |
| [P4 Actions run #43089658871](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43089658871), attempt 1 at `0387412e` | **COMPLETED SUCCESS, 3/3 jobs** | GitHub-hosted CI, no owner PC |
| Focused Python P4 suites | **147 passed** | Synthetic/disposable data only |
| Node source/frontend contracts | **40 passed, 0 failed** | Not native UI |
| TypeScript / Vite | **Build PASS** | No installer produced |
| Real-HTTP Chromium P4 | **9 passed** | Disposable localhost CI browser/backend |
| Windows safety | **PASS** (synthetic integrity and WebView, PowerShell 7.6.9 and Windows PowerShell 5.1) | Does not resolve original real app-data drift |
| Native Windows owner source parity | **NOT RETESTED** | Intermediate installer freeze |
| Actual owner offline Qwen / 8 GB and real business Gate C | **NOT TESTED / UNVERIFIED** | Requires independent real-world evidence |

## Remaining gates and next action

Original production EXE and independent backup previously matched their baselines, and protected original `data/` subtree showed no detected changes. The **strict whole original app-data directory preservation gate still FAILS**: 320 backup versus 346 observed files, 74 WebView/cache *candidates*, historic writer UNKNOWN. Do not remove anything, relabel the evidence, replace baselines, waive it or attribute the discrepancy without evidence.

No further intermediate P4–P7 installer builds, downloads or installations are authorised. P8/final-stage packaging, if ever reached, separately requires owner approval. Physical owner WebView2 parity, real 8 GB/offline AI, independently verified business label provenance/decision timing/group independence/nonmodel benefit/fair use and P4-R01–R06 stay open. The owner declined a proposal to defer residual risks.

**Next:** Restrict development to genuinely verified P4 source negative/version/integrity gaps. Keep acceptance BLOCKED where only owner-native or independent business evidence can resolve it. **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**
