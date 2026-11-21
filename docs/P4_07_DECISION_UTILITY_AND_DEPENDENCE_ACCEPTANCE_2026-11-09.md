# PilotODIN 1.0 | P4-07 Decision Utility and Repeated-Identifier Evidence

**Date:** 9 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Active phase:** P4 only; P1/P2/P3 CLOSED for bounded development; P8 NOT CERTIFIED.  
**Source commit:** [`3212403ab5328a0aa58a07d0e323bd046886d92c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3212403ab5328a0aa58a07d0e323bd046886d92c).

## Scope rationale

P4-01–06 had already implemented structural target screening, unverified owner business context, timing/provenance lexical review, separated technical/decision evidence axes, a transparent target-review queue and full context-editor parity for alternatives. These remain accepted. P4-07 was authorised by the owner's "next" after P4-06 and is confined to P4. It does **not** implement a new business-value score, independent ground-truth verification, training or target approval.

Before P4-07, a review checklist asked about group/time leakage and the target's usefulness, but the recommendation response had no aggregate observation of repeated identifier-like values. The new increment supplies two kinds of information **without conflating them**:

1. **Observed evidence:** bounded counts of repeated values in identifier-like headers, a relevant *question* for grouped validation. Aggregate additional occurrences mean `nonmissing - distinct` in the scanned subset, not number of distinct real entities, total duplicate rows, evidence of fraud or leakage.
2. **Unverified operational evidence:** whether the user described an action, and explicit lack of independent verification of decision benefit, non-model comparator, label origin, prediction time, group independence and suitable deployment. All remain unknown/unestablished regardless of confident language in an owner description.

The review asks for the actual actor/action, comparator, measurable benefit and costs, independent label source, predictor availability and defensible split. **No status is automatically upgraded to safe, valuable, approved or fit for training.**

## Implementation and safety

- `backend/target_opportunities.py`: `_repeated_identifier_evidence(frame)` scans no more than 30,000 leading rows, 100 leading headers, eight identifier-like columns and five visible flags, once per GET. It exposes only column name, nonmissing observations, distinct values, additional occurrences, coverage and truncation status. Does not return identifier values, create data/model rows or call ML. `_decision_utility_review` attaches an always-unverified, never-training-authorised evidence contract to each candidate, preserving existing ranking, technical blockers, user-text status, 3+12 queue, soft warnings and abstention.
- `frontend/src/TargetOpportunities.tsx`: shared `DecisionUtilityEvidence` shows the same contract inside the existing top-three evidence disclosure and lower-ranked alternative review disclosure. It makes no independent HTTP call or write and never advances an unselected target.
- `tests/test_p4_review_queue.py`: four added deterministic synthetic regression cases verify 80 account observations with 40 distinct values and 40 extra occurrences, no identifier content in response, no false clearance on unique IDs, 30,000-row truncation and blocked rare-label abstention even with a user description.
- `frontend/tests/p4-review-queue-contracts.test.cjs`: new source/TS contract for bounded calculation, conservative flags, both UI disclosure locations, and no training calls.
- `frontend/e2e/p4-real-http-review-queue.spec.ts`: existing disposable synthetic 80-row CSV now uses intentionally repeated `row_id` values; both existing end-to-end scenarios assert observed repetition and unchanged manual selection/context-save with no unexpected training or experiments. No real datasets used.

**Unresolved empirical caveat:** Pattern matching on column names cannot independently establish entity identity. No detected repeats cannot prove independence because of source sampling, absent group columns and temporal dependencies. A partial scan explicitly discloses its limit. This does not replace train-fold-only preprocessing, proper grouped/temporal split or one-time final holdout checks in Expert ML.

## Exact accepted verification

- [P4 Actions #42590016405](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42590016405): **COMPLETED SUCCESS at exact source SHA `3212403ab532...`**. Job logs show **42/42 Python PASS**, **19/19 Node PASS**, TypeScript/Vite production build PASS, **2/2 real-HTTP Playwright Chromium PASS** using isolated synthetic backend/SQLite and existing approved local browser test protocol.
- [P1 frontend #42590016499](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42590016499): **COMPLETED SUCCESS at same exact source SHA**, including **5/5 isolated Chromium cases** and frontend verification.
- No failures appeared in these exact-source runs. Historical P4-06 initial failed locator test and its subsequent fix remain in earlier history and were not erased. All checks here are synthetic CI browser/source tests, **not** owner physical Tauri/WebView2 acceptance, final Windows distribution or real operational-value measurement.

## Scope disposition, residuals, next increment

**P4-07: SCOPED DEVELOPMENT ACCEPTED.** Still open: independent business utility, verified label origin, validated point-in-time availability, repeated real entities, practical split and leakage analysis, normative permission for sensitive outcomes, full end-to-end/native P4 journey and owner P4 phase closure. P8 remains NOT CERTIFIED.

**Recommended P4-08:** Provide an explicit owner-led suitability review/abstention journey that carries this unverified evidence into human target-choice review without converting a click or a text description into automatic modelling permission. Do not introduce P5/P6/P7/P8 work or ask the owner to redo accepted P3/W5 gates. Phase closure requires separate owner decision.
