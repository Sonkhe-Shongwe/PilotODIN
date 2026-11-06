# PilotODIN: Design decisions

> **Historical first-release specification.** Some first-release boundaries below (such as requiring manual target selection and lacking AI) record an earlier iteration. Do not treat them as the current approved end-state. The living [development handoff](./CONTINUE_HERE.md) and **research-only** [Master modes / target-discovery proposal](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md) describe the current October 2026 direction. Their proposed autonomy capabilities are **not yet implemented**.

## Goal

An intelligent data science workspace that can ingest data, interpret its structure, suggest analysis paths, prepare features, compare several valid ML candidates, and expose the selected saved pipeline through a prediction form.

## First-release boundaries

- The first release uses **deterministic rules** for profiling and candidate target detection.
- No LLM is connected and no external data is uploaded to AI vendors.
- This is a **single-user local development application**, not a secure hosted service.
- All preprocessing learned from data is fitted within each training fold.
- The user chooses the target and reviews feature exclusions.
- The user confirms random splitting is valid for their data, rather than allowing the tool to guess about time or group structure.
- The selected model is evaluated once on the held-out test set; an experiment locks this choice.

## AI provider contract for a future release

- The back-end gathers only verified data summaries, column-level statistics, target candidates, and an explicit user question.
- The provider receives these **only after opt-in** and should avoid including sensitive raw rows or personal identifiers.
- AI replies are structured and schema-validated. Suggestions require confirmation before execution.
- Reject any proposed AI action that references unknown columns, unsupported operations or unverified metrics.
- If a provider is not configured, the app works using its deterministic profiling engine.
- Never execute Python or shell code emitted by an LLM or included in uploaded datasets.

## Planned AI tools

- `profile_dataset(project_id)`: read-only verified statistics
- `suggest_targets(project_id)`: candidate target columns and uncertainty
- `propose_preparation(project_id,target)`: reviewable transformations; no auto-execution
- `read_experiment_results(experiment_id)`: verified metrics only
- `explain_findings(project_id,experiment_id)`: language-only explanation with citations to computed facts

## REST API

- `GET /api/health`: basic health and whether cloud AI is active
- `GET /api/projects`: project list
- `POST /api/projects`: multipart dataset upload (creates project)
- `GET /api/projects/{project_id}`: project and original profile
- `GET /api/projects/{project_id}/preparation?target=...`: validated plan suggestions
- `POST /api/projects/{project_id}/experiments`: asynchronous training
- `GET /api/experiments/{id}`: job status, scores and selected model
- `POST /api/experiments/{id}/select`: select model + final test evaluation
- `POST /api/experiments/{id}/predict`: prediction via saved pipeline

## Future state versioning

Project-level preparation and target versioning should be added before editable historical experiments are supported. This MVP preserves immutable experiment configs; the user can create a new experiment for changed features.
