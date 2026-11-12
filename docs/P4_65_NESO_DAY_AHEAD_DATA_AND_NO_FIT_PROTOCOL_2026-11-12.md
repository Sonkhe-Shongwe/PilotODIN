# PilotODIN 1.0 | P4-65 NESO day-ahead data integrity and no-fit protocol

**Date:** 12 November 2026. **Scope:** read-only independent audit of one public user-supplied CSV, frozen settlement/date research view, descriptive existing-baseline arithmetic. Not a model fit, prospective operational trial, business approval, native Windows acceptance or phase closure.

## Exact uploaded input and independent source

- User-uploaded **1b-incentive.csv** (not uploaded into this GitHub repository): **9,740,124 bytes**, **98,466 rows**, **11 fields**, SHA-256 **a9992f87a766f3cf3307b24cc7c9940e797bdea855427e6e31647984e27bdc0f**.
- Official source: https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance ; exact official resource schema: https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance/day_ahead_half_hourly_demand_forecast_performance.
- NESO defines its forecast/outturn and TRIAD avoidance correction fields and states that TRIAD estimates may be revised retrospectively. NESO describes **Datetime and Publish_Datetime as GMT/BST local clock labels**, even though CSV values end in a literal Z. Do **not** infer UTC from the suffix. Independent official settlement-day 46-/50-period explanation: https://www.neso.energy/data-portal/daily-balancing-volume-balancing-services-use-system/daily_balancing_volume_2025-2026.
- This SHA pins **the uploaded bytes**, not a signed original NESO release-vintage archive, independently established publication instant or immutable contemporaneous truth. NESO open-data rights do not constitute endorsement or permission to operate its grid systems.

## Reproducible conservative settlement-day inclusion

For each local Date, determine its exact 46, 48 or 50 half-hour settlement periods from the **Europe/London local-midnight to next-local-midnight duration measured in UTC**. Eligible dates must contain the exact expected number of rows, every Settlement_Period integer from 1 to expected exactly once, and one consistent daily Publish_Datetime. Preserve all other legitimate 46-/48-/50-period days. Do not overwrite, repair, deduplicate or silently reindex source rows. Entire anomalous dates remain in the exception ledger.

| Quarantined date | Actual/expected rows | Exact reason |
| --- | --- | --- |
| 2021-10-31 | 50/50 | Periods 4 and 5 duplicated, 2 and 3 absent |
| 2022-10-30 | 48/50 | Periods 2 and 3 duplicated; 21, 22, 49 and 50 absent |
| 2026-11-12 | 18/48 | Incomplete last date; periods 19-48 absent |

**Result:** **116 records quarantined; 98,350 eligible rows on 2,049 dates**. Zero blank CSV fields or duplicate entire rows. Exactly one prior-calendar-day publication timestamp per day in this snapshot. No proof that the timestamp was independent of later revisions. The raw Datetime calendar day differs from Date in 2,053 records; do not use naive Datetime as a unique settlement join key.

## Source error arithmetic, independently checked

All **98,466** rows satisfy **corrected outturn = raw outturn + TRIAD estimate** and **Absolute_Error = absolute(forecast - corrected outturn)**. Published APE matches **100 * Absolute_Error / corrected outturn** within 0.05 percentage points (rounded field). **313** rows have a nonzero TRIAD adjustment.

- Entire unfiltered CSV, mean published corrected absolute error: **645.2209 MW**. Comparing to raw uncorrected outturn yields **645.5553 MW**, which is not NESO's defined error measure.
- Conservative eligible view: **644.7488 MW** published forecast MAE, **2.5142%** mean of published rounded APE.

## Chronological no-fit partitions (historical, already inspected)

| Partition | Inclusive dates | Eligible rows / dates | Existing NESO MAE (MW) | Published mean APE |
| --- | --- | --- | ---: | ---: |
| Historical development | 2021-04-01 to 2024-12-31 | 65,710 / 1,369 | 607.5977 | 2.3187% |
| Historical validation | 2025-01-01 to 2025-12-31 | 17,520 / 365 | 679.4651 | 2.6908% |
| Inspected retrospective | 2026-01-01 to 2026-11-11 | 15,120 / 315 | 765.9768 | 3.1592% |

All partition figures are **descriptive results of NESO's already-published forecast only**, computed on identical eligible period geometry and corrected-outturn definition. Their error differences are not an improvement claim, a causal trend or a PilotODIN experiment. Because historical outcomes and these metrics have been inspected, the 2026 block is **NOT blind/prospective**, even if later called a holdout.

## Mandatory contract before any separately authorised future fit or utility claim

1. Define an advisory day-ahead electricity-demand or forecast-review decision, a real decision owner, and a fixed forecast horizon/cutoff. **No autonomous operational grid actions.**
2. Independently verify forecast-vintage publication timestamps and source-as-of feature availability. The current file's previous-day calendar date does not establish verified UTC time, vintage integrity or retrospective corrections.
3. Block all same/future-outcome predictors: **Demand_Outturn, TRIAD_Avoidance_Estimate, TRIAD_Avoidance_Corrected_Demand_Outturn, APE, Absolute_Error**, and any post-cutoff inputs. Published Demand_Forecast, Date and Settlement_Period remain only candidate predecision fields until provenance checks pass.
4. Use strict chronological train-only transformations and development folds, settlement-day grouping and no random half-hour row splitting across days. One fixed official NESO baseline and the same target/time/eligible rows for every comparison.
5. Treat existing 2021-2026 retrospective observations as **inspected**, not an untouched final test. Truly blind claims require a future snapshot/window frozen before actual outcomes, with separate permission and no leaked adjustments.
6. Even if forecast MAE improves, require independent lawful intervention, human decision authority, labels and as-of system records, benchmarked existing process, intervention/error costs, fairness review, actual measured utility and owner signoff. No measured business benefit exists in this audit.

## Local verification chronology and residuals

- First **local synthetic test** pass exposed a verifier-helper empty-period division-by-zero edge case (two errors in five synthetic checks). This was **a new local verifier's bug**, not an application error or finding in NESO source data. Corrected locally without GitHub application changes.
- Final local synthetic verifier suite **5/5 PASS**: UK DST 46/48/50 periods; read-only valid synthetic audit; duplicated-period quarantine; changed error rejection; wrong snapshot hash refusal.
- Local stdlib-only verifier scanned all **98,466** uploaded rows; independent read-only pandas calculations agreed on row counts, 313 adjustments, eligible-view mean errors and all three historical partitions. The standalone verifier and tests remain conversation artifacts; no dataset, helper code, model weights or original private files were committed.
- **Blocked/unverified:** actual historical issued-vintage/UTC reconciliation, independent business decision owner and lawful operational use, real measured utility/cost/fairness, truly prospective evidence, and separately authorised native 8 GB/offline validation. This research does **not** replace the P4-61 internal CI shadow-study charter or supply original Gate C approval.

**Binding disposition:** P4 Target Intelligence ACTIVE; P4-R01–R06 OPEN; original real-business Gate C UNVERIFIED; prior original entire app-data-tree STRICT FAIL (320 backup files vs 346 observed, historical writer UNKNOWN) unchanged; P5 NOT AUTHORISED; P8 NOT CERTIFIED. No new CI dispatch, fit, native build, installer, owner Windows or original app-data access.

**Next justified action:** Independently source an operational decision owner and exact archived forecast-vintage / source-as-of evidence, or receive separate owner approval for the already-defined consolidated native acceptance. Do not manufacture model scores or repeat public-data studies merely to create a new commit.