# PilotODIN 1.0 | P4-11 Manual Target Structural-Blocker Disclosure

**Date:** 9 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Verified application SHA:** [`6251aa35abd2c298108a1608fc30cc35479945a7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6251aa35abd2c298108a1608fc30cc35479945a7)  
**Phase:** P4 ACTIVE only; P1/P2/P3 development-CLOSED; P5 not authorised; P8 not certified.

## Specific defect and bounded fix

The accepted P4-08 selected-target suitability panel matched chosen columns against `suggestions` and `other_reviewable` but did not match the backend's first five `blocked_examples`. Thus a manually selected `churn` column with only four labelled minority examples was shown as simply *not in the bounded P4 review queue* even though read-only backend evidence already contained an explicit minimum-class blocker. That message was incomplete and potentially misleading.

P4-11 extends the existing selected-target lookup to include `blocked_examples`. If the currently selected column is structurally blocked, an accessible `role="alert"` in the selected-target checkpoint displays the actual returned blocker reasons plus a clear **not recommended or approved for training** statement. For reviewable candidates, the panel distinguishes structural reviewability from independent validation. For a manually selected column absent from all bounded lists, it explicitly states that the screening list is incomplete and absence is not approval. The blocked-list disclosure also reveals the count of blocked named columns omitted beyond five.

The user still controls the manual target dropdown. This is a P4 read-only presentation change, not a new ML/training precondition or broad approval bypass. Existing Prepare/backend constraints and old versions remain unchanged; no saved model, project or owner file was modified.

## Exact tested files and evidence

- `frontend/src/TargetOpportunities.tsx`: look up selected target in 3+12 candidates and five blocked examples; display reasons and bounded omissions. No extra HTTP request, new write, automatic target or training action.
- `tests/test_p4_review_queue.py`: one added Python case for six blocked named outcomes with only five returned, no automatic training.
- `frontend/tests/p4-review-queue-contracts.test.cjs`: one added source contract checking the warning, bounded caveat and no training mutation.
- `frontend/e2e/p4-real-http-review-queue.spec.ts`: one new CI-only real-HTTP Chromium scenario with disposable 80-row CSV, 76/4 class split, explicit manual blocked selection, exact minority-class warning, clearing it, distinction for an unscreened identifier column, no unexpected writes and zero experiments.

**Passing source commit:** [`6251aa35abd2c298108a1608fc30cc35479945a7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6251aa35abd2c298108a1608fc30cc35479945a7)

| Evidence | Result |
| --- | --- |
| [P4 CI #42600161691](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42600161691) | COMPLETED SUCCESS; 53/53 Python, 22/22 Node, TypeScript/Vite PASS, 4/4 synthetic real-HTTP Chromium tests PASS |
| [P1 frontend #42600161703](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42600161703) | COMPLETED SUCCESS at identical SHA; 160/160 Node, TypeScript/Vite PASS, 5/5 isolated Chromium PASS |

**First unsuccessful run kept in history:** [initial source `e9b2d600a0b8...`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e9b2d600a0b8cc91afe5e544262d2152314ab073) had [P1 #42600044543](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42600044543) **FAIL** (missing closing JSX expression brace; TS2657 / TS1005), while [P4 #42600044326](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42600044326) was **CANCELLED** by subsequent push. Corrected code is only accepted by the subsequent green source-SHA CI, not by treating the earlier history as successful.

## Remaining gates and next focus

Current P4 candidate API intentionally caps visible reviewable suggestions at **3+12** and blocked examples at **5**. A manually selected column omitted from these bounded lists is clearly labelled **not screened in the visible bounded result**, not approved. A future P4-only scoped read-only candidate detail lookup could improve evidence on such deliberate manual selections, but would require its own version security, privacy, overflow and browser tests; it is **not implemented here**.

The owner previously requested **CI-first, milestone-based** acceptance with fewer downloads. P4-11 obeys this: no manual acceptance package, native installer work or owner data. Physical Windows native checks are reserved for a source-matched milestone and remain **UNTESTED**. No independently verified operational benefit, label origin, prediction-time inputs, actual grouped split, legal/fair use or owner phase-close decision has been obtained.

**Disposition:** P4-11 **SCOPED DEVELOPMENT ACCEPTED** based only on CI source/build and synthetic browser evidence. P4 as a whole remains ACTIVE; P5 NOT AUTHORISED; P8 release NOT CERTIFIED.
