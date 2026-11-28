# PilotODIN 1.0 | P4-55 One controlled, disposable public bike research experiment

**Date:** 12 November 2026. **Approval interpretation:** User replied **"okay next"** directly to a proposal for **one controlled, disposable, time-split research fit using the public categorical Bike Sharing CSV only**. This permission was applied strictly to that narrow purpose, not to production model training, any owner original files, Windows native builds/installers, real business Gate C or deployment.

**Authorised training source:** [`cd7ce3d000c3c69f67cadacde6f8445e7bee68cf`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cd7ce3d000c3c69f67cadacde6f8445e7bee68cf). **One successful GitHub Actions research fit:** [#43195711568](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43195711568), **COMPLETED SUCCESS**, one research job. Job logs contain full authoritative aggregate JSON line `P4_55_RESEARCH_SUMMARY_JSON=...`, and no raw rows, model files or downstream artifacts were uploaded.

## 1. What actually ran

- **Exact approved public fixture:** `tests/fixtures/public_bike_daily_categorical_preday_731.csv`, SHA-256 `8981926c70d117fd487ce5ac5d0381be30dd159488576646c67978a2d3139a2e`, **731 rows / 8 fields** with 2011-01-01 through 2012-12-31 historical dates and the original actual total `daily_rentals_target`. UCI Bike Sharing, historical Capital Bikeshare data, Fanaee-T/Gama, CC BY 4.0, [dataset provenance](../tests/fixtures/README_public_bike_daily_preday_731.md).
- **Prediction objective (research):** hypothetical **pre-day citywide total rental demand** with only six string-typed categorical calendar predictors `season, yr, mnth, holiday, weekday, workingday`. Original same-day weather and arithmetic target components `casual/registered` were excluded. `date` is a **Time** split key, **not a fitted predictor**.
- **Current exact PilotODIN engine:** a single call to `backend.engine.run_training(df, target="daily_rentals_target", excluded=[], models=["ridge", "random_forest"], task="regression", split_strategy="time", split_column="date")` from [`qa/p4_research/p4_55_one_disposable_bike_fit.py`](../qa/p4_research/p4_55_one_disposable_bike_fit.py). No custom model engine or product code modification.
- **Isolation:** GitHub-hosted disposable Ubuntu 24.04 runner, 3.11 Python, existing backend test requirements; `PILOTODIN_HOME` and Joblib temp under **unique `RUNNER_TEMP` subdirectories**. Limited to 1 job and 10-minute cap, BLAS threads forced to 1, **no action credentials persisted** and **contents:read** only. No resident owner-app process or local original project accessible. Neither application API project, persisted SQLite experiment, model serialization, run artifacts, native Windows EXE, installer, Qwen nor deployment were used.
- **Frozen chronological design:** 584 development days (2011-01-01 through 2012-08-06), 147 held-out 2012-08-07 through 2012-12-31, three expanding chronological model-selection CV folds. `ridge` and `random_forest` were declared **before** fitting. Each preprocessing pipeline fitted its categorical one-hot steps within development folds. CV selection by **smallest validation MAE only**. The final historical holdout was scored for the **single selected model** only.

## 2. What the actual training logs show

**All MAEs are mean absolute error in rentals per day; lower is better.**

| Candidate | Development expanding CV MAE | Final 147-day historical holdout MAE | Comment |
| --- | ---: | ---: | --- |
| Median baseline (fold-fitted DummyRegressor; fixed 584-day median for holdout) | **1,987.73744** | **2,259.16327** | Non-model benchmark appropriate to *same fixed-origin calendar-feature study* |
| **Ridge regression** | **1,417.93486** | **1,068.60687** | **Selected from CV**, then scored exactly once on historical holdout |
| Random forest (70 trees, bounded depth 14) | **1,992.45615** | **NOT SCORED** | Not chosen from development CV |
| Historical month × working-day development mean | Not the engine's CV baseline | **2,353.14180** | Prior P4-54 *descriptive reference*, independently computed before this model fit |

The **selected Ridge** retrospective historical holdout MAE is **1,190.56 rentals/day lower than the fixed development median**, or about **52.70% lower MAE**. It also outperforms the pre-examined month/workday reference numerically, but no business impact follows from this observation.

The engine's existing `beats_baseline` field means at least one candidate was better than the development CV median. It is **not** a real-business value claim. Ridge and the baseline saw the same chronological split; the random forest holdout was deliberately NOT consulted. No opportunistic model tuning or unreported additional fits were made.

**Crucial statistics limitation:** P4-54 *already examined the aggregate outcome distribution and several baselines on this final 147-day period*. Thus although the Ridge model was chosen only by development CV, the project's overall work had previously inspected the holdout: **this is exploratory retrospective research, NOT a genuinely blind untouched independent test**. It cannot be used for an unbiased future performance certification. The current feature encoding includes `yr_0/yr_1` for only 2011/2012, so any claim for 2013+ remains unsupported. Citywide system counts do not allow station-level bike availability decisions.

**As-of-time limitation:** source UCI `holiday` and `workingday` are coded attributes, but historical advance knowledge of published holiday schedules and original rental-total reporting delay were NOT independently documented. The Capital Bikeshare current public trip-data publication is monthly and cannot establish 2011/2012 internal reporting latency. Model fit is a retrospective exercise without an operational decision owner, action, measured cost/benefit or governance approval.

## 3. Failure disclosed, successful attempt, permission consumed

- First GitHub Actions [#43195506498](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43195506498) at [`9deda17`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9deda1796cdf41246dc57c10c27e7eb911614fad) **FAILED before any model fitting**. Its research script pointed one parent directory too shallow and raised `FileNotFoundError` reading `/qa/tests/fixtures/...csv`. No estimator was run, no model artifact generated, no owner data affected. Failure is not misreported as PASS.
- Exactly one path-only fix [`cd7ce3d`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cd7ce3d000c3c69f67cadacde6f8445e7bee68cf) changed `parents[1]` to `parents[2]`. Successful complete run [#43195711568](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43195711568) verified **COMPLETED SUCCESS**. Its log contains one `P4_55_RESEARCH_SUMMARY_JSON` record with exactly the results above.
- **One-off automation retired:** ephemeral `.github/workflows/p4-55-one-approved-public-bike-fit.yml` push trigger is **removed in this documentation commit**, while the executed script and immutable workflow source commit remain in Git history. This prevents further automatic model fitting on routine future changes and does not imply blanket approval for another experiment.
- The general source CI was **not rerun** for these research-only scripts, and the successful fit job is **not** a Windows, frontend, browser or full P4 acceptance suite. The preceding product/source test at [P4-53 #43192250027](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43192250027) remains the latest 169 Python/45 Node/9 browser/Windows synthetic success for its own exact SHA. Do not conflate source SHAs.

## 4. Gate, original-data and future decision

**Research result:** the selected model **improved a retrospective calendar-only historical MAE** under a fixed development/holdout design, using genuine public historical outcomes. This is useful product-research proof that PilotODIN's existing engine can execute an actual carefully configured chronological regression fit in a disposable environment. It is NOT independent operational value, profit, deployment eligibility, future year forecasting proof, a live owner-reviewed use case or the real Gate C acceptance.

- **P4-R01 real-world Gate C** remains **UNVERIFIED**; independent decision owner/label-as-of proof/intervention and costs/fairness/approval still required.
- **P4-R02–R05 owner-native and 8 GB/offline acceptance** remain **OPEN**. The one-time prior native build permission from P4-47 was consumed independently; this work did not touch it.
- **P4-R06 original whole app-data preservation** remains **STRICT FAIL** (320 backed-up files / 346 current, 74 browser/cache *candidates*, historical writing process UNKNOWN). Independent original EXE SHA and protected `data/` subtree matched in previous owner read-only evidence; that does NOT reverse the whole-tree strict FAIL. No deletion, rebaseline, waiver, new owner scan or cross-app writes assertion.
- **P4 ACTIVE. P4-R01–R06 OPEN. P5 NOT AUTHORISED. P8 NOT CERTIFIED.**

**Next justified step** is *independent real operational owner/use-case provenance* or previously scoped owner Windows acceptance, not repeated experimentation on the already-inspected holdout or an additional model run merely to increase scores.
