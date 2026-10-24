# PilotODIN — Master Analyst, Master Scientist & Intelligent Target Discovery
**Status:** Product research and architecture proposal — **NOT IMPLEMENTED**  
**Discussed:** 24 October 2026  
**Project:** PilotODIN 1.0 / local-first Windows analytical workspace  
**Related:** [Current handoff](./CONTINUE_HERE.md) · [Deep research: semantic inference & candidate ranking](./TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md) · [Design history](./DESIGN.md) · [Master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)

> IMPORTANT: This document records the user's product direction and the research discussion, not proof that new autonomous features exist. Keep the existing manual Expert workflows working. Don't start implementation until an execution design, test conditions and placement in the release roadmap have been reviewed.

## Why these discoveries matter

The project is evolving from a **collection of powerful manual analytical tools** into an **expert-workflow assistant that can perform substantial analytical work automatically**.

We identified **two important and related initiatives**, with a shared foundation:

1. **Autonomous Master modes:** Master Data Analyst and Master Data Scientist should run end-to-end, professional-quality workflows from a simple user action, without forcing the user to clean each column, choose every chart, tick every predictor or compare models manually.
2. **Intelligent prediction-target discovery:** Before automated ML, PilotODIN should evaluate what is **meaningful and feasible to predict** in a dataset, prioritising real decision outcomes rather than arbitrary technically predictable fields. The discovery engine is a critical subsystem of Master Data Scientist, but a distinct product/engineering initiative worth separate design and acceptance.

Neither means “do anything silently.” A credible expert is capable of **declining**, asking one essential business question, distinguishing observed vs inferred semantics, and showing uncertainty.

## Initiative 1A — Master Data Analyst (proposed)

**User experience:** Import dataset → optionally state goal → click **Run Master Analysis** → receive a structured, inspectable work product with minimal configuration.

Proposed deterministic and reviewable pipeline:

1. Inspect row grain, likely domain, metadata, column semantics, missingness and recording conventions.
2. Profile completeness, uniqueness, validity, consistency, time coverage and plausible accuracy issues. Distinguish true source anomalies from legitimate business events.
3. Build a **reversible cleaning plan** on a **new working version**. Auto-execute only low-risk, high-confidence, technically verified transformations explicitly permitted by the eventual automation policy. Preserve source bytes, row identities, lineage and before/after quality measures.
4. **Escalate** ambiguous, high-impact or semantically destructive changes before commit. Never silently delete real outliers, erase returns, overwrite unknown dates, flatten multi-line order records, strip leading zero IDs or make up missing values.
5. Verify transformations; perform meaningful EDA, measures, trends, segments, relationships, unexpected distributions and actionable findings with correct denominators.
6. Generate relevant charts, a navigable analytical workbench, ranked evidence-led insights, recommended next steps and a version-linked report.
7. Produce an audit trail: actions taken, actions deferred, exceptions, confidence, tested assumptions, results and source-version pointers.

**Non-negotiable:** A “cleaning score” or large number of edits is not a quality goal. Data must remain fit for the real business question.

## Initiative 1B — Master Data Scientist (proposed)

**User experience:** Import dataset → optionally give decision or outcome → click **Run Master Data Science** → PilotODIN identifies credible opportunities, prepares predictors, runs a bounded model search, evaluates honestly, explains limits and saves the result.

Proposed pipeline:

1. Reuse the common dataset understanding/quality foundation.
2. Invoke **Intelligent Target Discovery** (Initiative 2) unless a user-defined objective is already provided.
3. Choose an eligible task (classification/regression; no supervised model if no defensible target). Route clustering/anomaly detection to exploratory tools when labels are absent, without mislabelling them supervised fraud detection.
4. Infer likely predictor roles, warn about identifiers, leakage, target proxies, sensitive attributes, post-outcome fields, derived labels, duplicate entities and unsuitable features.
5. Perform justified preprocessing/feature engineering **inside the training/CV pipeline**; don't leak fit statistics from the final holdout.
6. Choose random/group/time-aware validation based on actual data availability, business time ordering and repeated entities. Stop or request a targeted clarification if the split cannot be defended.
7. Compare a bounded number of feasible models against simple development-only baselines under real 8 GB resource budgets. Avoid exhausting the user's laptop.
8. Lock the chosen model before held-out evaluation; report genuine untouched-test metrics, class/segment performance where feasible, practical failure modes, calibration status and non-causal explanation limits.
9. Save reproducible model artifacts, feature schema, source data version, approvals, selection history and evidence-backed prediction/report outputs.

**Do not** automatically promise accuracy, train a fraud detector without historical fraud outcomes, claim causal effects, infer label timing without supporting evidence, or use test results repeatedly to tune/select the model.

## Initiative 2 — Intelligent Prediction-Target Discovery (proposed)

**Core question:** “Which outcome in this dataset would be *worthwhile* to predict, and can we predict it honestly from information available at decision time?”

**Inputs:** actual column names, safe value profiles, type/cardinality, missingness, class balance, plausible date/sequence fields, record grain, explicit user objective and domain metadata (if known).

**Screening sequence:**
1. Identify likely domain and business process, with a confidence/evidence explanation.
2. Generate plausible outcome candidates grounded in **existing data**; do not fabricate labels.
3. Screen out identifiers, arbitrary descriptive attributes, deterministic duplicates/formulas, leakage proxies, administrative post-outcome fields and unsupported/sensitive objectives.
4. For remaining targets, assess **(a) decision value** and **(b) modelling readiness** separately: meaningful action, label reliability/imbalance, sample sufficiency, measurement timing, feature availability, validation feasibility, fairness/privacy and computational feasibility.
5. Rank as **recommended**, **potentially valuable but needs clarification**, or **not recommended**, each with reasons and blockers. “Readiness” is never an estimated model accuracy.
6. If no credible supervised target exists, **abstain** and offer descriptive analysis, anomaly investigation, clustering or data collection guidance. Do not select a target solely because it is easy to fit.

**Illustrative examples, not validated rankings for any imported data:**

| Domain | Higher-value candidate with conditions | Typically low priority |
| --- | --- | --- |
| Insurance | `fraud_reported` only if label means what the UI says; future claim severity only if unknown at prediction time | `policy_number`, gender in default autonomous workflow |
| Retail | Future demand, returns, delivery delay, churn when labels and observation windows exist | Order IDs, arbitrary employee codes |
| Education | Future learner promotion/dropout with date-aligned information | Learner number, classroom code |
| Banking | Default or late payment with suitable historical outcome windows | Account number, branch identifier |
| Manufacturing | Fault/defect prediction with genuine pre-failure inputs | Serial number |

`device_type` might be low-value in insurance but high-value for some service-diagnostics tasks. **Business context overrides naïve universal blacklists.**

For potential fraud: distinguish *reported suspicion*, *reviewed cases* and *confirmed fraud*. If only investigated cases are labelled, selection bias and operational risk must be disclosed. Never frame a score as proof a person committed fraud.

**Ranking design principle:** Build a transparent scoring/ruleset with evidence-backed gates, not a made-up 0–100 “prediction potential” or apparent likelihood of success. The engine may use bounded cheap statistical checks on development data, but final held-out data cannot be used repeatedly to choose targets or models.

## Shared autonomous-workflow architecture (proposed)

```text
Dataset understanding / domain & grain profiling
                 |
       Evidence-backed planner
                 |
     +-----------+---------------+
     |                           |
Master Analyst             Target discovery
     |                           |
Quality/EDA/report         Master Scientist
     |                           |
     +----- Shared execution/evidence ---+
                        |
       Versioned results, visible actions,
       checkpoints, approvals, recovery and reports
```

- **Deterministic Python tools own computation and data writes.** Local Ask ODIN may help interpret goals and narrate *verified* findings, but must not invent statistics, silently execute arbitrary model-generated code, or be required for non-AI analytics.
- Execution plan should be resumable/idempotent, version-scoped and inspectable. Reuse existing Quality, Explore, Prepare, Model and Deliver modules instead of parallel contradictory pipelines.
- User control modes: **Master Auto** (minimise interruption for low-risk reversible work), **Guided** (review checkpoints), **Expert** (preserve manual tools). All modes share the same security, scientific validation and high-impact approval policies.
- Automatically execute only **explicitly authorised reversible low-risk operations** on a new working version. Decide exact operation allowlist before coding; default to proposing when uncertain.
- Preserve progress updates, cancellation, rollback/discard controls, retry/recovery, provenance, original source and version pinning.
- Any proposed 8 GB execution must account for memory, cancellation and per-project isolation, and must be proven on actual Windows hardware.

## Relationship to existing release work

- Existing **A2 Quality/Explore/Deliver** is the foundation for Master Analyst; do not rewrite or bypass it.
- Existing **A3 ML preparation/training/evaluation/prediction** is the foundation for Master Scientist; target discovery is placed **before** auto-feature selection and training.
- **B1 Ask ODIN** can provide contextual understanding/explanations only when grounded; the deterministic engine must function without AI.
- **B2 progress** should become the universal operation framework needed for both Master modes; avoid building a disposable, duplicate job system.
- **A4 Reporting** must consume trusted products of either autonomous mode.
- **Final installer/offline 8 GB acceptance** remains separate.

**Roadmap placement is NOT yet decided.** The initiatives may be named dedicated macros or cross-cutting builds after reviewing B1/B2 dependencies. Do not silently substitute them for previously promised phases.

## Open product-design and research decisions (NOT agreed or built yet)

1. How reliable domain recognition can be without a user-supplied business goal (semantics, grain, ambiguous time fields, categorical synonyms, privacy)?
2. Formal automatic cleaning allowlist, before/after validations and the approval threshold for ambiguous/high-impact actions.
3. How to determine **prediction timing** and target semantics, not merely target data type.
4. Transparent ranking criteria, abstention thresholds and duplicate/derived target treatment without costly dozens-of-model searches.
5. How to persist an autonomous run, interrupted steps, partial evidence, user approvals and final reproducible deliverables.
6. How to coordinate with B1/B2 while genuinely running offline and within the 8 GB target.
7. User-facing acceptance datasets: insurance, retail, learner promotion, fraud-labelled/unlabelled, adversarial leakage and outlier-heavy examples.
8. Whether Master Auto should initially require a one-time permission to apply predefined low-risk reversible fixes (recommended), while reviewing all material modifications separately.

## Research anchors / methodology

The product principles follow the earlier research discussion, not a claim that an academic standard certifies this implementation:
- CRISP-DM for business understanding → data understanding/preparation → modelling → evaluation and iterative review.
- UK Government Data Quality Framework for data quality dimensions and guarded correction.
- scikit-learn common pitfalls for leakage-safe pipelines and held-out evaluation.
- Google ML problem framing for decision value, labels and prediction-time feature availability.
- AutoML tools such as AutoGluon, MLJAR, Azure ML and Databricks as evidence of technical automation; auto-discovering *valuable* targets remains distinct from ordinary AutoML.
- NIST AI RMF for risk awareness, documentation, oversight and ongoing validation.

Useful public references: [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) · [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) · [AutoGluon](https://auto.gluon.ai/) · [UK Government Data Quality Framework](https://www.gov.uk/government/publications/the-government-data-quality-framework/the-government-data-quality-framework).

## Continuity rule

**In future chats, treat this as the active research/design proposal, not completed code.** Consult [CONTINUE_HERE.md](./CONTINUE_HERE.md) for actual implementation and Windows test status. Maintain historical design notes rather than rewriting history; update this living proposal when new decisions are made.
