# PilotODIN — Consolidated Feature Inventory & Complexity-Last Roadmap

> **EXECUTION PRECEDENCE, 4 November 2026:** The 24–26 October paragraphs below saying P2 is the active priority are historical. The [owner-adopted 28 October one-phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) makes **P1 the only current primary phase**. This page remains the binding **complexity-last sequence and feature inventory**, **not** the current acceptance/status ledger. Use [current status](./PROJECT_STATUS_CURRENT.md) and [current P1 handoff](./SESSION_HANDOFF_CURRENT.md) for live work. No phase is declared complete by this notice.


> **STATUS REFRESH, 26 October 2026:** This file remains the binding **complexity-last sequencing roadmap**, not a live release acceptance ledger. The verified cross-phase position now appears in [P0–P8 Status Reflection](./PILOTODIN_STATUS_REFLECTION_2026-10-26.md), and the exact next action in [Current Session Handoff](./SESSION_HANDOFF_CURRENT.md). After this roadmap was written on 24 October, the owner accepted focused P3 semantic, P4 target-screening/context, P5 task-control and multiple P2 Deliver gates; those slices do **not** imply those entire phases or P8 are complete. **Active priority remains P2**, especially frozen Python font resource packaging and actual Unicode PDF integration. On 26 October the owner passed **8/8 future font-path synthetic tests** and a **6-file build-review identity/receipt check**, both explicitly **NOT** an actual PyInstaller bundle test. Previous accepted P2 3+9 mixed, 5/5 disclosure, chart visual and 9/9 isolated CMap tests stand. Actual offline model+ML 8 GB feasibility, universal task scheduler, Master modes and E-01–E-24 clean Windows release remain unaccepted. Do not replay accepted tests or launch installers merely to satisfy this historical roadmap.

**Date:** 24 October 2026  
**Status:** Architecture/implementation-sequencing recommendation; no code changed as part of this decision.  
**Current branch:** `feature/live-dev-workspace-20261023`  
**Sources of truth:** [Living handoff](./CONTINUE_HERE.md) · [Master reconstruction blueprint](../README.md) (original DOCX retained by owner) · [Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) · [A2 checklist](./MACRO_A2_CONSOLIDATED_ACCEPTANCE.md) · [A3 checklist](./MACRO_A3_ML_ACCEPTANCE.md) · [Master modes research](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md) · [Target intelligence research](./TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md)

## The owner's sequencing preference

**Prioritise simpler, testable, deterministic features and functional journeys first. Leave the largest autonomous-AI, scheduler/crash-recovery and offline bundled-runtime implementation for later.** Do not conflate **late implementation** with **late feasibility proof**. An early, tightly scoped local-Qwen/8 GB/offline-WebView2 spike is necessary to detect a potential blocker before substantial dependent architecture is committed.

The original master blueprint describes (a) feasibility gate E2 early and (b) final Build E/F implementation/release only after proof. This document preserves that risk strategy while making the *major implementation order* complexity-ascending.

## Evidence snapshot — do not call partially tested work complete

| Existing area | Actual state | Required confirmation |
| --- | --- | --- |
| Desktop foundation & unified project shell | React/TypeScript + FastAPI + Tauri source; native launcher preview and historical Windows hotfix validation; per-project contextual modes exist | Resizable tabs/docks/layout persistence, smaller Windows viewports, security/session, fully offline packaged app and clean installer NOT accepted |
| Import and versioned Quality | CSV/XLSX import, versioned working data, approvals, Quality findings, preview/investigation and exports in source | Full malformed/oversize/interrupted import, raw/working lineage, Save As desktop and exact version/row checks |
| A2 Explore and analysis | Linked filters/charts/record inspector, column dictionary, Quality handoff, saved analyses, version-bound evidence; source fixes for saved-history Open | 83 frontend + 107 focused backend tests passed on user's Windows checkpoint, build passed. Complete manual A2 walkthrough (including latest Open scroll) not signed off |
| Investigation & evidence | Durable investigation artifacts, typed local analysis, some planner/evidence foundations exist | Objective-aware plans, accurate tied-group interpretations, version-grounded conclusions, autonomous repair/stopping and actual AI inference remain unresolved |
| A3 Expert ML | Feature audit and risk review, CV/time/group split guards, model families/budgets, selected-model heldout baseline, bounded explainability, prediction caveats | 99 frontend + 27 focused backend Windows tests passed and frontend build passed; **actual user Prepare→Train→Evaluate→Predict**, 8 GB stress and cross-project/version acceptance pending |
| A4 Reporting | Saved report revisions, frozen investigation and Explore snapshot evidence, PDF and HTML export exercised on Windows | Professional layout, clearer composer, model/Quality/chart evidence coverage, exact HTML filenames / native Save As, report output parity and formatting |
| B1 Ask ODIN | Limited planner and deterministic fallback foundations; Settings may expose model state | A specific real local-Qwen generation with verified evidence not demonstrated; autonomous tool loop/recovery and accurate UI status still major gap |
| B2 Task/progress | Individual async-task and state features exist | One unified durable queued/running/approval/paused/cancelled/retry/recovered protocol not accepted |
| Master Analyst, Master Scientist, Target Discovery | **Research/architectural decisions only** | None of the autonomous Master modes/semantic target-ranker implemented |
| Full 1.0 integrated offline desktop | No accepted final installer | Clean offline Windows launch without separately installed Python/Node/Ollama; bundled runtime/AI/WebView2, actual 8 GB coexistence, privacy/security/migrations and complete end-to-end acceptance |

**Test totals are separate checkpoints on different code revisions.** Do not add them up to claim an independent full-system suite, and do not confuse implementation with Windows acceptance.

## Consolidated feature inventory (original vision + subsequent design)

1. **Workspace and Projects:** home/recent/resume, project creation/import/switch/rename/archive, dataset provenance, one active dataset, persistent project tabs, primary/secondary resizable panes, contextual ODIN dock, responsive rail, navigator visual identity, keyboard support, command palette, Settings.
2. **Import and storage:** robust CSV/XLSX, sheets/previews, type/locale overrides, protected IDs/leading zeros, bounds and malformed-data safety, source checksums, immutable original, approved working versions, history and restore, per-project data isolation, transactional storage and recoverability.
3. **Data Quality:** missing/duplicate/type/outlier/identifier findings, contextual source-row preview, why/what-to-do interpretations, explicit reversible proposals and one-time version-pinned approvals, undo/restore, safe CSV/XLSX export by version and selected rows/columns.
4. **Explore / analytics:** profile and column dictionary, metrics/aggregations, linked filters, histogram/box/scatter/bar/line, correlation heatmap, sample/count denominators, record-level drill-down, proactive evidence links, saved analytics and read-only frozen snapshots; accessibility and accurate statistics.
5. **Investigate:** objective, persistent investigation, typed tool plans, group comparisons, trends, distributions, verified evidence, notes and explanations, provenance and a navigable investigation timeline; eventual ODIN-supported multi-step runs.
6. **Expert ML:** Prepare, target/feature/split selection, baselines, model library, leakage guards and preprocessing within CV folds, asynchronous training, evaluated selected model on untouched holdout, feature sensitivity, Predict form/schema, validation and saved experiment artifacts.
7. **Deliver:** report library/composer, immutable revisions, analysis+investigation+Quality+ML evidence, rich charts/insights, CSV/XLSX cleaned-data export and consistently named HTML/PDF professional reports.
8. **Master Analyst (new):** one-click quality audit, safe/non-destructive cleaning plan, approved low-risk working changes, regenerated quality check, domain-specific insights/charts and evidence-backed analytical report. Escalate ambiguous/meaning-changing operations.
9. **Semantic Understanding (new shared service):** infer likely domain, record grain, column roles and business meaning from schema/profile/glossary, separate observed/inferred/confirmed/unknown, support ambiguity and abstention.
10. **Target Intelligence (new):** no-model-cost candidate generation, business-value vs modelling-readiness ranking, label/timing/leakage/hard eligibility gates, explanation of lower-ranked targets and abstention. **User always explicitly selects the target**; system does not auto-commit it.
11. **Master Scientist (new):** after the user selects target, automate safe predictor selection, feature engineering, defensible validation, affordable candidate models, selected-model evaluation/explanation and report while preserving scientific stop/review gates.
12. **B2 universal tasks:** actual queue/progress/elapsed and phase counts, cancel, pause for resources/approvals, retry, durable persistence, resume after crash, truthful failures and final-state acknowledgement.
13. **B1 Ask ODIN full intelligence:** functional bundled/offline Qwen inference, grounded interpretations and question-to-typed-tool orchestration, model/provider status and fallback transparency, tool validation, limited repair and safe stopping; prompt-injection/privacy controls.
14. **Native Windows release:** production desktop shell, self-contained Python sidecar+web frontend+WebView2+local model/runtime, bundled offline launch, 8 GB joint-load measurements, installer signing/upgrade/data preservation/security and full clean-machine acceptance.

Historical Build E QA issue row statuses may be stale; use dated later comments and relevant acceptance docs before calling a defect open or fixed.

## Proposed IMPLEMENTATION ORDER — simple to complex

| Priority | Deliverable package | Complexity | Entry/exit principle |
| --- | --- | --- | --- |
| **P0 — Now** | **Close functional acceptance and correctness**: A3 full Prepare→Model Lab→Evaluate→Predict on disposable data, A2 remaining visual steps, earlier analytical interpretation/ties, export naming, project switching and actual error paths | Low–medium | Existing code first; repair actual defects with small local regression runs; no new grand system |
| **P1** | **Data/project/UI reliability**: robust import boundaries, persisted project state, last UX defects, verified Quality flows, accessible windows/nav, version isolation; **first read-only Resource-Aware Mode settings and RAM status slice** | Medium | Golden dataset flows, no silent changes or lost data; resource modes cannot bypass existing guardrails |
| **P2** | **A4 Reporting polish and evidence composition**: analyst-grade layouts, verifiable model/Quality/Explore/Investigate artifacts, HTML/PDF parity, export names and Save As | Medium | Real browser/Windows report preview and immutable revision checks |
| **P3** | **Shared deterministic semantic profile**: business/column/record-grain hypotheses, local glossary and concise bounded evidence; show observed vs inferred vs unknown | Medium | No heavy language model; never invent provenance |
| **P4** | **Target Intelligence recommendations**: rule-based opportunity screening, independent value/readiness explanations, hard gates, full target chooser and abstention; **no training until user selection** | Medium | Works on many representative datasets including no-valid-target cases |
| **P5** | **B2 minimal durable execution backbone**: canonical operation IDs, status/progress/persisted checkpoint and approval handoff for long runs, later extend retry/recovery; **resource-aware serialization/preflight of expensive tasks** | Medium–high | Needed *before* safely operating one-click Master workflows; build shared contracts once |
| **P6** | **Master Analyst v1 then Master Scientist v1**: orchestrate existing deterministic tools, auto-stage safe cleaning/EDA/report and target-selected ML, documented change approvals and human checkpoints | High | No new second analytical engine; end-to-end tests and high-risk refusal cases |
| **P7** | **Advanced B2 orchestration and B1 autonomous ODIN**: scheduling, load-shedding, crash-safe resume/cancel/repair; actual local language-model inference and secure multi-step tool planning/evidence | Very high | Highest application complexity; demonstrate real models and safety on Windows; plain rule-based functions remain available offline regardless of LLM |
| **P8 — Last** | **Integrated offline Windows 1.0 / Build F**: bundled Qwen/runtime/WebView2, clean offline install, memory/performance/security/privacy, migrations/rollback, accessibility and packaging | Very high | No premature installer; no release claims until mandatory Windows tests pass |

**Important sequencing nuance:** The expensive work and final packaging are late, but a small early **feasibility probe** must measure model/runtime availability, real offline constraints, approximate combined RAM and licensing. This is not the full AI implementation or a user installer. If infeasible, revisit the requirement **before** building late-stage dependencies. Also create only the essential B2 operation contracts before Master modes; reserve sophisticated recovery and scheduling for P7.

## Complexity and user-value rationale

- **Early P0–P2:** Existing features already deliver analyst value. Finishing and testing them is cheaper than starting new architecture, removes known defects and makes the product useful as a deterministic offline tool.
- **P3–P4:** Semantic/target intelligence can first be read-only and explainable, making it testable without training dozens of models or depending on uncertain local LLM performance.
- **P5–P6:** Automation is valuable but affects data versions and cross-workspace operations. Build one shared task/approval/evidence backbone so 'one click' doesn't become an untraceable sequence of hidden changes.
- **P7:** Real local-AI autonomy, planner/tool repair and resource-aware crash recovery are hard to validate and likely to create integration failures. Build after deterministic tools and safe orchestration are stable, with feasibility known.
- **P8:** Offline installer, bundled local AI, WebView2, 8 GB end-to-end performance, privacy, signing and updates form the last release gate, not a development milestone to repeatedly publish early.

### Resource-Aware Mode — owner-approved design direction (25 October 2026)

The owner agreed to the proposed **Adaptive / Low-memory / Performance** resource policies. Record these as a **staged feature, not shipped code**. P1 begins with truthful read-only available-RAM status and persisted user policy. P5 adds central heavy-operation preflight/serialization and durable cancellation/approval handoffs; P7 integrates actual lazy-loaded local AI only after the early E2 feasibility spike proves a licensed model/runtime can execute alongside PilotODIN on **real 8 GB-class Windows hardware**. Performance mode must never bypass hard integrity, privacy, import, ML split/leakage or memory safeguards. Never automatically kill unrelated apps, disable Windows memory protections or download AI models. Full contract and test criteria: [RESOURCE_AWARE_MODE_DESIGN.md](./RESOURCE_AWARE_MODE_DESIGN.md).

## Explicit decisions and scope discipline

- **Confirmed:** The user selects the supervised output/target after seeing PilotODIN's rankings, and may choose a lower-ranked eligible target.
- **Confirmed direction, policy details TBD:** Automatic Master workflows should minimise clicks while protecting immutable source data and escalating ambiguous/high-impact data edits.
- **Not approved yet:** Exact safe cleaning operation allowlist; target-ranking rubric; calibrations/thresholds; inferable business definitions; internal semantic model; cloud/LLM policy for private data.
- **Not proven:** True peak 8 GB RAM, complete offline Qwen inference, bundled installer, fully automated Master modes.
- **Deliberate non-goals for 1.0:** Multi-user enterprise collaboration, arbitrary untrusted plugin/code execution, full replacement of major BI platforms, unrestricted OS windows/infinite canvas and unsupported causal/accuracy claims.

## Continuity

Maintain:
- `docs/CONTINUE_HERE.md` — current turn handoff and actual test status.
- This feature inventory & roadmap — current priority and phased scope.
- `docs/MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md` and target intelligence deep research — research decisions vs open design.
- GitHub Issue #2 — dated QA/acceptance log. Never silently mark a planned feature as built.
- Original master reconstruction blueprint — product obligations/24 clean Windows acceptance scenarios.

**Latest next action is intentionally NOT defined in this historical roadmap.** Read [SESSION_HANDOFF_CURRENT.md](./SESSION_HANDOFF_CURRENT.md) for verified latest implementation, acceptance and one immediate next step. Master modes and target discovery remain planned/research-only; resource admission is newer P1 source and must be validated before scheduling or AI expansion. This roadmap records sequencing, not test certification.
