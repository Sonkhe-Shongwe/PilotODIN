# PilotODIN 1.0
**Local-first Windows data investigation, analytics and predictive modelling.**  
**Development status, 15 November 2026.** P1, P2 and P3 have bounded development closure records. **P4 Target Intelligence is active.** The [current phase ledger](docs/PROJECT_STATUS_CURRENT.md) tracks Windows acceptance, physical offline inference, preservation and owner signoff. P5 is unauthorised and P8 release certification is pending.

PilotODIN combines a React/TypeScript workspace, a local FastAPI/SQLite analytical engine, and a Tauri desktop shell. The intended 1.0 vision includes versioned data-quality approval, evidence-backed investigation, model evaluation, reports and a bundled locally functioning ODIN assistant. **Implemented foundations do not prove all future autonomy or packaging requirements are finished.**

## Read this first
- **[Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)** for the latest verified change and next task.
- **[P0–P8 development and release status](docs/PROJECT_STATUS_CURRENT.md)**: accepted development slices and remaining limitations.
- **[P4 acceptance worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md)** for gate status and Windows evidence. **[N12 runbook](qa/p4_native/N12_TRACE.md)** for the next Windows check.
- **[P1 prior-phase closure matrix](docs/P1_CLOSURE_REGISTER_2026-10-28.md)**: dated historical P1 acceptance.
- **[Phase policy](docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)**: owner-approved one-primary-phase and closure criteria.
- **[Documentation index](docs/DOCUMENTATION_INDEX.md)** for current references and historical audits.
- **[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)** for chronological issue/evidence discussion.

## Verified development evidence
[P4 source CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43672531160) passed Python, Node, TypeScript/Vite, real-HTTP browser tests and Windows fixture checks at `8f57d22`. The [separate live collector rehearsal](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43672824700/job/132686419880) passed Sysmon prelaunch and reached the combined audit. Unresolved ETW background mutations blocked strict coverage. [Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)

Hosted Windows passed the scoped [R04 docking retest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) and [R05 fitted Prepare acceptance](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43439284563). See the [P4 worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) for the tested source and evidence limits.

## Development and historical material
Use the [live development guide](docs/LIVE_DEVELOPMENT.md) only when appropriate to the current authorised phase and with **disposable test data**. Do not test destructive recovery against original projects, existing Quality history or external backups. Preserve untracked Tauri `Cargo.lock` and `gen/` work.

The original 22 October **Master Reconstruction Blueprint**, held by the owner as a DOCX, is the normative product specification unless explicitly amended. [Complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) is the intended sequence, not proof of shipped code. Older v0.x/Build A–E README paragraphs are [preserved verbatim in the audit archive](docs/archive/ROOT_README_PRE_AUDIT_2026-11-04.md) and are not current instructions.

**Repository licence/security:** No root `LICENSE` or `SECURITY.md` existed at this audit checkpoint. Their content requires an explicit owner decision; a public repository does not imply a particular licence or security certification.
