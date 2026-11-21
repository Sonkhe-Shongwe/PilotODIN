# PilotODIN 1.0 | P4-12 On-demand Manual Target Inspection

**Date:** 9 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Corrected application SHA:** [`d9552f450f5a1c853b5c1e4f5b443a6d9a3235b4`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d9552f450f5a1c853b5c1e4f5b443a6d9a3235b4)  
**Phase status:** P4 ACTIVE only; P1/P2/P3 CLOSED for bounded development; P5 NOT AUTHORISED; P8 NOT CERTIFIED.

## Problem and bounded change

Previously the P4 review pane returned a deterministic, conservative human investigation list: 3 shortlisted + up to 12 other reviewable columns + 5 blocked named examples. After P4-11, manual selection of a *listed* blocked example showed its real structural reasons. But selected columns omitted by those limits, including the sixth blocked outcome or the sixteenth reviewable outcome, were still labelled only *not in the bounded list*. Existing backend evidence for those columns was not available in the selected-target checkpoint.

P4-12 adds a **single-column, on-demand, read-only inspection** triggered only after an explicit owner manual choice outside both bounded sets. The shortlist, its deterministic human review priority, other-list caps, abstention, target chooser, saved user descriptions and all preparation/ML scientific gates are unchanged.

## Backend API and evidence contract

`GET /api/projects/{project_id}/target-opportunities/inspect?expected_version=N&column=C`:

- Calls the existing local request policy and project lookup. The expected nonnegative Quality version is required; a stale version yields **409**. A missing, empty, unknown or too-long exact column yields **422**; unknown project gives **404**; an unapproved foreign Origin gives **403**.
- Calls `target_opportunities.inspect_manual_target(frame, version, column, contexts)` for **one exact column**, never re-ranks the other columns. It reuses the existing target structural check, prediction-time/label review, separately unverified decision axes and bounded repeated-identifier evidence. The existing repeated-identifier scan limits still apply: first 30,000 rows, first 100 headers, up to 8 identifier-like columns, up to 5 aggregate flags.
- Returns `project_id`, `version`, `column`, `inspection_scope=single_manual_column_not_ranked_or_approved`, `name_hint`, the candidate's aggregate evidence and `training_authorised=false`. No raw record identifier values, per-row labels, model fit, prediction outcome or score.
- An arbitrary manually selected field without a supported outcome-name hint (such as `account_id` or `feature`) is **explicitly blocked** by the P4 review, even if the user wrote a purpose for it. An outcome-named column that passes structural checks is only *structurally reviewable*, not independently validated or training-approved. Current Model Lab backend guards remain independent.

## Frontend and stale-response safety

`TargetOpportunities` first searches the existing visible 3+12 reviewable items and five blocked examples. It makes **no extra API inspection request** for these. For a manually chosen column outside the bounded list, an effect makes a current-project/current-version GET with the selected column URL-encoded.

The selected-target checkpoint displays a review-in-progress state and any request error conservatively. The async result is used only if its project, version, selected column, response scope and `training_authorised=false` match. React cleanup prevents applying a superseded response. The resulting selected checkpoint shows structural blockers or reviewability, observed label support, unverified group/time/value warnings and optional expanded single-column utility/timing review. No new write or model training control is introduced.

## Exact synthetic acceptance evidence

- [P4 #42603031835](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42603031835) **COMPLETED SUCCESS** at corrected source `d9552f...`: **56/56 Python**, **24/24 Node**, TypeScript/Vite production build **PASS**, **5/5** isolated *real HTTP* Uvicorn/SQLite/Chromium browser cases **PASS**.
- The new API tests cover a synthetic 80-row project with **22 structurally reviewable** and **6 rare-class blocked** named outcomes, plus an unrecognised identifier; they verify the original queue order unchanged, selected one-column evidence for omitted reviewable `outcome_21`, omitted blocked `rare_outcome_05`, an arbitrary non-outcome `account_id`, privacy, version mismatch **409**, project/column errors **404/422**, denied origin **403**, project isolation and no experiments or automatic choice. User descriptions remain unverified.
- The new browser scenario selects those same omitted columns, expands independent decision caveats, checks specific blockers and a stale-version negative GET, then verifies no unexpected writes or saved experiments.
- [P1 isolated frontend #42603031893](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42603031893) **COMPLETED SUCCESS** at same SHA: **160/160 Node**, frontend build PASS, **5/5** synthetic browser regressions PASS.
- Changing shared `backend/main.py` triggered other existing P1/P2/P3 source regression workflows at the initial source SHA. Those backend, report and semantic workflows **completed successfully**, but are compatibility regression evidence, not permission to re-open those closed phases.

## Historical failure and corrective scope

- First source commit [`bc5a0521b92191b45e63ed9d76152dd07efc1fe2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bc5a0521b92191b45e63ed9d76152dd07efc1fe2): [P4 #42602391649](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42602391649) **SUCCESS** with 56 Python, 23 Node and 5 real-HTTP tests; however [P1 frontend #42602391197](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42602391197) **FAILURE** (4/5 isolated browser cases) because an isolated mock audit did not recognise the new legitimate, current-version `GET .../target-opportunities/inspect` triggered by a manually selected column absent from its intentionally empty synthetic suggestions. Source contracts/build already passed there.
- Corrective commit [`d9552f450f5a1c853b5c1e4f5b443a6d9a3235b4`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d9552f450f5a1c853b5c1e4f5b443a6d9a3235b4) changes **only the synthetic P1 browser API mock** to permit and return a conservative **2-label, structurally blocked** response for the precise synthetic project/version/column and adds one P4 Node contract asserting the mock's fail-closed scope. Its follow-up P1 and P4 workflows both passed. This is not evidence that the initial red P1 run passed, nor proof of native Windows acceptance.

## Residual work and phase policy

The existing structural test for one target inspects candidate predictors across the loaded approved DataFrame; the *repeated-identifier* scan is bounded, but this does **not** establish a global CPU/time/memory budget for a very wide dataset. P4 source/resource resilience on large/wide synthetic frames is a justified subsequent bounded review if authorised. No memory or native Windows 8 GB device benchmark was performed here.

Other unmet P4 phase-exit evidence remains independent label provenance, real prediction-time feature availability, actual group/time split, measured benefit over non-model baseline, appropriate lawful/fair operation, a physical source-matched Windows Tauri/WebView2 walkthrough and a separate owner phase-close decision. The earlier P4-10 acceptance kit remains optional only at native milestones, not required after every CI increment.

**Disposition:** P4-12 **SCOPED DEVELOPMENT ACCEPTED** after corrected exact-source CI. **Overall P4 ACTIVE / owner native acceptance NOT TESTED / P5 NOT AUTHORISED / P8 NOT CERTIFIED**. No owner projects, original data, saved reports, installed application or models modified.
