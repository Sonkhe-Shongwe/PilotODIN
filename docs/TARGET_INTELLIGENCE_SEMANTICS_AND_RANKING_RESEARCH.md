# PilotODIN — Target Intelligence: Semantic Understanding & Lightweight Opportunity Ranking

**Status:** External research and proposed architecture ONLY. **No autonomous target discovery implemented.**  
**Research checkpoint:** 24 October 2026  
**Parent proposal:** [Master modes & target discovery](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md) · [Current handoff](./CONTINUE_HERE.md) · [QA history](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)

## The two questions studied
1. How can PilotODIN infer domain, column meaning, record grain and target semantics from unfamiliar headers and actual values **without pretending to know the business context**?
2. How can it shortlist meaningful prediction opportunities before AutoML, **without training models for every column**, leaking future/holdout information or overspending CPU/RAM on an 8 GB Windows laptop?

### Evidence from external research, separate from our design inferences

- **Sherlock** (Hulsebos et al., KDD 2019) combines statistical, character-distribution and language-based representations to detect semantic column types; evaluated on 78 types with reported support-weighted F1 of 0.89. This concerns type detection, NOT business purpose or outcome timing. https://vis.csail.mit.edu/pubs/sherlock/
- **Sato** (Zhang et al., PVLDB 2020) adds table context to value signals and reported 0.925 support-weighted / 0.735 macro F1 on its semantic typing benchmark; benchmark performance should not be extrapolated to arbitrary private business data. https://arxiv.org/abs/1911.06311
- **GitTables** (Hulsebos et al.) provides a corpus of real GitHub CSV-derived tables and ontology annotations; it demonstrates domain shift between web tables and real tables. https://gittables.github.io/ and https://arxiv.org/abs/2106.07258
- **DataHub Business Glossary** links canonical business terms and definitions to physical columns; domain metadata is essential beyond string matching. https://docs.datahub.com/docs/glossary/business-glossary/
- **Google ML Problem Framing** requires an actionable purpose, reliable outcome labels and predictor availability when predictions are made. https://developers.google.com/machine-learning/problem-framing/problem
- **Azure Automated ML / Databricks AutoML** show that mainstream AutoML workflows still explicitly take the user-selected target. Target discovery is a problem-framing layer *before* AutoML, not a claim that ordinary AutoML already solves it. https://learn.microsoft.com/azure/machine-learning/how-to-use-automated-ml-for-ml-models?view=azureml-api-2 and https://docs.databricks.com/aws/en/machine-learning/automl/automl-api-reference
- **scikit-learn common pitfalls** and **nested CV** explain leakage from preprocessing/selection and optimistic estimates when the same held-out data guides repeated choices. https://scikit-learn.org/stable/common_pitfalls.html and https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html
- **Feast point-in-time features** and Azure Databricks point-in-time joins illustrate why timestamps and 'known as of' metadata are necessary to exclude future features. https://docs.feast.dev/getting-started/concepts/feature-retrieval and https://learn.microsoft.com/en-us/azure/databricks/machine-learning/feature-store/time-series
- **Datasheets for Datasets** (Gebru et al., CACM 2021) documents dataset purposes, collection, labels, composition, intended uses and limitations: needed to distinguish apparent semantics from actual provenance. https://www.microsoft.com/en-us/research/publication/datasheets-for-datasets/
- **DuckDB** offers sampling and approximate distinct/quantiles/top-k to bound exploration; seeded reservoir sampling requires care with parallel execution for reproducibility. https://duckdb.org/docs/current/sql/samples and https://duckdb.org/docs/current/sql/functions/aggregates.html
- **Google Rules of ML** recommends simple metrics/baselines before expensive complex modelling. https://developers.google.com/machine-learning/guides/rules-of-ml
- **NIST AI RMF MAP** requires documenting intended context/use and limitations, not optimising predictive scores in isolation. https://airc.nist.gov/airmf-resources/playbook/map/
- **Positive-unlabeled learning literature** describes selection bias where fraud examples are labelled because suspicious cases are preferentially investigated; a missing fraud label must not be equated to confirmed innocence. https://pmc.ncbi.nlm.nih.gov/articles/PMC8075513/

## A. Proposed semantic understanding engine

Do NOT infer business meaning from physical dtype alone. Keep these five layers independent:

1. **Physical profile (observed):** pandas/Arrow dtype, parsing patterns, missingness, distinctness, sample values and invalid tokens.
2. **Structural role (inferred):** entity identifier, temporal key, monetary measure, dimension, status/label, free text, join key or calculated field.
3. **Semantic hypotheses (inferred):** insurance claim amount, post-investigation fraud flag, product return, medical treatment outcome, learner progression etc. Include top alternatives and evidence/contradictions.
4. **Dataset-level context (inferred):** likely business domain, row grain, source system, relationships, event timeline and who/what one row represents.
5. **Operational meaning (must be substantiated):** definition of target, who labels it, what action follows, what is known at the requested decision time, allowed uses, and whether data was selectively collected/reviewed.

Evidence sources in preference order:
- Explicit user goal, documented data dictionary, source provenance/business glossary.
- Stable technical metadata, names, value profiles and cross-column consistency.
- Local contextual language reasoning, only on sanitised metadata summaries, never as a factual substitute for unknown label provenance.

**Confidence model:** publish 'observed', 'inferred', 'user-confirmed' or 'unknown' for each claim. An LLM's self-reported percentage confidence is not a measured/calibrated probability. When critical fields conflict or business timing is unknown, ask ONE targeted business question or leave the status unresolved.

Example: `fraud_reported` + Y/N strongly indicates a binary field and a plausible fraud-related topic, but NOT confirmed fraud, who investigated it, whether N means 'investigated non-fraud' or 'unreviewed', or whether this label is available before claim approval.

**Record grain first:** a repeated `OrderID` may mean line items and a repeated `CustomerID` may mean a longitudinal series. Neither should be called duplicate/error or be used as a target just on cardinality.

**Local-first implementation route:** cheap rule/pattern signatures and seeded bounded value samples; expandable curated domain glossary; table-level context reconciliation; optional local Ask ODIN only to explain and propose constrained schema-validated hypotheses. Record which signals support each claim and which are missing.

## B. Proposed cheap ranking engine — no blanket model training

### Gate 0 — available task types
- Candidate supervised outcome must be an existing historical label or a **well-defined approved transformation** with legitimate observation windows.
- Detect classifications, regression and (later) genuine chronological forecasting separately; 'no valid supervised target' must be a normal outcome.
- Without reliable labels, offer descriptive analysis/anomaly investigation/clustering as distinct tasks, NOT trained supervised fraud inference.

### Stage 1 — O(rows × columns) lightweight profiling
Only bounded schema/metadata and small repeatable samples; count target present/missing labels and class support, cardinality, plausible identifiers/sensitive attributes, dates, simple formula relationships. Source data is read-only and version-pinned. Large profiling tasks may be streamed; exact counts vs sampled estimates are explicitly labelled.

### Stage 2 — candidate generation without training
Use canonical outcome vocabularies ('fraud', 'default', 'promoted', 'returned', 'failed', 'churn', 'settled', 'amount', 'time_to_resolution', etc.) **plus dataset domain context**, with a fallback generic operational-event pattern. Generate alternatives, not just one overconfident answer. Label domain heuristics 'provisional', never universal.

### Stage 3 — hard validity and risk gates
Refuse or hold for review when:
- target is an identifier, constant/all-missing or unduly fragmented high-cardinality free text;
- label source/timing/meaning is materially ambiguous (e.g. `fraud_reported` vs confirmed fraud);
- target is an exact formula from available input fields, already known at decision time, or all plausible predictors are recorded after outcome;
- multiple records/entities, future leakage, label-selection bias or operationally dangerous/sensitive uses cannot be resolved;
- no defensible temporal/group holdout or enough examples/rare positives exist;
- computing planned models would exceed local caps.

These are **gates**, not compensable point deductions. Name-based leakage detection alone is insufficient; use provenance/timestamps when present and stop for missing critical facts.

### Stage 4 — transparent opportunity ranking
Maintain **two separate ordinal assessments** with rationales:
- **Decision relevance:** what action would change, when, by whom, and how would the decision be better than a simple rule?
- **Modelling readiness:** real verified labels, adequate support, allowable pre-outcome predictors, defensible validation and resource feasibility.

Then rank **eligible** candidates, explaining blockers and leaving tied/uncertain choices visible. Do NOT invent a 92% 'predicability' score or compare unknown potential classification accuracy against regression errors.

Proposed status labels: `ready for pilot`, `needs one key answer`, `insufficient evidence/labels`, `not recommended`.

### Stage 5 — only then a bounded ML pilot
- Shortlist (proposed initial ceiling **3 targets**, configurable after profiling; a product setting, NOT a research-derived universal constant).
- If business purpose still unknown, first ask for the target/decision choice rather than train several targets.
- Decide the target **before** reserving its final untouched holdout. For each independently authorised task define target timestamp, forecast horizon, key entities and allowed predictors. Select validation strategy (time/group/random) using actual data, not a guess.
- Start with **zero models during ranking**. After decision is made, run an inexpensive majority/median heuristic and at most a small, explicit model-family pilot *on training/development folds only*. Escalate to full A3 comparison only if justified.
- Never rank targets by their final heldout performance; that would make the final set a hidden selection loop. If trying many targets and repeatedly reporting results, do not present them as independent unbiased tests.
- Use existing A3 budgets (general 30k labelled rows, kernel SVM/SVR 5k, KNN 12k, 256 MiB estimated dense features) as provisional training guardrails, not peak RAM promises.
- Publish a reproducible candidate decision ledger, selected goal, blocked alternatives, feature eligibility, split logic, bounded runtime and actual accepted/rejected models.

## C. Worked example (NOT a calculated result for the owner's insurance dataset)

| Candidate | Business relevance (hypothesis) | Readiness from names alone | Gate |
| --- | --- | --- | --- |
| `fraud_reported` | Potentially high, because investigations can be prioritised | Unknown: label provenance, investigated-population bias, positive case count and predictor timing | NEEDS VERIFICATION; no automatic fraud-as-fact claims |
| `total_claim_amount` | Conditional, useful only as future cost/severity | Unknown: amount may already be known at submission | NEEDS PREDICTION-MOMENT DEFINITION |
| `gender` | Usually low for default claims workflows; sensitive attribute considerations | Even if simple to classify, business purpose not justified | DON'T AUTO-RECOMMEND |
| `device_type` | Depends on domain; weak in generic insurance, potentially useful in device diagnostics | Undefined without goal | DEMOTE, NOT ALWAYS BLOCK |
| `policy_number` | No legitimate predictive decision by default | Identifier | HARD BLOCK AS TARGET |

## D. Concrete proposed architecture contracts (design only)

```text
Original dataset (immutable)
   -> Column & row-grain profiler (observations)
   -> Evidence-led semantic role hypotheses + glossary/context
   -> Prediction opportunity candidates (no training)
   -> Purpose / target time / label source / risk gates
   -> Value and readiness ranking / abstention
   -> User or bounded-policy target decision
   -> Train-only feature engineering & group/time split
   -> Cheap baseline -> bounded AutoML development search
   -> Frozen holdout evaluation -> provenance and report
```

Suggested records (future APIs, NOT existing):

- `ColumnMeaningEvidence`: column, physical_type, structural_roles[], semantic_hypotheses[], observed_fields[], evidence[], counterevidence[], evidence_status, lineage.
- `PredictionOpportunity`: target_column, task_kind, proposed_decision, prediction_moment, horizon, outcome_definition, label_source, candidate_feature_policy, blockers[], relevance_assessment, readiness_assessment, eligible_status, reasons[], alternatives[], dataset_version.
- `DiscoveryRun`: dataset hash, schema fingerprint, engine/glossary versions, user objective, sample seed/method, ranked candidates, abstention reason, actions requested, no-models-trained flag, traceable calculations.

Re-use Quality/Explore/Prepare/Model/Deliver, existing approved versions and future B2 orchestration. Avoid a second incompatible experiment/report store.

## E. Empirical validation plan (must be built before claiming success)

- Curate 20–50 varied table fixtures with *human-reviewed business meaning*, including messy headers, cross-domain terms, mixed languages, multiple grains, short ambiguous names and privacy-sensitive columns. Not a training benchmark claim.
- Include disambiguation pairs: actual null vs literal `(Missing)`; `fraud_reported` vs `fraud_confirmed`; `claim_amount` known vs future settlement; `OrderID` multi-line items; post-outcome leakage traps and repeated entities.
- Measure semantic classification accuracy/top-k and **abstention calibration** on unseen domains, not only familiar examples.
- Separately measure target-recommendation precision at top 1/top 3 against expert-reviewed actionability; false 'ready' recommendations are more costly than abstaining.
- Test absence of cross-project/raw sensitive data exposure, split leakage and invented metrics.
- Profile actual 8 GB Windows CPU/RAM/time and cancellation under worst cases.
- Hold back unseen *datasets/domains* for evaluation of the target-discovery rules themselves; do not endlessly tune the same fixture list.

## Decision state

This is a detailed **proposed** pipeline grounded in external sources. Exact candidate ranking rubric, dataset governance policy, semantic glossary, optional local-LLM boundary, acceptance thresholds, top-K ceiling and target-confirmation policy have **not yet been approved or implemented**. Discuss/decide these before coding.

**Short answer to research questions:** Train no models to discover whether a target is meaningful; use evidence-backed table semantics + provenance first. Semantic models detect plausible column *types*, not guaranteed business truths. Rank objectives by actionability and scientific feasibility, apply hard safety gates, and only fit bounded models after a defensible task is selected.
