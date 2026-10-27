# PilotODIN Macro A3 — Machine Learning reliability checkpoint

**Branch:** `feature/live-dev-workspace-20261023`  
**Checkpoint:** A3-1 through A3-4: audited features, leak-aware splits, held-out evaluation, bounded post-selection sensitivity, conservative 8 GB-local resource controls and group-identity integrity  
**NEW Windows acceptance evidence (24 October 2026, later screenshots):** The user tested a saved Logistic Regression prediction in `insurance_claims_CLEANED` using invalid `incident_hour_of_the_day=25`. Live Dev displayed the server validation error **`incident_hour_of_the_day must not exceed 23`**, and the output panel displayed **Ready when you are** instead of a new prediction. **PASS: this named invalid-hour case was rejected on Windows.** A separate screenshot displays continued out-of-training-range warnings for atypical numeric inputs and the previously observed held-out 82.0% accuracy reference; the precise predicted class and the actual incident-hour value are outside the captured viewport. No proof yet for a specifically valid-hour=12 test, `number_of_vehicles_involved=-1`, save/reopen, or new focused pytest execution. Do not claim full A3 signoff.

**Predict Studio UI evidence (24 October 2026):** Owner supplied a real `insurance_claims_CLEANED` prediction workspace showing training-fitted missing-input imputation notices, observed-range out-of-distribution warnings for extremely large/small insurance values, and the held-out 82.0% accuracy reference. The predicted class/probabilities are above the captured viewport, so those numbers were not independently inspected. This verifies warning visibility, **not** rejection of semantically impossible inputs. Source review identified that the strict clock domain covered `HourOfDay` but not the real column `incident_hour_of_the_day`; a targeted backend fix also guards the non-negative whole-number `number_of_vehicles_involved`. Added same-file regression tests including persisted-schema fallback, **awaiting local execution**. Existing historical experiment forms may not display the new HTML constraints until retraining, but the patched server checks at prediction time. No blanket prohibition of signed `capital-loss` amounts or all out-of-range values.

**Acceptance state (owner Windows checkpoint, 24 October 2026):** Focused local checks **passed: 99 frontend tests, 27 backend tests**, TypeScript/Vite build and Python syntax compilation (~23.2 seconds). **Interactive training → Evaluate was observed on 24 Oct 2026 using insurance_claims_CLEANED: populated CV leaderboard, post-selection held-out metrics and confusion matrix. This is partial functional acceptance, not a full A3 sign-off. Predict-domain inputs, saved experiment reopening, lower-page baseline/explainability details, realistic 8 GB stress and installed/offline desktop acceptance remain pending.** This is not an exhaustive backend suite. See [living handoff](./CONTINUE_HERE.md).

### A3 preflight follow-up — split metadata should not consume model memory (25 October 2026)

After Windows demonstrated the invalid-hour prediction rejection, a source audit found that group/time split keys were removed from predictors **only after** the 8 GB resource guard had already estimated model input size. A high-cardinality group ID or timestamp could therefore cause an invalid false refusal of an otherwise eligible experiment.

**Source fix committed:** both `backend/main.py::new_experiment` and `backend/engine.py::run_training` now compute effective training exclusions (`excluded_features` plus any non-random split key) **before calling** `validate_config`. The original user's manual exclusion list is kept unchanged in the saved configuration, while the split column remains available for its real validation strategy. The API now also rejects target-as-split immediately rather than enqueueing a doomed experiment.

**Coverage committed:** `tests/test_ml_a3_preparation_and_split_safety.py` parametrically checks group and time flows, ensures split columns are absent from preflight and fitted input schema, verifies the source frame and user exclusions remain unchanged, and rejects target-as-split.

**Verification status:** Re-fetched committed files and verified source contracts; **new Python tests have not yet run on owner Windows**, and no full A3/8 GB acceptance is claimed. Existing Windows evidence for the insurance prediction hour guard is separate. The next consolidated local A3 script run will include the new tests.

## What changed

1. Prepare returns one backend-authored, version-dependent audit row per candidate feature: numeric/categorical role, null and distinct counts, treatment used by the existing scikit-learn pipeline, and review reasons. Empty-only features are excluded by the existing backend `validate_config`; target and split keys are never predictors.
2. The analyst still controls manual feature exclusions. Applying suggested high-risk exclusions **merges** them with prior selections and must never remove a manually excluded field.
3. For predictors resembling identifiers or post-outcome leakage, Model Lab shows a named review gate. The **backend** checks the same risk list and rejects training without an explicit `acknowledge_feature_risks` or exclusion. Accepted experiments persist `reviewed_high_risk_features` and the acknowledgement flag for audit.
4. Time-ordered holdout refuses to divide observations with an identical timestamp between development and final test. Chronological cross-validation now splits distinct timestamp groups, preventing one instant from appearing in both development-training and validation folds. A3-4 additionally encodes grouped validation IDs without stringifying missing labels, preventing null IDs from collapsing into a legitimate literal `(Missing group)` value.
5. A3-2 adds a training-derived simple baseline scored alongside the selected model on identical held-out rows, conservative reliability warnings, unseen-category/missingness explanations, explicit uncalibrated probability labels, and Evaluate-first reopening of experiments.
6. A3-3 adds a visible conservative resource plan before training (up to 30,000 labelled rows and 256 MB estimated dense training-matrix allocation; these are not measured peak RAM usage). The backend rechecks limits after actual exclusions and refuses oversized experiments without modifying the source data.
   A3-4 tightens this to a full-labelled-row upper bound for uneven group splits, plus stricter selected model-family limits for SVM/SVR (5,000 rows) and KNN (12,000). The backend owns the limits; Model Lab discloses them in context.
7. A3-3 adds bounded post-selection permutation sensitivity: up to 64 deterministic held-out observations, up to 8 evenly distributed original input fields, two shuffles each, one process. It stores sample counts, covered feature counts, seed, metric, directional scores and limitations with the immutable final evaluation, **never** using them for model selection. Unavailable or older analyses show an explicit no-diagnostic explanation.
8. Existing leakage barriers remain: transformations fitted inside training CV folds, held-out test evaluated only after a user selects a model, one-time selected model, quality version pinning, group-aware split support and server-side prediction domain validation.

**Limitations:** Name- and cardinality-based risk checks are *heuristics*, not proof of leakage or feature relevance. No exhaustive, causal, individual-prediction or globally validated feature importance, calibrated confidence or universal domain inference is claimed. Bounded permutation analysis is sampling-limited and post-selection only. Duplicated entities, time-dependent labels and target timing require business review. A3 remains open until full preparation, training, evaluation and prediction acceptance.

## How to run the focused local tests

Use the existing development clone only (not the installed desktop application). After pulling the checkpoint and ensuring `.venv-live` and frontend dependencies exist, run this from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Verify_Macro_A3_Local.ps1
```

The script executes:
- Frontend Node behavioural tests, TypeScript compilation, Vite build.
- Backend Python compilation and focused ML regression tests, including `tests/test_ml_a3_preparation_and_split_safety.py`, model-library validation and earlier non-AI correctness gates.
- Python runs from the repository's isolated `.venv-live`; datasets and SQLite use a unique temporary `PILOTODIN_HOME`.
- It does **not** dispatch GitHub Actions, train bundled AI, install packages, alter production data or build an installer.

If pytest is missing in the development venv, explicitly install from `backend/requirements-test.txt` within the existing `.venv-live`.

## Manual Windows acceptance (at the A3 checkpoint)

- [ ] Choose an output column and compare Prepare's candidate vs included predictor counts with excluded and unusable fields.
- [ ] Check Prepare's resource preflight before excluding columns, then exclude a high-cardinality field. The server rechecks the actual trainable features on submission; there must be no silent auto-downsampling, peak-RAM guarantee or production-data mutation.
- [ ] Confirm that training with more than 30,000 labelled rows or a projected dense matrix greater than 256 MB fails with an actionable guardrail message rather than trying to fit a large model.
- [ ] For expensive kernel SVM/SVR, confirm that more than **5,000 labelled rows** are rejected before training. KNN is capped at **12,000** labelled rows. When comparing multiple algorithms, the *strictest* selected model cap applies and Model Lab explains which option prevents training.
- [ ] Check that the conservative dense feature estimate uses **all labelled rows** as a protective upper bound, not an assumed 80% train fraction; grouped holdout sizes can be uneven. It must not be described as measured peak memory.
- [ ] For group-based CV, include a literal source value `(Missing group)` and genuine missing group IDs. They must be treated as two distinct groups, never accidentally merged; holdout and CV train/validation fold groups must be disjoint.
- [ ] Inspect feature audit for a numeric field with missing values, a categorical field, a constant field and a likely identifier.
- [ ] Manually exclude one predictor, apply suggested exclusions, and confirm the manual exclusion remains.
- [ ] Leave a high-risk predictor included: the review acknowledgement should be visible; without it the Train action must be disabled and a forged API request rejected.
- [ ] Acknowledge intentionally and train; verify the experiment configuration preserves the reviewed predictor list and approved dataset version.
- [ ] Try chronological data containing two rows with the exact same boundary timestamp. The holdout must refuse a split of those rows rather than leak.
- [ ] Run time/group stratified experiments on adequate real or synthetic datasets; inspect CV folds and baseline vs candidate scores.
- [ ] Select a model: land in Evaluate, inspect actual held-out metrics and reliability warnings, then proceed explicitly to Predict.
- [ ] Check the held-out score against the **training-derived constant baseline** on the same held-out rows. This must be a diagnostic after selection, never an input to choosing the winning model; for older experiments with no saved training baseline, display unavailable instead of inventing a comparison.
- [ ] After selecting a model, examine the post-selection sensitivity table. It must disclose at most eight tested predictors, at most 64 held-out rows and two shuffles per feature, with explicit incomplete-coverage/non-causal warnings. No untested predictor may appear ranked. Reopening an old experiment without sensitivity shows unavailable, not fabricated values.
- [ ] Check source test records and the saved selected-model metrics remain immutable and no diagnostic is allowed to retune or reselect the model.
- [ ] Reopen an already selected experiment from the project and confirm it navigates to **Evaluate** rather than bypassing the held-out report.
- [ ] Prediction input with a missing feature explicitly warns that training-fitted imputation is used; an unfamiliar category warns only if the training category list is complete.
- [ ] Class probabilities are clearly identified as **uncalibrated model estimates**, not externally validated likelihoods.
- [ ] Predict valid and invalid inputs (e.g. HourOfDay 9 vs 25); invalid values must not produce a successful inference.
- [ ] Switch projects or approve a new Quality version and check that stale experiment predictions are refused.

Keep A3 separate from subsequent reporting (A4), offline Ask ODIN (B1), universal progress (B2) and final 8 GB packaged desktop acceptance (C1).


## P0 real Prepare-to-Predict versioned API lifecycle: new isolated owner acceptance gate (27 October 2026)

The complexity-last P0 roadmap explicitly requires a full **Prepare→Model Lab→Evaluate→Predict** journey on disposable data. Existing `tests/test_p0_ml_persistence_version_journey.py` already trained a real deterministic Logistic Regression via FastAPI, selected and evaluated it, predicted valid/invalid rows, and applied an explicit Quality approval to make the model stale. This new source increment **extends that same test, not a duplicate**, with the actual Prepare feature audit and a second version-pinned real training/held-out model selection/prediction after approved Quality version 1. It confirms that the old version-0 model remains stale, its selected metrics unchanged, both original uploaded CSV bytes remain untouched and the second project has no experiment history. A pre-selection prediction is refused until held-out Evaluate is completed. This is stronger *server-side functional integration evidence* than mocking the API, but not browser/workspace or packaged-offline acceptance.

**Safety of actually running it:** Previously the test imported `backend.main` before changing its data home inside the test, which could initialise the default checkout data directory during accidental pytest collection. The test now performs a module-level `pytest.skip` BEFORE importing backend unless a runner establishes a marked disposable OS-temporary `PILOTODIN_HOME`. New `tools/p0_real_ml_versioned_api_devqa.py` spawns the genuine one-test journey in a child process with that isolated home already set and temporary pytest base; deletes temp data, does not echo private paths/logs, disallows desktop session, installs nothing and has a bounded 240-second timeout. New `Run_PilotODIN_P0_Real_ML_Journey_DevQA.bat` runs it once from the repo root using the existing `.venv-live` interpreter. No real files, cloud providers, Qwen, installer, or fonts are involved. The generated CSV only contains small synthetic columns.

**Current evidence level: SOURCE COMMITTED, OWNER WINDOWS NOT YET EXECUTED.** Do not confuse the earlier P2 real PDF 28/28 or ML domain validation checkpoints with this complete version-transition API journey. The intended scoped output is `SCOPED_P0_REAL_ML_VERSIONED_API_JOURNEY_PASS`; a future PASS will certify only this tiny generated-data in-process API sequence. Explicitly open: real UI Prepare→Model Lab→Evaluate→Predict navigation, varied split/target datasets, real 8 GB peak RAM, full concurrency/crash recovery and final P8 offline installer. If blocked, fix only a new P0 issue without repeating old accepted tests.
