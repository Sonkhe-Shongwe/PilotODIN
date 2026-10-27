# PilotODIN P0 | One complete interactive ML journey on synthetic data

**Status (27 October 2026):** Source fixture and walkthrough committed. **Owner Windows interactive UI acceptance NOT YET TESTED.**

**Authoritative branch:** `feature/live-dev-workspace-20261023`.

## Scope and safety

This is **not** the already accepted `SCOPED_P0_REAL_ML_VERSIONED_API_JOURNEY_PASS` backend QA (two real scikit-learn training runs on Windows); that accepted API milestone is **closed, do not rerun**. This check is a browser/UI acceptance of the existing real workflow. The fixture contains exactly **80 entirely generated rows**, four synthetic predictors and one synthetic binary label. Its contents match the `_dataset()` structure of `tests/test_p0_ml_persistence_version_journey.py`, and are not derived from any personal or insurance project.

Fixture: `fixtures/P0_SYNTHETIC_UI_ML_80.csv`.

- `incident_hour_of_the_day`: 0–23 (generated, whole number). Test valid 12 and invalid 25.
- `number_of_vehicles_involved`: 1–4 (generated integer). Test invalid -1 if convenient.
- `premium`: generated numeric value. Example for UI input: 465.
- `Region`: generated Gauteng/Mpumalanga categories, with deliberate leading/trailing whitespace in a few source rows, solely for a separate Quality issue if reviewed later.
- `fraud_reported`: synthetic Y/N label, not real fraud outcomes or a performance reference.

Do not assume a particular accuracy, feature importance, prediction class, or fairness result. Any numbers displayed are experimental, not externally validated.

`Start_PilotODIN_Live_Dev.bat` uses the **ignored isolated** `.pilotodin-dev-data/` home (local loopback only); this home **persists** the imported synthetic project until deliberately cleaned. It is *not* an ephemeral temp directory. Do not switch to installed production, import user files, upload private logs, enable local LLMs, overwrite existing project data, or test font/installer assets.

## Exactly one owner UI journey

1. Safely pull the branch without discarding local changes. Reuse an existing local isolated Live Development session or launch `Start_PilotODIN_Live_Dev.bat` from repo root (prefer standard, non-admin Windows). Open `http://127.0.0.1:5173`. Select **New project** / **New dataset**; import **only** the committed `fixtures/P0_SYNTHETIC_UI_ML_80.csv`. Confirm ~80 rows and 5 columns in the synthetic project. Do not use the earlier uploaded local insurance dataset for this acceptance.
2. Navigate to **Prepare** (called Preparation in the sidebar). Choose target `fraud_reported`. Confirm **Classification**, four candidate predictors, feature-by-feature audit, missing labels and resource preflight appear. Review the displayed field risk/exclusions. Avoid blindly clicking target-opportunity suggestions, which are explicitly unverified.
3. Press **Open Model Lab**. Select **Logistic Regression** as the *only* algorithm for this small test (remove other default models, if any). Keep **Random: independent observations** for this explicitly generated synthetic sequence and acknowledge the split warning if you judge it appropriate for this controlled fixture. If any predictor remains marked high-risk, manually exclude it or knowingly acknowledge the risk after reviewing it. Use the default or no time limit and click **Train models** once. Do not train on an actual or external dataset.
4. Watch the real experiment's queued/running/completed state in **Evaluate**. Confirm the **cross-validation leaderboard** and held-out selection gate. Choose **Select model** for Logistic Regression if it is ready. Inspect the saved **Held-out test report**, baseline comparison, confusion matrix, class reports and any explicit reliability warnings. Do not assume the model beat the baseline, and do not treat a test score as deployment validity.
5. Click **Open Predict Studio**. Use valid inputs: `incident_hour_of_the_day=12`, `number_of_vehicles_involved=1`, `premium=465`, `Region=Gauteng`. Click **Generate prediction**. Verify the output shows Y or N, an explicit experimental warning, and any uncalibrated-probability disclosure. **Do not interpret the result as a verified fraud determination.**
6. Attempt a separate invalid input `incident_hour_of_the_day=25` (if the browser input control permits it; otherwise a client-side input rejection is acceptable). Confirm the UI does not display a new successful prediction for an invalid hour and shows a guard/error if submitted. Return the field to 12.
7. Reopen this **same saved experiment** using the project's experiment history / recent work. Confirm it returns to **Evaluate**, preserves selected Logistic Regression and held-out metrics, and does not silently regenerate them or jump straight into a new prediction. If convenient, switch to a different project and back to confirm experiment/prediction state isolation. Do not approve a Quality change solely to repeat the stale-version API check already accepted.

## Scope and evidence handling

A concise outcome is sufficient: (a) imported synthetic fixture and Prepare audit, (b) training and held-out Evaluate, (c) valid and invalid Predict, (d) saved experiment reopening. Only send **safe, cropped screenshots** from the synthetic test project if a defect needs diagnosis. Stop at the first unexpected behavior and report the visible screen/error; **do not re-import actual datasets, rebuild sidecars, reset SQLite, or rerun the previous P0 API test**.

**Acceptance boundary:** A successful owner-run browser session can close **only the scoped P0 single-dataset local UI journey**. It does not certify all models/splits, general dataset performance, peak 8 GB RAM, concurrent/crash recovery, native offline installer, P8, or P2 font/Unicode distribution. P2 remains `REVIEW_REQUIRED`, end-user mixed Unicode PDF `NOT_ACCEPTED`, font release `NOT_GRANTED`, P8 `NOT_CERTIFIED`.
