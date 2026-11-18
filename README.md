# PilotODIN 1.0
**Local-first Windows data investigation, analytics and predictive modelling.**  
**Development status, 18 November 2026.** P1, P2 and P3 have bounded development closure records. **P4 Target Intelligence is active at 14 of 20 engineering checks (70%).** P5 is unauthorised and P8 release certification is pending. [Engineering scorecard](docs/PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard)

PilotODIN combines a React/TypeScript workspace, a local FastAPI/SQLite analytical engine, and a Tauri desktop shell. The 1.0 roadmap covers versioned data-quality approval, evidence-backed investigation, model evaluation, reports and a bundled local ODIN assistant. [Roadmap and scope](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md)

## Read this first
- **[Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)** for the latest verified change and next task.
- **[P0–P8 development and release status](docs/PROJECT_STATUS_CURRENT.md)** for accepted development slices and remaining limits.
- **[P4 acceptance worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md)** for gate status and Windows evidence. **[N12 runbook](qa/p4_native/N12_TRACE.md)** for the collector and trace procedure.
- **[Local analytics implementation plan and acceptance evidence](docs/P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md)** for the Ask ODIN milestone and remaining resource checks.
- **[Whole-app RAM range and measurements](docs/RESOURCE_AWARE_MODE_DESIGN.md#everyday-ram-range-and-system-headroom)** for the roughly 1–3 GiB planning range and physical laptop results.
- **[Phase policy](docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)** for the installer freeze, owner approvals and closure criteria.
- **[Documentation index](docs/DOCUMENTATION_INDEX.md)** for current references and historical audits.
- **[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)** for chronological issue/evidence discussion.

## Verified development evidence
All four routine P4 jobs passed at `8d18c8e`, and the Windows FileIO integration job passed at `6e5bd7d`. The latest N12 app audit matched protected endpoint snapshots and reduced unresolved WebView network-process write paths from 199,409 to 141 in a strict comparison. The ordinary audit still reported eight unexpected connections, 69 outside-scope file operations and blocked coverage. [Routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44357423097) · [Windows FileIO CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44341573377) · [N12 evidence](docs/SESSION_HANDOFF_CURRENT.md#windows-audit-evidence)

The owner accepted two native Ask ODIN Local analytics interactions on the physical 8 GB laptop. An updated walkthrough completed with a verified HTML export and a **735.27 MiB sampled combined working-set peak** on that workload. The 1.50 GiB QA attempt deferred Qwen and returned local rules. Physical offline bundled generation and coexistence remain open. [Physical Windows evidence](docs/SESSION_HANDOFF_CURRENT.md#physical-windows-evidence)

Hosted Windows passed the scoped [R04 docking retest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) and [R05 fitted Prepare acceptance](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43439284563). See the [P4 worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) for the tested source and evidence limits.

## Development and historical material
Use the [live development guide](docs/LIVE_DEVELOPMENT.md) only when appropriate to the current authorised phase and with **disposable test data**. Do not test destructive recovery against original projects, existing Quality history or external backups. Preserve untracked Tauri `Cargo.lock` and `gen/` work.

The original 22 October **Master Reconstruction Blueprint**, held by the owner as a DOCX, is the normative product specification unless explicitly amended. [Complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) is the intended sequence, not proof of shipped code. Older v0.x/Build A–E README paragraphs are [preserved verbatim in the audit archive](docs/archive/ROOT_README_PRE_AUDIT_2026-11-04.md) and are not current instructions.

**Repository licence/security:** No root `LICENSE` or `SECURITY.md` existed at this audit checkpoint. Their content requires an explicit owner decision; a public repository does not imply a particular licence or security certification.
