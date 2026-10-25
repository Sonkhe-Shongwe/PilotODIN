# P4 — Conservative prediction target opportunities (first increment)

**25 October 2026: source implemented on active development branch; focused owner Windows verification PENDING.**

## Product contract and reason for scope

The user's binding complexity-last roadmap places user-governed target recommendations after P3 deterministic semantic understanding but before expensive Master Modes and P7 orchestration. This increment provides *structural screening and an unverified decision question*, not learned target success, full business-value rankings, automatic selection or automated modelling.

Earlier owner gates remain accepted: P3 `pilotodin-p3-repair-x8uxs9kq.zip` **9/9 Python and 4/4 Node PASS** with the original P3 frontend Vite PASS; P5 slot **25/3**, factual progress **18/7 + Vite**, cooperative cancellation **45/12 + Vite**. No need to rerun them as separate owners' workflows.

## What the first P4 increment implements

**Backend** `backend/target_opportunities.py`:

- Scans current approved working dataset **read-only**; generates candidate target *hypotheses* only from explicit outcome/name clues (e.g., fraud, churn, default, status, return, case outcome, future cost/revenue). Arbitrary numeric/date columns and ID-like headers are NOT recommended merely for existing.
- For every named candidate, reports actual aggregate **non-missing label count, missing label count, distinct observed labels, minimum class count** for classification, and a *tentative* task kind. No label values or source rows are returned.
- **Hard blockers:** identifier-like columns, date/time column targets, insufficient labelled records (30 minimum), constant or all-missing labels, classification classes with fewer than six rows, unsupported high-cardinality free text, regression labels that aren't finite numbers, zero usable nonconstant predictors, more than the current `engine.MAX_ML_LABELLED_ROWS` limit, and headers that resemble **model-derived scores, probabilities or predictions** rather than verified outcomes.
- **Soft/contextual warnings:** potential outcome leakage/proxy fields, missing-label selection bias, sensitive label use, reported fraud is not confirmed fraud, and always unverified label provenance, prediction time, group/time split and operational action.
- Shortlists at most **3 reviewable** candidates. The deterministic displayed order is observed label support followed by field name; **not** measured business value, fairness, performance or calibrated confidence. Other blocked examples are shown separately. If none are eligible, the service **abstains** and recommends descriptive analysis or an explicitly defined verified target. Each candidate has `business_relevance: unverified`, `safe_to_train_automatically: false`.
- No fitting, cross-validation, model selection, changed data, new task scheduling, label value preview, cloud call, Qwen model or user-target choice occurs.
- **Known limit:** screening the number of labelled rows does not fully prove memory fit, temporal leakage safety, outcome label availability or decision utility. The existing Model Lab preparation, split, resource and feature-risk checks still apply on user selection; an outcome that looks plausible may remain inappropriate for use.

**API** `GET /api/projects/{project_id}/target-opportunities?expected_version=N`:

- Reuses the P3 project's **server-side `_local_request(request)` guard** before project metadata, a version-pinned approved Quality working frame, stale version `409`, missing/invalid version `422`, missing project `404`.
- GET only; zero persisted target selection. Never calls `engine.run_training`, reserves a P5 slot, changes Quality or creates a model experiment.

**UI** `frontend/src/TargetOpportunities.tsx` integrated into the existing **Prepare → Define your prediction target** view in `App.tsx`:

- Displays a maximum of 3 conservative opportunities with hypothetical business questions and observed label counts. Blocked named fields can be inspected with rationale. The UI explicitly says **UNVERIFIED** and asks for intended decision and label definition; there is no false predictive score or green-ready guarantee.
- **Only a real button click** `Review this target` calls the parent `onChooseTarget(column)`. It sets the normal user target for *existing* preparation review. No automatic selection or training. The original manual dropdown remains available, with old unvalidated “suggested” suffixes removed.
- Both manual and recommended target changes immediately clear stale previous-target `prep`. New preparation loading also clears it. `startTrain()` refuses a plan if `prep.target !== target`, and the server independently revalidates the chosen dataset version, split, labels and models.
- Read-only result is keyed and fetched by `projectId + approved dataset version`, with request cleanup and result-version comparison. No additional interval polling, model runtime, audio or native packaging.

## Regression package — owner gate not yet run

- `tests/test_p4_target_opportunities.py`: **12 isolated synthetic tests** for insurance fraud-reported warning, rare class labels and too few records, completely unrelated numeric fields (abstention), plausible revenue and time-to-resolution duration regression without performance claims, identifiers/empty/constant labels, derived scores/probabilities/predictions, missing label aggregate privacy, over-cap labels, deterministic bounded suggestions, duplicate column refusal, project/version/local-origin safety and no new experiments.
- `frontend/tests/p4-target-opportunities-contracts.test.cjs`: **4 source-contract tests** for no AutoML calls, local/version GET guard, explicit user click + stale-preparation reset, and backend regression inventory.
- Future `tools/Verify_P0_A4_Readiness.py` includes the new P4 Pytest file once. No hosted GitHub Action.

**One focused Windows verification:** After pulling current `feature/live-dev-workspace-20261023`, run `Run_PilotODIN_P4_Target_Opportunities.bat`. It calls `tools/Verify_P4_Target_Opportunities_Local.py`, running **P4 new Pytests + adjacent accepted P3 semantic Pytests (affected API imports)**, P4 + P3 Node source contracts and **one TypeScript/Vite build** (new UI component and App changes). Isolated synthetic `PILOTODIN_HOME`, one `pilotodin-p4-targets-*.zip` in Windows Temp. If fails, upload that ZIP; if passes, send PASS and no repeated old P5/P0/A4 standalone tests are needed.

**Verification honesty:** Source files were written to GitHub and re-fetched/source-inspected; **no NEW P4 Pytest/Node/Vite execution on owner's Windows machine has yet occurred**. Do not mark P4 green based on P3/P5 passes.

## Next after one green focused gate

Optionally obtain user-confirmed target metadata (outcome definition, label source, prediction moment, decision action, entity granularity) and preserve it version-aware and read-only; only then can richer decision-value ranking distinguish actual business value from header semantics. Require **explicit user selection** and preserve all existing split/leakage, approval, resource and training safeguards.

**Still separate:** Larger P5 general task scheduler, P6 Master Analyst/Scientist, P7 ODIN orchestration and true E2 licensed/disconnected local Qwen + simultaneous 8 GB memory test, and P8 offline installer/release E-01–E-24.
