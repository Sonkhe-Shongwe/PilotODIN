# PilotODIN — CONTINUE HERE (living cross-chat handoff)
**Updated:** 24 October 2026  
**Active repository:** [Sonkhe-Shongwe/PilotODIN](https://github.com/Sonkhe-Shongwe/PilotODIN)  
**Active branch:** `feature/live-dev-workspace-20261023`  
**Master QA and ongoing decisions:** [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)  
**Strategic research proposal:** [Master modes and target discovery](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md)  
**Latest target-intelligence research:** [Business semantics, opportunity ranking & leakage-free budget](./TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md)  
**Implementation priorities (complexity-last):** [Consolidated feature inventory & P0–P8 roadmap](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md)

## Read this first when switching conversations/tabs

**This document is a continuity snapshot, not code.** GitHub branch history and the QA issue preserve implementation work; local Windows user screenshots/test outputs preserve acceptance observations. A new chat must verify current GitHub HEAD before editing and must not mistake an old QA issue-body status for the newer dated issue comments.

**User's current request:** Pause coding to reflect and **research/design** two important initiatives:
1. **Master Data Analyst / Master Data Scientist** automated professional workflows, including safe automatic cleaning, analysis, feature preparation, ML, findings and reports.
2. **Intelligent target discovery:** automatically find **worthwhile, defensible prediction objectives**, not just easy targets such as gender/device type. Prefer meaningful outcomes such as well-defined fraud investigation, future claim severity, demand, dropout or repayment risk where genuine labels and prediction-time inputs exist. Rank business usefulness and modelling readiness separately; abstain if no valid target.

They are **product proposals, not implemented phases**. The second initiative is a distinct subsystem enabling Master Data Scientist, sharing data understanding/quality infrastructure with Master Analyst. Read the [full research blueprint](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md), including agreed direction vs unresolved design choices. No new autonomy code was authored in this discussion.

## Confirmed design decision — preferred target belongs to the user

**Decision recorded 24 October 2026:** PilotODIN should automatically discover, evaluate, rank and explain meaningful target suggestions, but **the user must explicitly select the preferred target/output variable before any supervised training begins**. The user can choose a lower-ranked eligible option; critical validity/leakage risks still require resolution. After selection, Master Data Scientist automates predictor/input-feature preparation, split and model selection, evaluation and reporting, subject to review gates. This research decision is **documented, not coded or tested**.

Read both linked research documents for the precise distinction between selecting the output (human) and selecting input features (usually automated).

## New Predict Studio functional evidence & targeted validation patch (24 October 2026)

Owner's insurance claims Predict Studio screenshots visibly displayed **missing-input training-fitted imputation warnings**, **out-of-training-range warnings** for deliberately extreme values, and an **82.0% held-out performance reference**. The exact prediction class/probabilities were not visible in the submitted crop. Source audit found that `HourOfDay` strict numeric checks did not recognise the real input `incident_hour_of_the_day`. The backend now recognises exactly that alias and `number_of_vehicles_involved` as a nonnegative integral count; a focused regression test also covers pre-change saved schemas. **This source patch is not Windows-tested yet**, so A3's final invalid-value and reopen/persistence acceptance remain open. No automatic blanket bounds were added to unusual financial amounts.

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
