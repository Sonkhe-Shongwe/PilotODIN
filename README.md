# PilotODIN 1.0
**Local-first Windows data investigation, analytics and predictive modelling.**  
**Development status, 4 November 2026:** substantial working foundations; **P1 is the active OPEN phase**. PilotODIN 1.0 is **not a certified offline Windows release**.

PilotODIN combines a React/TypeScript workspace, a local FastAPI/SQLite analytical engine, and a Tauri desktop shell. The intended 1.0 vision includes versioned data-quality approval, evidence-backed investigation, model evaluation, reports and a bundled locally functioning ODIN assistant. **Implemented foundations do not prove all future autonomy or packaging requirements are finished.**

## Read this first
- **[Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)**: concise source SHA, verified CI and exactly one next task.
- **[P0–P8 development and release status](docs/PROJECT_STATUS_CURRENT.md)**: accepted development slices and remaining limitations.
- **[P1 acceptance/closure matrix](docs/P1_CLOSURE_REGISTER_2026-10-28.md)**: owner native checks, hosted evidence and outstanding gates.
- **[Phase policy](docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)**: owner-approved one-primary-phase and closure criteria.
- **[Full documentation index](docs/DOCUMENTATION_INDEX.md)** and **[4 November document audit](docs/DOCUMENTATION_AUDIT_2026-11-04.md)**.
- **[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)** for chronological issue/evidence discussion.

## Verified development evidence
The most recent P1 frontend workflow [#41802760086](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802760086) passed **130/130 Node tests**, the TypeScript/Vite build and **5/5** isolated Chromium scenarios. The production-code real-loopback HTTP workflow [#41802476525](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802476525) passed **1/1 integrated Chromium/Uvicorn scenario** using synthetic data. These do **not** establish a clean installed native Windows release or completed offline AI/8 GB feasibility.

Selected native Tauri DEV interactions and WIN-K1–K4 have scoped owner-reported PASS evidence; scaling, Snap, reduced motion, screen reader and final release gates remain open or deferred.

## Development and historical material
Use the [live development guide](docs/LIVE_DEVELOPMENT.md) only when appropriate to the current authorised phase and with **disposable test data**. Do not test destructive recovery against original projects, existing Quality history or external backups. Preserve untracked Tauri `Cargo.lock` and `gen/` work.

The original 22 October **Master Reconstruction Blueprint**, held by the owner as a DOCX, is the normative product specification unless explicitly amended. [Complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) is the intended sequence, not proof of shipped code. Older v0.x/Build A–E README paragraphs are [preserved verbatim in the audit archive](docs/archive/ROOT_README_PRE_AUDIT_2026-11-04.md) and are not current instructions.

**Repository licence/security:** No root `LICENSE` or `SECURITY.md` existed at this audit checkpoint. Their content requires an explicit owner decision; a public repository does not imply a particular licence or security certification.
