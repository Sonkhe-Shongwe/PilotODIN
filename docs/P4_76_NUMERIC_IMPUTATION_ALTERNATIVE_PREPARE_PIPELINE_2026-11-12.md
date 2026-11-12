# PilotODIN P4-76 | Numeric median/mean preprocessing choice, enforced by fold pipelines

**Date:** 12 November 2026. **Scope:** first narrow, real configurable preprocessing alternative for BE-024. **No training, full native execution, installer, original app/data access, risk waiver, P5, or P8 approval.** All tests use in-memory synthetic fixtures or CI-only disposable read-only HTTP state.

## Confirmed gap and design

Prepare's per-feature explanation previously described only median imputation, and there was no user-selectable preprocessing method reaching the Python training pipeline. The engine builds fold-local `SimpleImputer(strategy="median")` for numeric fields and keeps categorical `most_frequent` + capped OHE. The selected strategy needs to be threaded from the UI through a validated API request into persisted experiment provenance and each actual fold-fitted pipeline, including the baseline. A display-only option is insufficient.

**Bounded support:** a project/target/Quality-version-reset **numeric** choice between **median (unchanged default)** and **mean** for *all currently included numeric predictors*. No categorical alternative, per-field individual override, automated target selection, model training, inference, user-original-data access or extra ML library. The UI notes the outlier sensitivity of mean and the fit-within-training-fold rule.

## Implementation contracts

- `frontend/src/App.tsx`: explicit Prepare selector, dirty-draft notification, reset to median when target/project/Quality version changes, matching numeric audit and transformation descriptions, and `numeric_imputation` forwarded with the experiment request and local experiment configuration.
- `backend/main.py`: Pydantic `Literal['median','mean']` rejects any unsupported value with validation error before project/fit admission; old clients default to median. The value is persisted in experiment config and forwarded by `train_background` with `config.get(...,'median')` for legacy configurations.
- `backend/engine.py`: `validate_numeric_imputation` allowlist and `make_pipeline(..., numeric_imputation='median')`. Both baseline and all candidate-model `make_pipeline` paths in `run_training` use the same strategy. Each imputer is inside the existing fold-fitted ColumnTransformer, never applied to complete original data or before CV. Training results carry `numeric_imputation` for audit. Categorical mode/OHE, quality-version gates, high-risk acknowledgement, split leakage safeguards, resource limits and historical experiments remain unchanged.
- `frontend/src/api.ts`: backwards-compatible optional strategy in model experiment and results type.
- `tests/test_p4_consolidated_acceptance.py`: tests inspect **unfitted** genuine sklearn pipeline step configuration, both allowed values and invalid-value rejection, and stub the background worker to assert persisted setting reaches the engine. The deliberate sentinel prevents any model fit or project storage writes.
- `frontend/tests/ml-a3-feature-preparation.test.cjs`: source contract for UI, request, backend persistence and baseline/candidate reuse. Existing disposable P4-62 real-HTTP browser case toggles median → mean → median, verifies live per-field audit/plan text, manual/additive exclusions, version pinning and **no experiments**.

**Evidence threshold:** source and CI results must be observed separately; a green build does **not** demonstrate a full fitted model or its predictive impact. This is a genuinely configured *global numeric* alternative, not completion of all per-column preprocessing controls under BE-024. Do **not** run even a synthetic fit just to generate evidence without renewed owner approval.

## Acceptance and governance

P4 ACTIVE, R01–R06 OPEN. R01 independent real-world business Gate C UNVERIFIED; R02/R04/R05 newest-source native interactions NOT TESTED; R03 physical offline 8 GB/Qwen NOT TESTED; R06 historical entire original app-local-data STRICT FAIL (320 baseline files vs 346 observed, 74 differences, historical writer UNKNOWN). Earlier one-use native/model-fit approvals consumed; P5 NOT AUTHORISED; P8 NOT CERTIFIED. No installer or owner application data access.
