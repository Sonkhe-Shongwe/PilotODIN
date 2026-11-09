# PilotODIN 1.0 | P4-18 Fail-Closed Target Screening Safety Audit

**Evidence date:** 9 November 2026  
**Authorised scope:** P4 safety/correctness verification following owner's explicit refusal to defer risk at P4-17. Owner said `next` to continue risk-first P4 only. This is NOT P4 phase closure, owner Windows installation/rebuild, model training, real-business deployment, P5 or release authorisation.  
**Repository/branch:** `Sonkhe-Shongwe/PilotODIN` / `feature/live-dev-workspace-20261023`  
**Exact tested application SHA:** [`9dbc9236cb0fad7ebab481b92095190af3cc1738`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9dbc9236cb0fad7ebab481b92095190af3cc1738)  
**Current owner Windows QA binary:** Still from Windows CI source `bca3c57b94a425cd9ef489726e721328d12c2ead`, **not** rebuilt or changed by this source increment.

## Confirmed P4 safety gap: non-finite two-class numeric label

In the original P4 `backend/target_opportunities.py::_candidate`, pandas `notna()` counted positive and negative infinity as non-missing and `nunique()` counted them as two classes. `engine.infer_task()` uses `unique == 2` to infer classification *before* checking whether numeric labels are finite, while the existing finite-value check in P4 ran only when the task was **regression**. Consequently, a synthetic 80-row `churn` numeric column containing 40 `+Infinity` and 40 `-Infinity` values with a varying predictor could pass P4's technical classification screening. That was a **source-confirmed misleading reviewable-target result**, not an observed user-project problem, measured model prediction or permission to train.

**Bounded correction at `9dbc923...`:** In `_candidate`, reject numeric targets with any non-finite non-missing label **before** the two-class inference shortcut; fail closed on finite-conversion errors and complex-valued targets. Because both `recommend` and `inspect_manual_target` call `_candidate`, the correction covers the normal queue and explicit manual inspection. It does **not** change genuine finite binary classification, project storage, model training API, Tauri/runtime, installed old/QA projects or installer.

**Three new synthetic regressions** in `tests/test_p4_target_opportunities.py`:
- `test_nonfinite_two_class_numeric_target_is_blocked_not_a_classification`: infinity-only two-class numeric `churn` (40/40) reports observed counts but **blocked**, no task hypothesis, shortlist abstains, no automatic training; original DataFrame unchanged.
- `test_nonfinite_numeric_target_also_blocked_in_explicit_manual_inspection`: one finite class and `+Infinity` second class returns **blocked** and `training_authorised=false` in manually requested candidate.
- `test_finite_binary_numeric_target_remains_structurally_reviewable`: legitimate finite `0/1` labels are still **structurally reviewable** only, never automatically training approved.

## Exact-source CI outcomes, not inferred

| Independent check | Observed result | Evidence |
| --- | --- | --- |
| P4 Python including 3 new target-label regressions | **99/99 PASS** | [P4 Actions #42689004962](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42689004962), source SHA `9dbc923...` |
| P4 Node frontend/source contracts | **28/28 PASS** | Same run |
| TypeScript/Vite production frontend build | **PASS** | Same run |
| Real Uvicorn/SQLite + Chromium P4 browser acceptance | **8/8 PASS** | Same run (disposable dataset/project isolation) |
| Owner native Tauri/WebView2 correction for new non-finite case | **NOT TESTED** | No Windows rebuild or physical re-install at this exact application SHA |
| Real business label provenance, safety, decision benefit, fairness | **UNVERIFIED** | Synthetic numeric screening cannot establish Gate C |

Earlier Windows owner acceptance of 80-row classification/regression, 80/40/40 repeated identifiers and project switching remains valid **only for the earlier installed QA source**. Do not claim it physically tested this correction.

## Consolidated P4 negative-safety audit

| Failure mode | Evidence at last source SHA | Assessment |
| --- | --- | --- |
| Rare classification minority 4/80 | Existing `tests/test_p4_phase_exit_matrix.py`, `tests/test_p4_consolidated_acceptance.py`; focused P4 CI green | **AUTOMATED PASS; native N8 NOT TESTED** |
| Insufficient 24/80 labelled outcome | Same synthetic source/API suites; P4 CI green | **AUTOMATED PASS; native N9 NOT TESTED** |
| No supported outcome-name cue | Synthetic abstention cases + real-HTTP browser; no arbitrary numeric target inferred | **AUTOMATED PASS; native N10 NOT TESTED** |
| Two-class non-finite numeric labels | Three new direct queue/manual/finite-control cases at `9dbc923...` | **SOURCE FIX + AUTOMATED PASS; native NOT TESTED** |
| Duplicate column headers, scores/probabilities/derived names | Existing synthetic negative cases; no incorrect approval | **AUTOMATED PASS; no claim of full semantic truth** |
| Too-wide/too-long queue, bounded manual scan | Existing P4-13/14/15 resource tests and browser | **AUTOMATED FAIL-CLOSED PASS; whole app peak memory unmeasured** |
| Stale Quality version, foreign HTTP Origin, project context isolation | Existing FastAPI/real-HTTP 409/403 and project-switch cases | **AUTOMATED PASS; owner-native Quality version N11 NOT TESTED** |
| Unexpected model creation from target recommendation/abstention | Read-only route/source contracts plus existing browser no-saved-experiments checks | **AUTOMATED PASS FOR TESTED PATHS; no universal permission/cross-phase model-training claim** |
| Original user project modification/cloud use/offline/8 GB | Original binary hash preserved and separate QA data identity observed; no complete data hash/OS-network/memory capture | **PARTIAL native evidence only; N12/resource gate OPEN** |

No new training runs or original data experiments were created for this audit. The newly surfaced bug is addressed in code; the broader P4 safety requirement and all open operational gates remain intact.

## Explicitly remaining risks, owner constraints and next safe work

1. **P4-18-01** newly confirmed finite-label screening defect: **SOURCE-FIXED / CI PASS / OWNER-NATIVE NOT RETESTED**. Do not label it native-fixed or release-ready.
2. **P4-R01** original real operational **Gate C remains UNVERIFIED and not waived**: independent target label source, as-of prediction moment, group/time split, business alternative/baseline/benefit/cost and lawful/fair intended action. Without a real use-case and independent evidence, the appropriate verdict can be **NO SUITABLE PREDICTION OBJECTIVE YET**, not fabricated acceptance.
3. **P4-R02–R06** remain open: native rare/missing/none/version parity, real 8 GB/offline measurements, source-fixed but not native-retested UI issues (empty archived banner; crushed evidence text), medium BE-024 Prepare controls, and full old-project data preservation/restore verification. Critical/high out-of-scope master QA defects remain release blockers without being relabelled P4 defects.
4. **Next highest-value bounded task:** Inspect any remaining *P4-specific* false-eligibility/error-handling paths via cheap synthetic tests. Arrange at most **one later separately authorised consolidated Windows test** once meaningful fixes accumulate, to verify source parity and measured hardware/data safety. Business Gate C requires independent real operational evidence, not more synthetic CSV imports. No installer rebuild or repeated manual owner test is authorised here.

**Final status:** P4 **ACTIVE, CLOSURE NOT APPROVED** after owner's earlier "we shouldnt risk". P5 **NOT AUTHORISED**; P8 **NOT CERTIFIED**; master QA Issue #2 and P4 evidence Issue #9 remain **OPEN**. This audit is an engineering risk reduction, not a P4 phase-close vote.
