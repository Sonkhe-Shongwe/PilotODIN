# PilotODIN — CONTINUE HERE (living cross-chat handoff)
**Updated:** 25 October 2026  
**Active repository:** [Sonkhe-Shongwe/PilotODIN](https://github.com/Sonkhe-Shongwe/PilotODIN)  
**Active branch:** `feature/live-dev-workspace-20261023`  
**Master QA and ongoing decisions:** [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)  
**Strategic research proposal:** [Master modes and target discovery](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md)  
**Latest target-intelligence research:** [Business semantics, opportunity ranking & leakage-free budget](./TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md)  
**Implementation priorities (complexity-last):** [Consolidated feature inventory & P0–P8 roadmap](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md)

## Latest owner Windows verification — consolidated P0/A4 entry PASSED (25 October 2026)

The owner uploaded two generated output folders from the new single-run `Run_PilotODIN_P0_A4_Verification.bat` launcher. Both were checked directly against `result.json`, four phase logs, and Pytest JUnit XML.

- **Both runs PASSED all four phases** against clean branch commit `5bf174e328bebf9cfabbbb17cd46ffae687f7785`: 99/99 frontend behavioural tests, TypeScript/Vite build, Python compile, and **149/149 deduplicated backend regression cases** (A2/A3 plus existing A4/approval/export foundations); zero failures, errors, skips or preflight blockers.
- The 25 October group/time split-key API/worker fixes therefore have **executed local regressions**, superseding the older "not yet rerun" test-status warning elsewhere in this document. Earlier owner UI evidence for invalid insurance incident-hour rejection remains separate.
- **Decision for minimum owner back-and-forth:** The *automated development-entry gate* is green. Proceed with one coherent A4 Deliver implementation batch and automated tests; arrange ONE combined owner Windows A3/A2/A4 functional, visual and native Save As acceptance session after the batch. Do not claim full A3/A4 manual signoff.
- No installed native/offline Windows app, bundled Qwen inference, actual physical 8 GB concurrent load, or all 24 Build E release scenarios were exercised by these local source suites.
- Detailed new evidence: [P0->A4 single-pass verification](./P0_A4_SINGLE_PASS_VERIFICATION.md) and [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2). No raw synthetic test artifacts or machine identifiers were uploaded to GitHub.

## Latest A4-1 development — SOURCE IMPLEMENTED, NOT YET RUNTIME-TESTED (25 October 2026)

Source state through commit `5a739433618e7253232567e350199140cf40f7c3` on `feature/live-dev-workspace-20261023`. **Do not interpret the prior owner's two 99/149 Windows passes as validation of these later changes.**

- `backend/reports.py` now offers a completed, selected A3 model's held-out evaluation as a version-scoped report evidence artifact. Only aggregate metrics and bounded per-class summaries are copied; individual held-out row predictions, feature rows and model binaries are excluded. The artifact is frozen into the report revision and cannot be imported across projects.
- HTML and PDF show an ordered evidence register and artifact-specific limitations/notes. Scientific metric labels keep correct capitalization (e.g., R²); regression metrics are not described as classification accuracy.
- `frontend/src/ReportWorkspace.tsx` now supports explicit exhibit ordering and refuses to export an out-of-date saved revision while the draft has unsaved title, narrative, evidence selection or ordering changes.
- Automated A4 tests were added: `tests/test_a4_model_evidence_reports.py` plus `frontend/tests/a4-model-report-composer.test.cjs`. The single-pass `Run_PilotODIN_P0_A4_Verification.bat` runner now includes the new backend tests, and Node's existing suite will discover the new frontend tests.
- **New A4 tests have not been executed** on owner Windows; the source was inspected and re-fetched from GitHub. Exact acceptance details, remaining reporting/visual work and the one-owner-validation strategy are in [A4 Deliver acceptance](./MACRO_A4_DELIVER_ACCEPTANCE.md).
- No hosted GitHub Actions, installer/release, actual 8 GB load validation, local Qwen generation or modification of existing end-user project data. Advance A4 in coherent tested batches, with one final owner Windows pull and smoke session rather than constant pull/test loops.

## Read this first when switching conversations/tabs

**This document is a continuity snapshot, not code.** GitHub branch history and the QA issue preserve implementation work; local Windows user screenshots/test outputs preserve acceptance observations. A new chat must verify current GitHub HEAD before editing and must not mistake an old QA issue-body status for the newer dated issue comments.

**User's current request:** Pause coding to reflect and **research/design** two important initiatives:
1. **Master Data Analyst / Master Data Scientist** automated professional workflows, including safe automatic cleaning, analysis, feature preparation, ML, findings and reports.
2. **Intelligent target discovery:** automatically find **worthwhile, defensible prediction objectives**, not just easy targets such as gender/device type. Prefer meaningful outcomes such as well-defined fraud investigation, future claim severity, demand, dropout or repayment risk where genuine labels and prediction-time inputs exist. Rank business usefulness and modelling readiness separately; abstain if no valid target.

They are **product proposals, not implemented phases**. The second initiative is a distinct subsystem enabling Master Data Scientist, sharing data understanding/quality infrastructure with Master Analyst. Read the [full research blueprint](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md), including agreed direction vs unresolved design choices. No new autonomy code was authored in this discussion.

## Confirmed design decision — preferred target belongs to the user

**Decision recorded 24 October 2026:** PilotODIN should automatically discover, evaluate, rank and explain meaningful target suggestions, but **the user must explicitly select the preferred target/output variable before any supervised training begins**. The user can choose a lower-ranked eligible option; critical validity/leakage risks still require resolution. After selection, Master Data Scientist automates predictor/input-feature preparation, split and model selection, evaluation and reporting, subject to review gates. This research decision is **documented, not coded or tested**.

Read both linked research documents for the precise distinction between selecting the output (human) and selecting input features (usually automated).

## Windows result — real insurance invalid hour rejection PASSED (24 October 2026)

Following the domain-guard patch, the user supplied a **Live Dev Predict Studio** screenshot for `insurance_claims_CLEANED` showing **`incident_hour_of_the_day must not exceed 23`** and the prediction panel reset to **Ready when you are**. This is direct Windows UI evidence that the `25` case was rejected without issuing a new prediction. A second screenshot confirms the unusual-value warning workflow still appears and displays held-out 82.0% accuracy, without revealing the exact output class or incident-hour input. **Valid-hour=12, negative vehicle count, experiment reopen/persistence, remaining sensitivity/baseline review, and focused Python regressions after this patch still lack demonstrated acceptance**. Update QA Issue #2 with observed evidence, not a blanket A3-complete claim.

## New Predict Studio functional evidence & targeted validation patch (24 October 2026)

Owner's insurance claims Predict Studio screenshots visibly displayed **missing-input training-fitted imputation warnings**, **out-of-training-range warnings** for deliberately extreme values, and an **82.0% held-out performance reference**. The exact prediction class/probabilities were not visible in the submitted crop. Source audit found that `HourOfDay` strict numeric checks did not recognise the real input `incident_hour_of_the_day`. The backend now recognises exactly that alias and `number_of_vehicles_involved` as a nonnegative integral count; a focused regression test also covers pre-change saved schemas. **This source patch is not Windows-tested yet**, so A3's final invalid-value and reopen/persistence acceptance remain open. No automatic blanket bounds were added to unusual financial amounts.

## Source follow-up — A3 group/time preflight consistency (25 October 2026)

A focused code audit identified that the group/date split key was counted toward the training resource estimate and could falsely exceed the local budget even though it is excluded from actual model fitting. The API preflight and background training worker now compute the **effective predictor exclusions before** model/memory validation while preserving the user's original exclusions in the saved experiment; target-as-split is blocked before queueing. Parametrised group/time regression coverage is committed. **Source contracts reviewed; Python tests after this fix still need the next consolidated Windows run.** This does not expand model rows, dense memory ceilings or AI capabilities, and A3 remains open for valid-prediction/reopen/remaining metrics proof.

## Current engineering status — do not overclaim

| Scope | What exists | Actual validation |
| --- | --- | --- |
| A2 Advanced Analytics/Quality/Explore | Linked chart filters/records, outlier and identifier investigations, data dictionary, saved versioned analyses, source-bound Deliver evidence; saved-history Open scroll fix | Owner ran Windows local script: **83 frontend tests + 107 focused backend tests passed**, TypeScript/Vite build passed. Some real UI walkthroughs and PDF/HTML exports were demonstrated. **A2 full manual visual signoff still incomplete.** |
| A3 Machine Learning packages 1–4 | Auditable feature preparation, risk acknowledgment, time/group split hygiene, train-derived held-out baseline, Evaluate-first handoff, bounded post-selection sensitivity, missing/unseen input caveats, model-family row/memory guardrails | Owner ran `tools/Verify_Macro_A3_Local.ps1` on Windows: **99 frontend tests + 27 focused backend tests passed**, TypeScript/Vite build and backend syntax compilation passed, ~23.2 s. **Interactive evaluation now demonstrated on the insurance_claims_CLEANED project (24 Oct): CV scores for 3 algorithms and baseline, held-out confusion matrix and metrics; owner reports normal operation. Predict domain validation, experiment reopen/persistence, lower-page evaluation details, 8 GB stress and full journey acceptance remain pending.** |
| Master Data Analyst / Scientist | Research, proposed architecture and risk boundaries | **Not implemented, not tested.** |
| Intelligent prediction-target discovery | Research on domain relevance, labels, leakage, ranking and abstention | **Not implemented, not tested.** |
| A4 Reports, B1 Ask ODIN, B2 universal progress, final offline desktop installer | Existing foundations and/or backlogs, still planned as later integrated release work | **No full integrated Windows/8 GB/offline installer acceptance.** |

**Important:** Previous A2/early A3 defect fixes are in GitHub; static contract reviews are not runtime tests. The user has demonstrated the two automated-checkpoint screenshots. Project files/history include original blueprints; check these where necessary before architectural shifts.

## Live-development/testing protocol

- Keep using the above branch in the local GitHub Desktop clone. Don't edit installed production releases.
- User Windows development launcher: `Start_PilotODIN_Live_Dev.bat` (frontend `127.0.0.1:5173`, backend `127.0.0.1:8000`). Dev data is stored separately in `.pilotodin-dev-data`.
- Existing isolated Python: `.venv-live\Scripts\python.exe` (not bare global `python`).
- A2 regression: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Verify_Macro_A2_Local.ps1`.
- A3 regression: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Verify_Macro_A3_Local.ps1`.
- The local scripts isolate test data; no native installer or Qwen3 inference testing is implied.
- The three development GitHub Actions workflows were switched to `workflow_dispatch` only due exhausted hosted minutes. Do **not** re-enable, dispatch or spend hosted minutes without a deliberate user request.
- Test in meaningful local batches; user prefers **no GitHub Desktop pull after every minor code commit**, and one consolidated Windows checkpoint per coherent package.
- **No installer** until all integrated macros, true offline Qwen3, 8 GB and final Windows release acceptance are ready.

## Product principles and hard constraints

- One source of truth for verified calculations; no invented statistics, scores, predictive guarantees or fabricated source records.
- Original datasets unchanged; version-scoped, reversible working operations and explicit approval for uncertain/high-impact changes.
- Auditable transformations, reasoned feature choices, leakage-safe pipelines, correct split/holdout design, failure/abstention paths.
- Local-first, offline-friendly and usable on an **8 GB Windows laptop**, with bounded compute and cancellation/recovery where required.
- Ask ODIN language generation must not become a substitute for deterministic analytical computation.
- Keep manual/Expert controls intact as Master Auto and Guided modes are added later.
- New product architecture should reuse Quality/Explore/Prepare/Model/Deliver and align with universal progress rather than create duplicate stores.

## Research/design pause — suggested next conversation

**Do not start coding automatically** when continuing this planning thread. Resume discussion about:
- How intelligent target discovery can identify true business outcomes from imperfect tabular schemas and when to **abstain**.
- The cleaning allowlist and escalation/approval model for autonomous Master Analyst.
- Shared orchestration/progress/evidence architecture and how to schedule it relative to A4/B1/B2.
- Acceptance examples and business-purpose clarification UX.
- Make architecture decisions **before** implementation, then scope milestones.

**Known tension:** More autonomy reduces user effort but increases the need for provenance, conservative defaults, honest uncertainty and reversible execution. “One click” may produce **an investigation plan and a small number of consequential approval requests**, not permission to silently rewrite the dataset.

## How to continue in a new ChatGPT tab

Open this document or give ChatGPT this exact instruction:

> Continue our PilotODIN project using GitHub repository `Sonkhe-Shongwe/PilotODIN`, branch `feature/live-dev-workspace-20261023`. First read `docs/CONTINUE_HERE.md`, `docs/MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md`, `docs/MACRO_A3_ML_ACCEPTANCE.md`, and GitHub Issue #2. We have **two research-stage initiatives**: autonomous Master Analyst/Scientist workflows and intelligent prediction-target discovery. A2 and A3 focused local automated checks have passed on Windows, but full UI/offline acceptance has not. Continue the strategic discussion without coding yet; respect manual-only Actions, isolated dev data, and no installer until final integration.

## Documentation update protocol

Whenever work meaningfully changes:
1. Commit implementation and regression coverage to the active branch (if coding).
2. Update **Issue #2** with observed test status, exact commit and open risks.
3. Update the relevant acceptance doc (A2/A3 or future macro).
4. Update this handoff when phase, user decision, validation status or next action changes.
5. Update the strategic research blueprint only for actual decisions/research findings; never relabel a proposal as implementation.
