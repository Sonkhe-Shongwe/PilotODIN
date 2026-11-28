# PilotODIN 1.0 | P4-53 Nominal categorical CSV for genuine public UCI Bike Sharing research

**Date:** 12 November 2026. **Type:** input-data preparation and source/test verification only. **No training, native build, original-data access or business approval.** Source/test [`5f1144ad26bfe425f6e946d54cef0c7a4c21e11a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5f1144ad26bfe425f6e946d54cef0c7a4c21e11a). Exact CI [#43192250027](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43192250027), **COMPLETED SUCCESS 3/3**.

## What was discovered and why it affects a future experiment

The official [UCI Bike Sharing dataset description](https://archive.ics.uci.edu/dataset/275/bike-sharing-dataset) identifies `season`, `yr`, `mnth`, `holiday`, `weekday`, `workingday` as categorical or binary attributes. In the previously accepted 731-row input these were **numeric CSV values**, and current generic `backend/engine.py::inferred_kind` classifies every numeric series as numeric. As a result, Prepare reports median numeric treatment and `make_pipeline` routes codes through the continuous numeric branch, even though the UCI data uses category labels. For linear regressors, that encodes a non-substantiated numerical interval and ordinary ordering across codes such as weekdays and seasons. Trees may behave differently; the finding is a *data type contract issue*, not proof of wrong trained predictions or a claim that numeric codes can never work.

**Decision:** Avoid modifying generic production preprocessing in P4 merely for one public research fixture. Instead provide an **optional reversible typed CSV**, and prove its effect on existing source/Prepare. Preserve original raw-code fixture as well so a future separately authorised research experiment can disclose which representation is used.

## Exact derivative

| Item | Value |
| --- | --- |
| Original/source | `tests/fixtures/public_bike_daily_preday_731.csv`, 731 rows, 8 fields, SHA-256 `51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636` |
| Additional typed fixture | `tests/fixtures/public_bike_daily_categorical_preday_731.csv`, 731 rows, 8 fields, **51,950 bytes**, SHA-256 `8981926c70d117fd487ce5ac5d0381be30dd159488576646c67978a2d3139a2e` |
| Verbatim preserved | Every `date` and `daily_rentals_target` value; all 731 row orders, six categorical numeric codes in bijective textual representation |
| Converted values | `season_1` to `season_4`; `yr_0/yr_1`; `mnth_01` through `mnth_12`; `holiday_0/1`; `weekday_0` through `weekday_6`; `workingday_0/1` |
| Unmodified scope | Original user-uploaded ZIP, earlier prepared CSV, historical source outcome/counts, source method, installed app data, production engine, GitHub issues and original baseline |
| Provenance/licence | Capital Bikeshare 2011–2012, UCI Fanaee-T and Gama, CC BY 4.0; source/reversibility documented in [fixture README](../tests/fixtures/README_public_bike_daily_preday_731.md) |

The text prefix is **mechanical**, not an inference that a given category means an actual holiday, season name or published operational state. The earlier removed `casual`, `registered` and retrospective same-day weather variables remain removed.

## What was actually verified in the hosted disposable backend

New [no-fit tests](../tests/test_p4_bike_categorical_readiness.py) confirm:

1. SHA-256 and shape for both CSVs; original target+date exact equality; all source values recover by removing text prefixes, each column's distinct count preserved, no missing or duplicate complete rows.
2. Current `engine.inferred_kind` returns **numeric** for six original fields but **categorical** for six typed fields; typed `engine.preparation` reports categorical mode-imputation/one-hot handling, unlike raw numeric treatment.
3. `engine.validate_config(typed, target, ["date"], ["linear_regression"], "regression")` succeeds with exactly six categorical candidate predictors and `date` used only as the future time split key. This is **configuration inspection without estimator fitting**.
4. `POST /api/projects` actually imports the typed file into a NEW `pytest` temporary SQLite home and temporary dataset folder. Version-bound target review marks rental count structurally reviewable, task regression, business relevance unverified, no automatic training. `GET /preparation` returns 7 available fields including `date` and six categorical audits. Empty experiments and empty model folder verified. No raw owner application path is touched.
5. Full source/test commit [`5f1144a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5f1144ad26bfe425f6e946d54cef0c7a4c21e11a) is gated in existing **source-only** P4 CI.

**[GitHub Actions #43192250027](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43192250027)** at exact test SHA **SUCCESS 3/3**: 169 Python pytest, 45 Node, TS/Vite, 9 other synthetic real-HTTP Chromium and Windows fake original-data/WebView safety in both PowerShell 7 and Windows PowerShell 5.1. None of the nine separate browser tests import or visually review this new typed dataset; only the two new Python integration/validation cases did. No native Windows EXE or installer built.

## Operational decision and Gate C are still open

Proposed decision horizon is pre-day rental demand. The category encoding correction does not establish historical advance availability of holidays or when total daily bike rental counts became final. [Capital Bikeshare's current system-data documentation](https://capitalbikeshare.com/system-data) says trip-history files are **published monthly**; that is a current publication statement, not independently verified evidence of actual reporting lag in 2011/12 nor proof that operational internal systems lacked faster access.

This dataset contains one citywide total, **not station inventory or dispatch records**, so it cannot by itself measure actionable station-level bike allocation and capacity benefits. No independent actual decision owner, prediction moment specification, measured interventions, true baseline action and cost, fairness/legal review, or future generalisation acceptance exists. Explicit model fitting permission and an independently verified business Gate C decision remain distinct unresolved dependencies.

**Strict preservation and phase state:** the earlier original app data full-tree comparison remains **FAIL** (trusted baseline 320 files, observed 346; 74 browser/cache *candidate* changes, historical writer unknown), although original EXE and protected project `data/` were unchanged in the documented comparison. No waiver, cleanup, restore, new baseline or file-write attribution. **P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**

**Next justified move:** Only if the owner explicitly chooses a bounded, disposable, time-split research experiment may it fit models to this categorically typed source. Predefine a same-horizon honest baseline and as-of-data assumptions before approving that fit. If the objective is **true operational Gate C closure**, seek a participating decision owner and validated intervention/outcome evidence rather than synthetic ML scores.
