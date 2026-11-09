# PilotODIN 1.0 | P4-13 Bounded Manual Target Inspection and Resource Disclosure

**Date:** 9 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Verified application SHA:** [`0b4ca41a16ee8eaf7ddb6a7c9cbe5eb1cb3bd42d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0b4ca41a16ee8eaf7ddb6a7c9cbe5eb1cb3bd42d)  
**Authority:** P4 Target Intelligence ACTIVE; P1/P2/P3 development-CLOSED; P5 NOT AUTHORISED; P8 NOT CERTIFIED.

## Scope and reason

P4-12 introduced an on-demand, local GET screening result for an explicitly manually selected target column outside the bounded 3+12 review queue and five blocked examples. Although its repeated-ID scan was bounded, the P4-12 one-column `_candidate` helper still swept all predictor series in the loaded working DataFrame to find nonconstant predictors and count values. With many columns and rows that work grows, even though only one target was requested.

P4-13 limits the **selected-column screening operation** without changing the main shortlist or Model Lab training logic. It does **not** restrict the original loaded DataFrame in memory or establish 8 GB native feasibility.

## Bounded inspection implementation

`backend/target_opportunities.py` declares `MAX_MANUAL_INSPECT_ROWS = 5000` and `MAX_MANUAL_INSPECT_PREDICTORS = 32`. In `inspect_manual_target` it selects **only the first 5,000 rows**, **at most the first 32 other predictor columns** and **the exact manually selected target, even if that target occurs at the end of a very wide schema**. All subsequent `_candidate` value/label and predictor checks operate on this subset. Existing prediction-context header review is bounded separately; identifier value scanning operates on the bounded subset and explicitly marks original row/column omissions.

The new `resource_review` response includes all of the following:

| Key | Meaning |
| --- | --- |
| `scope` | `bounded_single_column_structural_observations` |
| `rows_examined` / `total_rows` | Number of observed leading rows and original loaded-row count |
| `columns_examined` / `total_columns` | Selected target plus sampled other columns versus complete header count |
| `predictor_columns_examined` / `total_predictor_columns` | Other headers inspected versus all other original headers |
| `row_limit` / `predictor_column_limit` | 5,000 and 32 |
| `truncated` / `interpretation` | Incomplete observation marker and explicit limitation |

If any row or predictor column is unexamined, **`technical_status='blocked'` and `task_hypothesis=null`** are returned even if the subset appears eligible; the blocker explicitly identifies truncation and unresolved full structural eligibility. If a subset contains no usable predictor, the message correctly says that **unexamined rows/columns could contain one**, rather than claiming that no predictors remain in the entire dataset. Unverified owner descriptions, unsupported outcome-name warnings and all training guards remain in force.

`frontend/src/TargetOpportunities.tsx` shows a selected-target `Bounded manual screening coverage` panel. For incomplete observations it says **Incomplete structural scan: not approved**, gives observed rows, other columns, configured limits and explicit **sample-only** label count context. A fully scanned small target retains the previous structural-review state with its existing unverified business/label/timing caveats.

The existing P1 synthetic browser mock adds only the corresponding `resource_review` fields to its pre-existing narrow two-label, structurally blocked response. It is a test-owned stub; production P1 logic has not changed.

## Actual synthetic CI acceptance

| Test/evidence | Observed result |
| --- | --- |
| [P4 workflow #42605278391](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42605278391) | **COMPLETED SUCCESS at exact source SHA:** 60/60 Python, 25/25 Node contracts, TypeScript/Vite build PASS, 6/6 real-HTTP disposable browser PASS |
| [P1 isolated frontend #42605278313](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42605278313) | **COMPLETED SUCCESS at same SHA:** 160/160 Node source contracts, frontend build PASS, 5/5 isolated Chromium cases PASS |
| Four added P4-13 Python cases | Small 80×30 complete; 5,120-row × 66-column only scans 5,000×33 and flags omissions; 80-row wide-only all-constant sampled predictors do not imply none elsewhere; 5,001-row boundary blocked conservatively; no underlying frame mutation, identifiers, fit or training |
| Added real-HTTP Chromium case | Disposable 80-row, 55-column imported project; omitted `outcome_99` selected by owner, 32/54 other predictors inspected, 33/55 total columns inspected, structural blocker and sample-only coverage shown, no training or unexpected browser writes |

**Resource claim restriction:** These checks validate *a deterministic scan-size bound*, not a measured memory ceiling, completion-time SLA, OS process memory, native Windows benchmark, QA acceptance on original owner data or proof that the overall PilotODIN app runs in 8 GB. The approved `quality.current_data` operation still loads the full project, and `recommend` may still assess many outcome-named columns against all predictors. Both are outside this narrowly scoped fix.

## Phase-exit boundary

The earlier P4-09 phase-exit evidence matrix remains the primary native/owner checkpoint, and the P4-10 synthetic Windows kit remains optional at milestone testing. The user prefers **CI-first development with fewer downloaded acceptance bundles**, which P4-13 respects. No source-matched physical Windows Tauri/WebView2 acceptance, independent real label provenance, as-of-time input availability, decision owner/baseline benefit, true grouped/time-split validity, lawful/fair deployment approval or explicit P4 closure decision has been recorded. Historical release Critical/High issues in master QA Issue #2 remain open.

**Disposition:** P4-13 **ACCEPTED ONLY FOR SCOPED SOURCE AND SYNTHETIC CI/BROWSER EVIDENCE**. P4 ACTIVE; P5 not authorised; P8 release NOT CERTIFIED.

**Next if owner explicitly says `next`:** investigate whole-queue wide/long read-only screening costs, document a conservative bounded strategy, implement and test it in P4 only if justified. Avoid manually installing or altering a Windows app for ordinary CI-first increments.
