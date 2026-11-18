# PilotODIN 1.0
**Local-first Windows data investigation, analytics and predictive modelling.**  
**Development status, 17 November 2026.** P1, P2 and P3 have bounded development closure records. **P4 Target Intelligence is active at 14 of 20 engineering checks (70%).** The [scorecard](docs/PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) records evidence and points for each check. P5 is unauthorised and P8 release certification is pending.

PilotODIN combines a React/TypeScript workspace, a local FastAPI/SQLite analytical engine, and a Tauri desktop shell. The intended 1.0 vision includes versioned data-quality approval, evidence-backed investigation, model evaluation, reports and a bundled locally functioning ODIN assistant. **Implemented foundations do not prove all future autonomy or packaging requirements are finished.**

## Read this first
- **[Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)** for the latest verified change and next task.
- **[P0–P8 development and release status](docs/PROJECT_STATUS_CURRENT.md)**: accepted development slices and remaining limitations.
- **[P4 acceptance worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md)** for gate status and Windows evidence. **[N12 runbook](qa/p4_native/N12_TRACE.md)** for the collector and trace procedure.
- **[Local analytics implementation plan and acceptance evidence](docs/P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md)** for the Ask ODIN milestone and remaining resource checks.
- **[Whole-app RAM range and measurements](docs/RESOURCE_AWARE_MODE_DESIGN.md#everyday-ram-range-and-system-headroom)** for the roughly 1–3 GiB planning range and physical laptop results.
- **[P1 prior-phase closure matrix](docs/P1_CLOSURE_REGISTER_2026-10-28.md)**: dated historical P1 acceptance.
- **[Phase policy](docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)**: owner-approved one-primary-phase and closure criteria.
- **[Documentation index](docs/DOCUMENTATION_INDEX.md)** for current references and historical audits.
- **[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)** for chronological issue/evidence discussion.

## Verified development evidence
All four [routine P4 CI jobs](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44106241787) passed at `0a5376c`. The latest [completed hosted N12 audit](docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--hosted-webview-path-audit) ran both launches and matched protected endpoint snapshots. It recorded six unexpected connections and 69 outside-scope file operations. Both acceptance checks failed, and strict trace coverage remains blocked.

The owner accepted two [native Ask ODIN Local analytics interactions](docs/SESSION_HANDOFF_CURRENT.md#16-november-2026--native-local-analytics-answers-accepted) on the physical 8 GB laptop. The [1.50 GiB QA attempt](docs/SESSION_HANDOFF_CURRENT.md#17-november-2026--physical-r03-candidate-deferred) deferred Qwen and returned verified local rules. Physical offline generation, coexistence and the proposed everyday-memory target remain unverified.

Hosted Windows passed the scoped [R04 docking retest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) and [R05 fitted Prepare acceptance](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43439284563). See the [P4 worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) for the tested source and evidence limits.

## Development and historical material
Use the [live development guide](docs/LIVE_DEVELOPMENT.md) only when appropriate to the current authorised phase and with **disposable test data**. Do not test destructive recovery against original projects, existing Quality history or external backups. Preserve untracked Tauri `Cargo.lock` and `gen/` work.

The original 22 October **Master Reconstruction Blueprint**, held by the owner as a DOCX, is the normative product specification unless explicitly amended. [Complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) is the intended sequence, not proof of shipped code. Older v0.x/Build A–E README paragraphs are [preserved verbatim in the audit archive](docs/archive/ROOT_README_PRE_AUDIT_2026-11-04.md) and are not current instructions.

**Repository licence/security:** No root `LICENSE` or `SECURITY.md` existed at this audit checkpoint. Their content requires an explicit owner decision; a public repository does not imply a particular licence or security certification.
