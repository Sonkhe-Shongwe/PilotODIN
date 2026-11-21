# PilotODIN | NESO Innovation Research Concept Note (UNSENT DRAFT v0.1)

> **SUPERSEDED BY OWNER DIRECTION, 13 NOVEMBER 2026: WITHDRAWN FROM ACTIVE ROADMAP.** The user explicitly rejects cold emailing or unsolicited external outreach as a condition of making PilotODIN progress. The inquiry/email/form below are a **historical, unsent draft only** and **must not be recommended, sent or used as a development dependency**. NESO official public data may still be examined for **licence-compliant, no-contact, non-operational research**, with honest uncertainty. This note changes no original R01/Gate C criteria: it remains **UNVERIFIED**, and P4 remains **ACTIVE**. No outside message was sent.

**Prepared:** 12 November 2026  
**For potential exploratory discussion with:** National Energy System Operator (NESO), Innovation Team  
**From:** PilotODIN independent prototype project; project lead's identity and formal affiliation **not supplied in this public draft**  
**Working title:** **Auditable, point-in-time validation of day-ahead electricity-demand forecasts**  
**Status:** **DRAFT ONLY, NOT SENT, NO NESO PARTICIPATION, NO PARTNERSHIP, NO LIVE OPERATIONAL USE, NO MODEL-FIT AUTHORISATION**

## Executive proposal, suitable for an initial inquiry

PilotODIN is a developing, local desktop analytics prototype that emphasises explicit human selection of prediction objectives, data-quality review, version-aware preparation and transparent model-evaluation evidence. We would like to explore whether a **strictly read-only, independent research feasibility study** could be useful to NESO's demand forecasting and innovation teams.

NESO publicly describes its demand forecasting function as providing forecasts to the Electricity National Control Centre, which supports planning and balancing electricity supply and demand. The potential contribution would **not** be an autonomous replacement for NESO's forecasting tools or any grid-dispatch decision. It would be a **transparent forecast-assurance research workflow**: reconstruct what information was published before a precisely defined day-ahead decision time, verify data/time provenance, compare like-for-like forecasts with defensible reference forecasts, and document where evaluation is reliable or where the evidence is insufficient.

**The immediate request is for an exploratory conversation only:** whether this problem and research framing are relevant to NESO, who would own any independent evaluation, which definitions and publication cutoffs NESO considers operationally meaningful, and whether public-data-only analysis would be suitable before a later formal innovation submission. We are **not requesting live dispatch access, personal or private operational data, funding, model deployment, operational endorsement or permission to change existing processes** at this stage.

## 1. Evidence-backed need and research question

NESO's publicly described control-room process includes demand forecasting, strategic planning and real-time balancing. Its day-ahead half-hourly forecast-performance resource publishes historical national demand forecasts, settlement periods, outturns, estimated TRIAD adjustments and forecast errors; reported adjustment estimates may later be revised. Forecast publication clock labels use GMT/BST local time despite some CSV timestamps ending in the literal character `Z`. The historic cardinal-point day-ahead forecast resource is **not** interchangeable with the half-hourly forecast-performance or Elexon NDF/INDO records without a justified target, temporal and grain mapping.

**Research question:** Can a reproducible, timestamp-aware and clearly explained *read-only review* of national day-ahead forecasts expose hidden source-vintage, definition, leakage and evaluation differences, and determine whether **any separately authorised** further comparison would be worthwhile?

**Possible outputs if evidence supports them:** provenance and revision exception log; honest common-period forecast-to-outturn comparisons; transparent error distributions across predeclared time windows; baseline definitions; failure/abstention documentation; brief reproducible research memo. **No claims of forecasting improvement, avoided balancing cost or operator decision benefit are currently made.**

## 2. Proposed restricted research design

**Phase A | Agree scope with the actual operator (discussion only).**
- Confirm whether a non-operational forecast-audit question is valuable. Identify the responsible business/forecast decision owner, what human decision can be improved, and whether NESO would accept an independent advisory study.
- Define the exact forecast product, measured target, MW unit, settlement-period treatment, operating-day grouping, forecast horizon, original as-issued publication clock and time zone. Agree a real decision cutoff **before** collecting or evaluating new vintages.
- Clarify what is permitted under each source's licence, especially independently published Elexon market data, and which materials may be quoted or redistributed. Do not infer operational consent from a data licence.

**Phase B | Read-only data provenance and baseline feasibility, only within authorised scope.**
- Use NESO's **Day Ahead Half Hourly Demand Forecast Performance** resource for a specifically defined forecast/outturn study. Only use separately verified matching Elexon **NDF** publication vintages and **INDO** outturns after checking equivalent definitions and permissions. Keep cardinal-point forecasts in a separate study unless correct matching has been established.
- Reconstruct *as-of* forecasts by source publication timestamp, time zone and settlement date/period. Distinguish GMT/BST wall-clock labels from genuine UTC. Flag recovered, revised and post-cutoff records. Preserve 46/48/50-period days at UK daylight-saving transitions and quarantine incomplete/duplicate periods without silently correcting source bytes.
- Exclude future/same-period outcome, after-cutoff TRIAD revisions, absolute error, APE and other leaked postdecision variables from any prospective prediction inputs. Do not assume weather, previous-day outturns or rolling references were available at the decision cutoff unless separately verified.
- Define a chronological evaluation by whole settlement days, with truly independent future measurements reserved if later authorised. A previously inspected retrospective period must **not** be marketed as blind or untouched.
- Compare the **existing published NESO forecasts** to matching outturns as one *operational forecast benchmark*. Use a **separate non-model rule** (if point-in-time feasible) as the non-model baseline. Because NESO's official forecasts are themselves generated by forecasting methods, **never label them a non-model baseline**.
- Preliminary error reporting may include MAE (MW), bias, distribution tails and seasonal/peak-period subgroup checks. It is descriptive accuracy analysis, not evidence of better real-world dispatch.

**Phase C | Conditional collaborative feasibility decision, no implied authority.**
- Only if NESO expresses interest, request an explicitly scoped data/rights review and agreement about what evidence would constitute decision utility (possible balancing error or intervention costs, human review process and independent signoff). Any later shadow proposal must be non-operational and subject to safety, data-use and authorisation review.
- A model challenger, experimental training, deployment, operational recommendation, automated dispatch action or private/system integration is **out of scope** until separately justified, authorised and evaluated. No final-stage PilotODIN release or certified Windows/offline environment exists for operational use.

## 3. PilotODIN's actual current evidence and limitations

- PilotODIN source-level preparation/review and no-fit synthetic browser tests have a tracked exact-source CI record, most recently [P4 #43299568196](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568196) and [P1 #43299568087](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568087) at `db811488...`. **These are engineering tests, not energy-system performance tests**.
- A limited existing *historical research* exercise ([P4-65](./P4_65_NESO_DAY_AHEAD_DATA_AND_NO_FIT_PROTOCOL_2026-11-12.md)) inspected a publicly provided NESO performance file, quarantining three exceptional dates and describing official forecast error. [P4-70](./P4_70_NESO_ELEXON_INDEPENDENT_ASOF_FIELD_MATCH_2026-11-12.md) independently reproduced **48/48 settlement-period MW matches for one 2025-06-15 day**, with records issued in **two distinct Elexon publication batches**; it did not establish a universal cut-off or demonstrate PilotODIN forecasting benefit. Do not extrapolate the one-day match.
- Current-source **native Windows interactive acceptance, physical sustained offline/8 GB operation and full product release safety are not certified**. The original app-data integrity incident remains an unrelated historical strict failure and must not be concealed in any later due-diligence dialogue.
- There is currently **no NESO contact, independent operator sponsor, legal/use permission for dispatch, measured operator benefit or completed innovation evaluation**.

## 4. Questions to put to NESO in the initial exploratory conversation

1. Would a **non-operational, timestamp-aware forecast assurance** and reproducible benchmark study be useful, or is there a more relevant innovation problem NESO would prefer?
2. Who is the right forecasting or business process owner to define a meaningful, human-reviewed decision and validation criteria?
3. Which official forecast vintage, exact decision cutoff, target demand definition, outturn revision and calendar conventions should govern comparable day-ahead checks?
4. Which published data resources are licensed for independent research and redistribution, and are there separate Elexon or third-party rights we should treat distinctly?
5. What minimum independent results (including an actual non-model process comparator and realistic error/intervention cost) would justify considering a further **read-only shadow** study?
6. Is an introductory discussion appropriate before the NESO **Big Idea** submission, and what project eligibility, cross-border participation, confidentiality, funding or intellectual-property conditions would apply?

## 5. Delivery route and readiness rules

**Initial recommended route:** a concise introductory inquiry to the NESO Innovation team using its official [Get involved](https://www.neso.energy/about/innovation/get-involved-neso-innovation) channel. NESO describes the Big Idea route and year-round proposal intake; **do not assume an idea is funded, eligible or accepted**. If a formal NIA collaboration is later considered, review the applicable intellectual-property rules before submitting proprietary source or commercial-sensitive material. NESO's [innovation page](https://www.neso.energy/about/innovation) describes NIA foreground-IP dissemination and accessibility obligations, which may materially matter for PilotODIN.

**Draft initial outreach email (NOT SENT):**

> **Subject:** Exploratory research inquiry: auditable day-ahead demand forecast validation (PilotODIN)
>
> Hello NESO Innovation Team,
>
> I am developing PilotODIN, an independent desktop analytics prototype focused on transparent data preparation and human-reviewed prediction analysis.
>
> I am exploring a strictly non-operational research concept using publicly available GB day-ahead demand forecasts. The idea is to examine forecast publication vintages, time-of-decision data availability, settlement-period and daylight-saving consistency, and clearly explained comparisons against independently defined reference forecasts. I would not seek operational access, deploy a model, or make grid-balancing recommendations.
>
> NESO's published forecasting and innovation work suggests this may fit your interests in trustworthy data and decision-support research. Would an initial conversation be appropriate to determine whether such a small read-only feasibility study is useful, who should review its methodology, and which data-use and proposal requirements would apply?
>
> I can share a short technical concept note if this is relevant. No partnership or results are presumed.
>
> Kind regards,  
> PilotODIN project lead  
> [Name and affiliation to be provided by the sender]

**Before any outreach:** sender must supply actual identity/affiliation and approve the final wording, check source rights/terms, decide whether public or proprietary prototype details are appropriate to disclose, and explicitly authorise submission. **No email is sent, form filled or organisation contacted by the creation of this draft.**

## 6. Sources checked for this draft (12 November 2026)

- [NESO ENCC operations and forecast-planning functions](https://www.neso.energy/what-we-do/systems-operations/what-does-day-encc-look)
- [NESO day-ahead half-hourly forecast performance](https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance) and [field definitions including local-clock Publish_Datetime](https://www.neso.energy/data-portal/day-ahead-half-hourly-demand-forecast-performance/day_ahead_half_hourly_demand_forecast_performance)
- [NESO separate cardinal-point historical resource and forecast timestamp caveat](https://www.neso.energy/data-portal/1-day-ahead-demand-forecast/historic_day_ahead_demand_forecasts)
- [Elexon NDF published metadata and one-day API restrictions](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/NDF), [Elexon INDO endpoint catalogue](https://bmrs.elexon.co.uk/api-documentation/endpoint)
- [NESO dataset-specific open licence, attribution and non-endorsement](https://www.neso.energy/data-portal/neso-open-licence)
- [NESO Innovation Get involved, Big Idea and year-round proposal information](https://www.neso.energy/about/innovation/get-involved-neso-innovation)
- [NESO innovation strategy](https://www.neso.energy/about/innovation/innovation-strategy), [AI/digitalisation innovation challenge](https://www.neso.energy/news/are-you-ready-innovate-neso), and [innovation IP context](https://www.neso.energy/about/innovation)

## 7. Governance

**Gate C / P4-R01 remains UNVERIFIED.** This document is a proposal draft, not independently observed decision-owner consent, verified as-of coverage for all features, a measured real decision benefit, a completed prospective experiment or organisational acceptance. Other P4-R02–R06 risks remain OPEN, historic original whole-app-data comparison STRICT FAIL, P5 NOT AUTHORISED and P8 NOT CERTIFIED. The prior one-use research model-fit and native compilation approvals were consumed. No product code, CI, model fit, native build, installer, data download, original-user-data operation or outbound communication took place in P4-82.
