# PilotODIN Macro A3 — Machine Learning reliability checkpoint

**Branch:** `feature/live-dev-workspace-20261023`  
**Checkpoint:** A3-1 through A3-4: audited features, leak-aware splits, held-out evaluation, bounded post-selection sensitivity, conservative 8 GB-local resource controls and group-identity integrity  
**Acceptance state (owner Windows checkpoint, 24 October 2026):** Focused local checks **passed: 99 frontend tests, 27 backend tests**, TypeScript/Vite build and Python syntax compilation (~23.2 seconds). **Interactive Prepare → Model Lab → Evaluate → Predict, realistic 8 GB stress and installed/offline desktop acceptance remain pending.** This is not an exhaustive backend suite. See [living handoff](./CONTINUE_HERE.md).

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
