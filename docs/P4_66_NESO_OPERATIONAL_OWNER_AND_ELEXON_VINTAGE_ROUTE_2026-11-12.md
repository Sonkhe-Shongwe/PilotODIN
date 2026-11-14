# PilotODIN 1.0 | P4-66 independent NESO operational authority, Elexon vintage route, and cutoff exceptions

**Date:** 12 November 2026. **Evidence type:** independent online official-source review plus read-only verification of the already-supplied public NESO CSV. **Not:** an observed Elexon forecast record, a new model fit, CI execution, owner-system access, source change, operational approval, measured benefit or P4 closure.

## 1. What is independently supported

- NESO confirms its Electricity National Control Centre (ENCC) has a **demand forecasting team** supplying forecasts to the control room, a **24-to-4-hour strategy/planning** team, and a **4-hour-to-real-time energy/balancing** team responsible for actual dispatch. The institution and workflow are documented. This does **not** imply those operators asked for PilotODIN, approved its recommendations or changed a decision: https://www.neso.energy/what-we-do/systems-operations/what-does-day-encc-look
- NESO's ENCC describes actual balancing actions and security/cost tradeoffs: https://www.neso.energy/what-we-do/systems-operations/what-does-electricity-national-control-centre-do
- NESO explicitly describes the P4-65 performance dataset as **historical day-ahead national demand forecasts as published via BMRS**, with outturn and potentially retrospectively revised TRIAD values: https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance
- Elexon's official developer portal says **Dataset endpoints provide material published as received from the provider**, permit filtering by publish times and retrieving superseded historical forecasts: https://developer.data.elexon.co.uk/
- Elexon's official BMRS **NDF** endpoint documents `publishDateTimeFrom` and `publishDateTimeTo`, maximum **one day** per request, and output fields including `publishTime`, `startTime`, `settlementDate`, `settlementPeriod`, and `demand`. This is an **independent verification route**, not yet verification of any row: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/NDF
- Elexon also lists historical day-ahead forecast **history**, **earliest**, and **latest** endpoints. Their existence is not proof of coverage for a particular old date or of exact equivalence to the performance-file vintage: https://bmrs.elexon.co.uk/api-documentation/endpoint
- Ofgem's independently published Performance Panel assessment documents potential consumer benefit from better demand forecast accuracy, but it does not quantify savings resulting from PilotODIN or authorise its operational use: https://www.ofgem.gov.uk/decision/performance-panels-end-scheme-report-nesos-performance-over-business-plan-2

## 2. New independent CSV timing verification

Re-read owner-uploaded `1b-incentive.csv`, **SHA-256 `a9992f87a766f3cf3307b24cc7c9940e797bdea855427e6e31647984e27bdc0f`**, using a new temporary read-only stdlib scan. Exactly **2,052 of 2,052** unique target dates have one internally consistent `Publish_Datetime` whose calendar date is the preceding day. This proves a **within-file date relation**, not independent message issuance.

Distribution of the **literal printed clock time** by target date: `08:33` 118 days; `08:45` 602; `09:03` 2; `09:33` 282; `09:45` 1,042; `10:03` 4; `10:33` 2. Six **complete, otherwise P4-65-eligible** dates exceed **10:00** in the source's printed clock time:

| Forecasted target date | CSV Publish_Datetime | Count |
| --- | --- | ---: |
| 2026-02-01 | `2026-01-31T10:33:00Z` | 48 |
| 2026-02-08 | `2026-02-07T10:33:00Z` | 48 |
| 2026-09-02 | `2026-09-01T10:03:00Z` | 48 |
| 2026-09-09 | `2026-09-08T10:03:00Z` | 48 |
| 2026-09-14 | `2026-09-13T10:03:00Z` | 48 |
| 2026-10-20 | `2026-10-19T10:03:00Z` | 48 |

**Important:** `10:00` is only a hypothetical research cutoff, **not** an approved NESO decision time or assertion that these are regulatory-late releases. The source schema labels these clock values **GMT/BST despite a literal Z suffix**; do not silently parse them as UTC. A proposed 10:00 previous-day eligibility policy would need to exclude/review these six target days. An 11:00 previous-day research cutoff covers the printed values internally but **does not prove** independent publication by then, operational availability or correct zone conversion. Do not change P4-65's 98,350-row geometry merely for this new conditional research timing observation.

## 3. Unresolved exact-source cross-check

**NOT EXECUTED / UNVERIFIED:** A live historical Elexon NDF API response could not be retrieved via the tools available in this session; therefore **zero NESO-versus-Elexon forecasts, publication instants, or settlement-period values have been matched**. Do not report a PASS or invent a retrieved API sample.

A genuinely independent verification should first obtain one *small* Elexon historical NDF publication window for a normal 48-period day. Freeze response bytes and origin/time; use Elexon's actual `publishTime` and `settlementDate + settlementPeriod` fields, and compare forecast MW values to the exact same NESO day, distinguishing earliest/current/historical revisions. Explicitly reconcile Elexon UTC `publishTime` with NESO's GMT/BST-labeled `Publish_Datetime`. If any discrepancy arises, investigate feed/vintage definitions and do not self-adjust historical data to force a match. Only then expand to representative seasons, exceptional periods and publication revisions. Do not perform a training run.

## 4. Original Gate C evidence boundary and next justified action

**Positive independent context:** real institution and operating teams, official published forecasting performance dataset, official independent market-data archive retrieval mechanism, and verified within-file publication-date relationship.

**Still missing:** proven identical *as-issued* vintage at a real predecision timestamp; an authorised real operational human willing to use PilotODIN; independent as-of input sources and label revisions; measured comparative human decisions, cost/error/fairness and benefit. Evidence of NESO's *existing* forecasting function does not supply a PilotODIN decision owner or trial. Public forecast MAE/APE alone cannot prove monetary savings.

No new GitHub Actions, application source, model fit, CI dispatch, native build, installer, original app-data access or public disclosure of private records. **P4 ACTIVE; P4-R01–R06 OPEN; original real-business Gate C UNVERIFIED; historical original whole app-data-tree STRICT FAIL unchanged; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** One-use native and bike-fit permissions remain consumed.

**Next:** retrieve and independently authenticate an exact historical NDF response *if access becomes available*, or obtain a genuine operational owner/decision/benefit authority. Do not keep generating synthetic research scores or treat documentation as acceptance.
