# PilotODIN 1.0 | P4-52 Public bike daily as-of calendar and chronological baseline readiness

**Date:** 12 November 2026. **Test-source commit:** [`5c582fc30555a2817e9ef513eca5fc96b4d46174`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5c582fc30555a2817e9ef513eca5fc96b4d46174). **Exact test-source GitHub Actions:** [#43190242820](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43190242820) **COMPLETED SUCCESS, 3 of 3 jobs**. This is a **NO-FIT** chronological design and historical reference evaluation, not a new fitted model, a native Windows test, an authorised business intervention or Gate C approval.

## 1. Input, source and prediction moment

The user-supplied, publicly licensed UCI Bike Sharing historical 2011–2012 research derivative is `tests/fixtures/public_bike_daily_preday_731.csv`. See [public source/attribution](../tests/fixtures/README_public_bike_daily_preday_731.md) and [P4-51 exact API import](./P4_51_PUBLIC_BIKE_DISPOSABLE_IMPORT_AND_PREPARE_2026-11-12.md). **731 dates, 8 fields, no missing values**, SHA-256 `51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636`. Target is actual historical `daily_rentals_target` total (regression). **Proposed** horizon: one day, decision before the target day begins. No city/bikeshare owner has independently confirmed the operational cutoff or historical publication latency.

| Field | Proposed role | As-of evidence and caution |
| --- | --- | --- |
| `daily_rentals_target` | **Outcome only**, never predictor | True total exists after the rental day; outcome definition is grounded in UCI daily counts, but original validation/audit timestamp and operational report latency are not provided |
| `date` | **Time ordering/split key**, never model predictor | Calendar date known in advance; select **Time** validation in Model Lab with `date` split column |
| `season` | Calendar-coded candidate predictor | The UCI category is coded per date; only legitimate if exact season policy is determined pre-day, not inferred from future data |
| `yr` | Calendar-coded candidate predictor | Original 0/1 codes cover 2011/2012 only, **not** an automatically generalisable future-year convention |
| `mnth` | Calendar-coded candidate predictor | Month known pre-day |
| `holiday` | **Conditional** pre-day predictor | UCI README says derived from DC holiday schedule; must verify advance availability and revised/unscheduled holiday handling before operational use |
| `weekday` | Calendar-derived candidate predictor | Day-of-week known pre-day |
| `workingday` | **Conditional**, redundant calendar flag | Derived from weekday and holiday; correct in source but inherits holiday availability assumptions |

Fields `casual` and `registered` (which sum to total demand) and actual same-day `temp`/`atemp`/`hum`/`windspeed`/`weathersit` were already removed in P4-51. No new data cleaning, synthetic outcomes, forecast weather or unverified operational features were added.

**Actual observed consistency on all 731 rows:** date is unique, chronological and daily without gaps; `yr` equals date.year minus 2011; `mnth` and `weekday` match the calendar; `workingday` equals non-weekend and not-holiday. This is **internal consistency**, not independent proof the historical UCI holiday flags were published before each prediction cutoff.

## 2. Fixed prospective evaluation geometry (no estimators fitted)

These are the actual current `backend/engine.py::run_training` time-split shape and `TimeSeriesSplit(n_splits=3)` boundaries, **reproduced independently without calling that model-fitting function**:

| Partition | Rows | From | Through |
| --- | ---: | --- | --- |
| Development (first 80%, `int(731*.8)`) | **584** | 2011-01-01 | 2012-08-06 |
| Unseen chronological holdout (last 20%) | **147** | 2012-08-07 | 2012-12-31 |
| Time CV fold 1: development-training | 146 | 2011-01-01 | 2011-05-26 |
| Time CV fold 1: validation | 146 | 2011-05-27 | 2011-10-19 |
| Time CV fold 2: development-training | 292 | 2011-01-01 | 2011-10-19 |
| Time CV fold 2: validation | 146 | 2011-10-20 | 2012-03-13 |
| Time CV fold 3: development-training | 438 | 2011-01-01 | 2012-03-13 |
| Time CV fold 3: validation | 146 | 2012-03-14 | 2012-08-06 |

- Each validation starts after the corresponding training period. The final 147-day holdout is chronologically after all three development folds.
- Pure `engine.validate_config(df,target,["date"],["linear_regression"],"regression")` was evaluated **without estimator fit**. The effective model candidate columns are exactly `season`, `yr`, `mnth`, `holiday`, `weekday`, `workingday`; `date` and target are excluded. The original DataFrame remains unchanged.
- The actual runtime `run_training` path has not been invoked with this data, as it would begin baseline/model fitting. Thus no claim of executing the complete training time-split pipeline or forecast scoring is made.
- **Holdout embargo** is not implemented here: fixed development is safe for full-day outcomes only if earlier labels and eligible features were actually available at their documented decision times. Investigate real reporting delays and any need for a safety gap before future fitting.
- This one two-year history cannot establish post-2012 generalisation, booking/business utility, stable weather or holiday data availability, repeated-entity structure or fair deployment.

## 3. Reference MAE on the 147 historical holdout days (not a trained ML model)

MAE means mean absolute error, in bicycle rentals/day. Lower is better. Read-only arithmetic using the original target observations:

| Reference | Holdout MAE | What is known at prediction time? |
| --- | ---: | --- |
| Fixed development-period **median** (4,200 daily rentals) | **2,259.16** | Only development-period actual labels, subject to retrospective label availability and report cutoff |
| Fixed development-period **mean** (4,153.60) | **2,290.41** | Same fixed-origin caveat; no holdout labels consulted to construct forecasts |
| Previous day's observed count | **878.39** | **Conditional rolling one-day-ahead**: requires yesterday's count to be finalised before today's decision |
| Mean of previous 7 observed days | **918.63** | **Conditional rolling one-day-ahead**: requires all seven recent counts to have been finalised in time |
| Same weekday previous week | **1,194.73** | **Conditional rolling one-day-ahead**: requires the observed label from seven days ago |

The three rolling rules were calculated independently for each of the 147 target dates, using only **earlier-dated** target rows. Thus they do not use contemporaneous or future labels for a given date, but may use already-observed dates **within the holdout interval** for later forecasts. **They are NOT direct fixed-origin 147-day-ahead forecasts; reporting latency remains UNVERIFIED**. Do not compare them to a model predicting the whole holdout from 6 August 2012 or claim gain without identical information/horizon conditions. This historical comparison is a research aid, **not measured incremental benefit of an authorised Capital Bikeshare decision**. No ML model was trained or selected.

## 4. Exact-source checks and result

[`tests/test_p4_bike_time_readiness.py`](../tests/test_p4_bike_time_readiness.py), source [`5c582fc`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5c582fc30555a2817e9ef513eca5fc96b4d46174), adds three checks of (1) exact original-public-derivative SHA, six-calendar-field availability schema/consistency, **no-fit** engine configuration excluding `date`, (2) precise 584/147 holdout and three expanding CV fold date windows, and (3) honest non-model reference baselines. GitHub workflow included the new test only in existing synthetic/source CI, never a native build.

**[GitHub Actions #43190242820](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43190242820) EXACT SOURCE SUCCESS 3/3**:
- **167 Python pytest PASS** including the three new public real-data, no-fit checks and prior public CSV import test.
- **45 Node PASS (0 fail)**; TypeScript/Vite **PASS**.
- **9 real-HTTP disposable Chromium PASS** on existing separately synthetic fixtures, **not** bike-data browser testing.
- Windows-2022 fake-file preservation and WebView profile negative tests **PASS** under PowerShell 7.6.9 and 5.1.20348.5773, **not** real owner original app/data.

**No new app implementation, experiment API call, estimator fit, installed native Windows source, model artifact, installer, Qwen inference, original app-data access, restoration, cleanup, baseline revision or owner approval.**

## 5. Acceptance and next justified step

The data passes **a narrowly bounded historical pre-day calendar/read-only chronology feasibility check**, not the independent business **Gate C**. A legitimate decision owner, outcome reporting latency, feature availability snapshots, group/time-dependent intervention baseline, real incremental cost/benefit and lawful/fair basis are still needed. A newly authorised *disposable model-training experiment* would be a **separate decision** requiring correct chronological configuration and strict preservation; passing this test does not grant that permission. A more urgent unresolved release concern remains original app-data strict P4-R06 **FAIL**, 320 trusted-backup versus 346 observed files, 74 WebView/cache *candidates*, historical writer unknown. Do not waive.

**P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** No P4–P7 intermediate installer or new native compilation authorised.
