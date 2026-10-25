# PilotODIN — CONTINUE HERE (living cross-chat handoff)
**Updated:** 25 October 2026  
**Active repository:** [Sonkhe-Shongwe/PilotODIN](https://github.com/Sonkhe-Shongwe/PilotODIN)  
**Active branch:** `feature/live-dev-workspace-20261023`  
**Master QA and ongoing decisions:** [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)  
**Strategic research proposal:** [Master modes and target discovery](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md)  
**Latest target-intelligence research:** [Business semantics, opportunity ranking & leakage-free budget](./TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md)  
**Implementation priorities (complexity-last):** [Consolidated feature inventory & P0–P8 roadmap](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md)

## Owner's first complete A4 consolidated Windows run (25 October 2026)

**Executed against clean checkout `f9c122448e01af61f4aacf31c4229c27bb54ea6e`.** Owner supplied the generated single diagnostics ZIP `pilotodin-p0-a4-readiness-s_9yn_ur.zip`, including `result.json`, phase logs and pytest JUnit XML.

- **Frontend:** 106/106 Node tests passed; TypeScript typecheck and Vite production build passed.
- **Backend:** Python compile passed; 167 collected Pytest cases: **166 passed, 1 failed, 0 errors, 0 skipped**.
- **Only failure:** `tests/test_a4_quality_audit_reporting.py::test_explicit_quality_capture_is_read_only_and_reportable`, which asserted the substring `preview` was absent from the string representation of all report evidence. The correct privacy disclaimer literally says "No record-level values, row identifiers, source previews ... are exported," triggering a **false-positive assertion** even though the preceding checks verified absence of synthetic private category strings and actual `preview` fields in the persisted audit. PDF/HTML checks later in that same test did not execute because the assertion stopped the test.
- **Fix committed:** `53db533921ac2b4c5b08bd8056cf6e9f6d851c93` changes the test to assert absence of an actual `preview` result field and `row_values` key, not the harmless word in an explanatory sentence. No product or source-data change was necessary.
- **Status:** Previous A4 source has been executed, with 166 cases passing. Full green A4 automated verification remains **PENDING one post-fix execution**; do not claim the edited test or full suite passed on the new commit. Native Windows Save As, physical 8 GB, bundled inference and complete manual PDF/UI acceptance are still untested.

## Post-fix full A4 consolidated Windows automated verification: PASS (25 October 2026, approximately 11:06 SAST)

The owner supplied the second, post-fix single diagnostic ZIP (`pilotodin-p0-a4-readiness-mrmk7kls.zip`) and its `result.json`, all four phase logs and Pytest JUnit XML were examined.

- **Exact tested code:** clean `feature/live-dev-workspace-20261023` checkout at `4b555d934ba7f6d3012141e1e3b53138590fb863`; `uncommitted_changes=false`; no missing prerequisites.
- **All four phases PASS:** 106 of 106 frontend Node behavioural tests, TypeScript/Vite production build, Python syntax compilation, 167 of 167 combined A2/A3/A4 backend regression tests (0 failed, 0 errored, 0 skipped).
- Pytest reports `167 passed` on the post-fix run. The earlier Quality audit privacy wording false-positive has been corrected and now passes as part of the suite.
- `automated_status=PASS`, `preflight_blockers=[]`, with isolated `PILOTODIN_HOME`. This closes the **automated A4-1/A4-2/A4-3 integration gate** at this specific commit, superseding the earlier 166/167 result.
- **Scope boundary:** These runs are not independent visual QA, real user Prepare→Train→Predict, on-screen PDF pagination inspection, Tauri native Save As, bundled Qwen/offline operation, real 8 GB stress test, installer or the original E-01 through E-24 release acceptance. Those remain open and must be evaluated separately.
- **Decision:** Do not ask the owner to rerun unchanged tests. Proceed to one short combined A2/A3/A4 functional/visual acceptance session, prioritizing report composition, model/Quality/Explore evidence, saved revisions and readable HTML/PDF. Native Save As is still a separate known implementation/verification gap.

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

## A4-2 snapshot graphics in reports — SOURCE IMPLEMENTED, UNTESTED (25 October 2026)

Following A4-1 selected-model report evidence, a new bounded presentation layer `backend/report_charts.py` now renders **bar, histogram and line** saved Explore aggregates as self-contained HTML SVG and ReportLab PDF vector figures, with identical frozen source points, visible dataset version, evidence table, and bounded/sampled caveat. `backend/reports.py` verifies saved chart + configuration hashes before embedding the visual projection in the immutable revision. Scatter/box graphics, native Windows Save As and model plots are not claimed. `tests/test_a4_frozen_chart_visuals.py` adds render parity, clipping, escaping, invalid point and immutable revision checks and is included in the one-pass runner.

**No execution of these new A4 tests or rendered output in owner Windows was demonstrated.** Continue with automated-test-first A4 improvements and one combined final owner test only when source is sufficiently frozen. The earlier A2/A3 99-frontend/149-backend pass evidence is the baseline for the earlier pre-A4 commit, not an A4 signoff. See [A4 Deliver acceptance](./MACRO_A4_DELIVER_ACCEPTANCE.md) and [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2).

## A4-3 checkpoint: Quality audit reports and tamper-proof exports (25 October 2026)

- Explicit Deliver action **Capture current Quality audit** calls `POST /api/projects/{project_id}/report-quality` with the current approved Quality version. It freezes only aggregate findings/counts, current active-approved-action count, exact dataset version, source digest and static cautions in `report_quality_audits_v1`. No approval or edit occurs, and no preview rows, user-specific category example strings, replacement values or raw receipt data enter the report evidence.
- Project-scoped audited Quality snapshots appear in Deliver alongside Explore/investigation/selected ML exhibits. They are digest-verified before save, retained at the original dataset version, and marked historical on subsequent version changes.
- All saved report revisions now reverify `content_sha256` on load/export, rejecting tampered or unreadable revision blobs with 409.
- Frontend now checks report HTTP MIME type and HTML/PDF signature before initiating download, and reports **download started** rather than claiming a successful disk save. Native Save As remains unverified/unimplemented in the new A4-3 changes and stays a later Windows integration requirement.
- Added `tests/test_a4_quality_audit_reporting.py`, `frontend/tests/a4-quality-export-gates.test.cjs` to the consolidated verification inventory. **All post-baseline A4-1/A4-2/A4-3 tests remain UNEXECUTED on owner's Windows clone.** Historic 99 frontend /149 backend passes covered the prior P0 commit only; don't describe these A4 features as tested or release-accepted.
- Next planned milestone: finish any narrow A4 UX/test corrections, then **one consolidated local automated test followed by one manual Windows acceptance session**, not repeated owner pulls after each commit. Detail: [A4 acceptance](./MACRO_A4_DELIVER_ACCEPTANCE.md), [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2).

## A4 source consolidation checkpoint — awaiting one Windows regression run (25 October 2026)

After implementing A4-1 ML reports, A4-2 saved vector chart illustrations, and A4-3 read-only Quality audits and report integrity, the source was consolidated for **one** owner Windows automated verification pass.

- The report load path now rejects a correctly hashed revision transplanted from another project or one with an invalid evidence/version schema. An API regression case covers project substitution, preserving privacy and report provenance.
- `tools/Verify_P0_A4_Readiness.py` now packages `result.json`, test-phase logs and Pytest JUnit evidence into one `%TEMP%\\pilotodin-p0-a4-readiness-*.zip` **without including synthetic project data or model files**; the exact path is printed.
- The Windows launcher `Run_PilotODIN_P0_A4_Verification.bat` now **pauses at the end** rather than silently closing. This replaces the previous manual ZIP-making and missing-output difficulty.
- The new A4 tests **have not run yet**. Previous two Windows 99/149 all-pass runs remain true evidence for the earlier P0 commit `5bf174e3`, not this A4 source checkpoint. Do not infer pass counts for the updated suite.
- **Owner next action:** ONE GitHub Desktop fetch/pull on `feature/live-dev-workspace-20261023`, ONE double-click of the verification BAT, share the ZIP. Resolve actual failures in small code patches first; defer full manual UI testing until automated green.
- **Unresolved:** native Tauri Save As, manually inspected paginated PDF and A2/A3/A4 browser journeys, offline native bundled model, physical 8 GB, final E-01 to E-24. A4 does not have full acceptance or a release build.

See [single-pass verification](./P0_A4_SINGLE_PASS_VERIFICATION.md), [A4 Deliver acceptance](./MACRO_A4_DELIVER_ACCEPTANCE.md) and QA Issue #2.

## First owner Deliver report artifact review (25 October 2026) — partial functional PASS

The owner provided a real Deliver screenshot plus HTML and 2-page PDF for report revision 2 on `insurance_claims_CLEANED` (v0). The only selected/exported exhibit is **Quality audit**; saved ML model evaluations and Explore analyses are listed but unchecked. Rendered pages were inspected: **legible, no obvious clipping**. PDF and HTML show matching 1,000 records, 39 columns, 9 findings, 0 active Quality corrections, source/version IDs and finding counts, with no claim-level preview rows.

Two presentation issues emerged: the PDF placed its findings section heading and only one row at the bottom of page 1; and a generic "first 35 findings" caveat was displayed although this audit has only nine. **After this user export**, source fixes added `CondPageBreak(160)` for PDF observations, made the truncation caveat conditional, and added regression coverage in `tests/test_a4_quality_audit_reporting.py` (fix checkpoint `f2b07731`). These newest changes **have not yet been executed on owner Windows**; earlier 106 frontend / 167 backend green suites predate them.

**Remaining acceptance:** one mixed model + Explore chart + Quality audit exported report; ordering/immutable revisions; visual PDF chart and layout; native Tauri Save As. Owner can save a more meaningful title and authored interpretation. See QA [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2#issuecomment-6395848645). Avoid requesting several individual repeated tests.

## Combined report revision 3 — real HTML/PDF review (25 October 2026)

Owner supplied `pilotodin_report (1)(1).html` and `pilotodin_report_e598f981d064_rev3.pdf` from insurance project `insurance_claims_CLEANED`. Report ID `e598f981d06446968e98df1db8a2fe40`, **revision 3**, content SHA-256 `9fc5f6ab39c65ec21a7e1ac791af4020fb2505ac8ac40b39b5aecbbd17cdb97c`.

**Verified against the actual artifacts:** Both formats include the three distinct ordered v0 exhibits Quality Audit → Model Evaluation (`logistic_regression`, target `fraud_reported`) → saved Explore Snapshot. Quality evidence records 1,000 rows/39 columns/9 findings/0 active corrections. Selected-model held-out metrics match across formats: accuracy 0.82, macro F1 0.73776, ROC AUC 0.81619, 200 observations. Class `Y` recall **0.53061** is a material qualification, not a production guarantee. The chart's seven values (MD 60540, PhD 60145, Masters 58200, JD 57505, High School 57300, College 56080, Associate 54200) and figure render in HTML SVG and PDF vector output; no obvious clipping was observed. PDF is **5 pages** with awkward heading/table splits.

**Semantics issue discovered:** saved Explore objective/title is `Claims by region` but recorded chart parameters are `aggregation=median`, `x=insured_education_level`, `y=total_claim_amount`. This is NOT claims by geographic region and NOT a sum. The exported chart is numerically sourced correctly but must explicitly state its aggregation and true grouping field.

**Immutability:** The old captured Quality audit includes the legacy 'first 35 findings' disclaimer despite having only 9 findings; it was already frozen before the later conditional wording fix. Do not mutate the original saved audit or revision to hide historical wording. A fresh explicit audit capture is needed if current wording is desired.

**Source fixes committed after inspecting rev3:**
- `backend/report_charts.py` derives `measure_caption` from the existing immutable chart settings, so the HTML SVG figure caption/y heading and PDF chart heading show **Median of total_claim_amount by insured_education_level** (and histogram always states Frequency).
- `backend/reports.py` now uses `KeepTogether` on compact exhibit headings+metric tables and compact verified observation tables, avoiding orphaned Model/Explore section headings and one-row fragments.
- New regression `tests/test_a4_mixed_report_pagination.py` exercises a synthetic three-exhibit PDF/HTML; `tests/test_a4_frozen_chart_visuals.py` asserts median/grouping and histogram labelling. New test included in `tools/Verify_P0_A4_Readiness.py`.

**QA boundary:** The provided real rev3 HTML/PDF predates the last targeted code refinements, and there has been **no new executable local 106/167 suite run or post-change PDF render**. Thus mixed evidence presence/value parity is a **functional PASS**, but final A4 visual/pagination acceptance and native Tauri Save As remain OPEN. No changes to uploaded data or pre-existing saved revisions. User-authored generic report title and empty narrative should be improved for a professional final report.

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
