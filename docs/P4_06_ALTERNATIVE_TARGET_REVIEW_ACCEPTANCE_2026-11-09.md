# PilotODIN 1.0 | P4-06 Alternative Target Review Acceptance

**Date:** 9 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Phase:** P4 ACTIVE, P1/P2/P3 CLOSED for bounded development. P8 NOT CERTIFIED.  
**Engineering changes:** `55c8c8fa5d6f2bfb8297c94328a705b82c7d7e68`, `a08a078ce4ae19623be0042169887585673b7d39` (browser selector correction).

## Scope and reason

P4-05 had already exposed the top three candidate targets with reviewed observations, unresolved decision and prediction-time questions, and an opt-in, local, version-scoped business context editor. Lower-ranked but structurally reviewable alternative candidates had only a short label-count line and a selection button. Thus the user could explicitly select an alternate without the same context and evidence visibility. This was **a human-review completeness gap**, not proof the target screening or numerical profile was wrong.

P4-06 extends only `frontend/src/TargetOpportunities.tsx` to show, for each of up to 12 existing alternatives:

1. A collapsible review with position (not business value), observed label support, separately labelled technical evidence and unverified decision context.
2. The existing backend-issued required evidence steps: action/decision, label provenance, prediction moment and safe validation, plus optional missing-label and leakage/uncertainty clues. Bounded existing header/timing hints are explicitly not proof.
3. The already implemented `TargetContextEditor`, with the same explicit Save action, local origin/project/Quality-version/column validation and `onSaved` refresh. A saved owner description can promote a candidate in the pre-existing *question-review* order; it cannot prove its validity.
4. The existing independent **Review this alternative target** action and normal Prepare flow, never automatic training or change of an original dataset.

No backend ranking, SQL schema, statistical computation, model logic, native Windows integration, packaging or security approval boundary was changed. Blocked candidates remain blocked, no target remains automatically chosen, and the shortlist/alternatives cap remains 3 + 12.

## Exact verification evidence

- [P4 run #42588769422](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42588769422) at source commit `a08a078ce4ae19623be0042169887585673b7d39`: **COMPLETED SUCCESS**; 38/38 Python synthetic tests; 18/18 Node tests (including new P4-06 source contract); TypeScript/Vite production compile/build PASS; 2/2 real HTTP Playwright Chromium tests PASS using a disposable backend and synthetic 80-row CSV.
- First browser journey: existing review list/ordering, alternative expanded evidence, at least four required checks and explicit selection; no spontaneous POST or experiment.
- Second browser journey: user intentionally enters four synthetic context fields for a lower-ranked alternative, submits exactly one allowlisted local POST, sees refreshed question-review ordering, and confirms the saved data remains `user_described_not_independently_verified`, with no training and no experiment.
- [P1 frontend #42588769353](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42588769353) at same SHA: **COMPLETED SUCCESS**, including 5/5 isolated Chromium regression scenarios, frontend contracts and Vite build.
- Initial [P4 run #42588535934](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42588535934) at `55c8c8fa...`: **FAILED** in browser only due to overly broad Playwright `other.locator('summary')` matching nested controls. Backend/Node/build passed; [P1 frontend #42588535815](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42588535815) passed. `a08a078ce...` scoped the parent locator to `:scope > summary`, and all affected CI was rerun successfully. The failure remains part of QA history.

**Evidence class:** Synthetic Linux-hosted browser, real FastAPI HTTP and SQLite + source/build checks. **NOT:** owner physical Windows/Tauri WebView2 acceptance, native app installed QA, full business verification, bundled offline local model, 8 GB AI/ML combined load or a release certificate.

## Acceptance and next decision

**P4-06 scoped development ACCEPTED** based on the completed green CI at its exact code SHA. This is not **overall P4 closure** or proof that target choice is ethically, operationally or statistically safe. No direct user project data was touched; the browser's synthetic metadata save was deliberate and disposable.

**Remaining P4:** Operationally grounded decision/action utility criteria, independently substantiated label origin and prediction moment, repeated entities/group leakage decisions, valid abstention, full human selection and deliberate Prepare journey with acceptance evidence. Owner phase-close decision remains separately required. Do not reopen accepted P1/P2/P3 gates or implement P5/P6/P7/P8 without authorisation.
