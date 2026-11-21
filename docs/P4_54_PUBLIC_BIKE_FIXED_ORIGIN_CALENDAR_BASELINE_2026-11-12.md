# PilotODIN 1.0 | P4-54 Public bike day-ahead calendar baseline diagnostic

**Date:** 12 November 2026. **Scope:** real public-data, reference-rule arithmetic only, **NO ML estimator fitting, experiment request, native build, owner machine access, original-data read/write, source-code changes or Gate C approval**. Result reproduced independently in pure JavaScript using the GitHub fixture and in a separate Python/pandas read-only calculation against the original previously uploaded derived CSV.

## 1. Source and prior verified guardrails

Exact source: [`tests/fixtures/public_bike_daily_preday_731.csv`](../tests/fixtures/public_bike_daily_preday_731.csv), Git blob `49369dc29a5a076d3c6267190a4cea8dccf6ce3a`, source SHA-256 `51e105f75acf827e5c089a8f30925fe8ab90c59df46201a9d724ad5f67588636`, 731 daily records, 1 January 2011 to 31 December 2012. Companion [P4-53 categorical fixture](../tests/fixtures/public_bike_daily_categorical_preday_731.csv) represents the **same date/target values**, not another independent dataset.

Use P4-52's fixed chronological geometry, unchanged:
- Development: first **584 rows**, `2011-01-01` to `2012-08-06`.
- Frozen final holdout: last **147 rows**, `2012-08-07` to `2012-12-31`.
- Outcome: `daily_rentals_target` (actual historical daily bike rentals).
- Proposed decision moment: before each rental day; `mnth` and `workingday` are source-coded calendar features, whose *actual* historic holiday schedule publication and business use remain **UNVERIFIED**.
- Ignore `casual` and `registered` (sum to target) and same-day observed weather; do not make `date` a fitted predictor. No holdout outcomes may enter development-group reference tables.

## 2. Independent no-ML reference-rule comparison

**Primary calendar reference defined for this audit:** for each holdout date, predict the arithmetic mean of **development-period** rental totals with matching `mnth` + `workingday`. If no corresponding development group exists, back off to the matching development `mnth` mean, then to the global development mean. For the final holdout there were **24/24 month × working-day groups in development**, a minimum of **9 development rows per group**, and **0 holdout group fallbacks**. The group table was not updated with any holdout actual outcome.

This is a **simple descriptive reference rule**, not an estimator trained by PilotODIN's experiment engine. It is a look-up of development outcomes used to evaluate a historical holdout. It is **not** a causal model, a validated deployment baseline, or business value.

```text
development = rows 0:584
holdout     = rows 584:731
month_workday_mean = mean(development.target grouped by (mnth,workingday))
for holdout_day in holdout:
    forecast = month_workday_mean[(holdout_day.mnth, holdout_day.workingday)]
MAE = sum(abs(holdout.target - forecast))/147
```

| Fixed 584-day-development reference (147-day holdout) | Historical holdout MAE, rentals/day |
| --- | ---: |
| Constant median from development (4,200) | **2,259.16** |
| Constant mean from development (~4,153.60) | **2,290.41** |
| Weekday-only development mean | **2,287.17** |
| Month + working-day development group mean (primary calendar rule) | **2,353.14** |
| Month + weekday development group mean (diagnostic) | **2,375.19** |
| Month-only development mean | **2,387.14** |

**Finding:** Month × working-day group reference is **93.98 rentals/day higher MAE**, approximately **4.16% worse**, than the simple development median. The calendar rule **does not establish improvement**, despite using correctly dated, relevant-looking features. The weekday-only group baseline is also slightly worse than the median. The other groupings are exploratory diagnostics and **must not be mined to select a 'winning' holdout model**, since this would bias subsequent final evaluation.

**Not a like-for-like comparison to earlier rolling baselines:** P4-52 also reported previous-day count MAE **878.39**, last-seven-day average **918.63** and previous-weekday **1,194.73**. Those use earlier outcomes **within the holdout** for later dates and require actual label publication before the next day's decision; the official public dataset does not verify such as-of-day operational access. They are conditional rolling one-day-ahead references, **not fixed-origin rules**. Do not use these as direct proof of real operational gain or compare mismatched horizon protocols.

## 3. Temporal drift and under-supported early folds

| Drift observation | Actual historical mean daily rentals |
| --- | ---: |
| Development (through 6 Aug 2012) | **4,153.60** |
| Holdout (7 Aug to 31 Dec 2012) | **5,897.80** |
| Sep-Dec 2011 | **3,609.99** |
| Sep-Dec 2012 | **5,686.81** |

The later population was substantially higher. Comparing Sep-Dec of the two years gives about **57.53% higher observed average** in 2012. This is evidence of **period difference in the published historical aggregate**, **not** independently verified causal growth, pricing/weather/capacity change or a model's forecast bias explanation.

The current engine's three expanding chronological development folds are valid for non-overlapping time ordering, but have **cold category coverage** for the calendar lookup:

| Expanding validation fold | Earlier train rows | Later validation rows | Validation dates without matching prior-month + working-day group | Calendar MAE (diagnostic) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 146 | 146 | **141/146** | 1,978.45 |
| 2 | 292 | 146 | **61/146** | 1,337.48 |
| 3 | 438 | 146 | **0/146** | 2,348.16 |

Each reference fold builds its lookup **only from prior-fold training outcomes**. Missing groups back off to the fold's month mean or global mean; as a result, fold scores reflect both time drift and **different source-category coverage**, not three equivalent calendar problems. These fold scores are **diagnostics only**, not used to tune a model or certify suitability.

There is also a future deployment limitation: `yr_0` and `yr_1` text codes encode only 2011/2012. A hypothetical 2013 record with a new `yr_2` would be an unseen category under the current categorical encoding. `OneHotEncoder(handle_unknown="infrequent_if_exist")` avoids an exception but cannot prove meaningful interpolation to future years. This is a **prospective extrapolation risk**, not an observed deployed failure.

## 4. Decision and integrity boundary

**Research feasibility finding:** Valid real data, valid target and reversible categorical representation are now confirmed; *calendar-only fixed-development historical references do not show improvement over a constant median*. This is a material reason **not** to claim an automatically valuable bike-demand model or retrospectively choose a different baseline because the first one underperformed.

Before any separately authorised disposable **model fit**, predeclare:
1. Whether the task is **each day's one-day-ahead rolling forecast** or a single fixed-origin 147-day forecast; use the *same forecast horizon and information timing* for models and references.
2. The primary no-model comparison baseline, selected without using final-holdout outcomes. For the fixed-origin design, the development-period **median** is a defensible minimum comparator; calendar group means may be retained as transparently evaluated secondary reference.
3. Which category data and past labels are available **as of each historical decision**; do not silently assume yesterday's rental count or a holiday revision was published.
4. Whether all 147 holdout days can still be considered **untouched** for a genuinely prospective model-selection study after repeated descriptive diagnostics. If not, designate a later independent period (not supplied) or explicitly label subsequent fitting as **exploratory rather than unbiased final evaluation**.
5. A genuine decision owner, action, costs, operational capacity granularity, legal/fairness and independent business signoff. Citywide daily rentals alone do not specify a station-level allocation decision or establish benefit.

**No training authorised or performed in P4-54.** No production code or source fixtures changed. Results are arithmetic cross-checked from publicly provided data, **not fresh GitHub CI execution**. Reference [P4-52 source-verified chronology](./P4_52_PUBLIC_BIKE_CHRONOLOGICAL_BASELINE_READINESS_2026-11-12.md), [P4-53 nominal-code readiness](./P4_53_PUBLIC_BIKE_NOMINAL_CATEGORY_READINESS_2026-11-12.md).

**Phase state:** P4 remains **ACTIVE**, P4-R01 through R06 remain **OPEN**, real Gate C **UNVERIFIED**, P5 **NOT AUTHORISED**, P8 **NOT CERTIFIED**. Prior historical strict original app-data entire-tree check still **FAIL** (320 backed-up files versus 346 observed, 74 browser/cache candidates, writer UNKNOWN). Separate one-use isolated native compilation permission was consumed at P4-47. Do not rebaseline, clear cache, modify installed project data or issue another installer.
