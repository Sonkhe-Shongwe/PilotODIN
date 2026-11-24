# PilotODIN 1.0

**CURRENT | Live reference.** Consult the [current handoff](docs/TAB_MIGRATION_HANDOFF_CURRENT.md) for changing source status and next action, and the [official scorecard](docs/PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) for acceptance. [Continuation protocol](docs/CONTINUATION_PROTOCOL_CURRENT.md). Historical evidence below is not a current work order.

**Resume development:** [Current migration handoff](docs/TAB_MIGRATION_HANDOFF_CURRENT.md) | [Live directive](docs/PILOTODIN_PRODUCT_FIRST_IMPLEMENTATION_DIRECTIVE_CURRENT.md) | [Current documentation audit](docs/DOCUMENTATION_AUDIT_B5_CONTINUITY_2026-11-24.md).

**Local-first Windows data investigation, analytics and predictive modelling.**  
**Development status.** P1, P2 and P3 have bounded development closure records. **P4 Target Intelligence is active.** P5 is unauthorised and P8 release certification is pending. [Current engineering scorecard](docs/PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard)

PilotODIN combines a React/TypeScript workspace, a local FastAPI/SQLite analytical engine, and a Tauri desktop shell. The 1.0 roadmap covers versioned data-quality approval, evidence-backed investigation, model evaluation, reports and a bundled local ODIN assistant. [Roadmap and scope](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md)

## Read this first
- **[Current product-first implementation directive](docs/PILOTODIN_PRODUCT_FIRST_IMPLEMENTATION_DIRECTIVE_CURRENT.md)**: sole live work order, fixed A–D scope, readiness specification and permissions.
- **[Active Package B specification](docs/PILOTODIN_PACKAGE_B_DURABLE_DATA_INTEGRITY_SPEC_2026-11-24.md)**: durable-data scope and exit criteria; live completion state is in the handoff.
- **[24 November migration audit](docs/DOCUMENTATION_AUDIT_B4_MIGRATION_2026-11-24.md)**: current authority, evidence and historical preservation.
- **[Current tab migration handoff](docs/TAB_MIGRATION_HANDOFF_CURRENT.md)**: single starting point, latest evidence, exact next action, safe scope and source references.
- **[Stage 1 golden-reference verification contract](docs/P4_N12_STAGE1_GOLDEN_REFERENCE_AND_BACKWARD_VERIFICATION_2026-11-21.md)** for retained native evidence requirements, not the current development sequence.
- **[Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)** for current product-first next action and historical engineering chronology.
- **[21 November documentation-direction audit](docs/DOCUMENTATION_DIRECTION_AUDIT_GOLDEN_REFERENCE_2026-11-21.md)** for the changes, preserved chronology and unresolved evidence.
- **[P0–P8 development and release status](docs/PROJECT_STATUS_CURRENT.md)** for accepted development slices and remaining limits.
- **[P4 acceptance worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md)** for gate status and Windows evidence. **[N12 runbook](qa/p4_native/N12_TRACE.md)** for the collector and trace procedure.
- **[Local analytics implementation plan and acceptance evidence](docs/P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md)** for the Ask ODIN milestone and remaining resource checks.
- **[Whole-app RAM range and measurements](docs/RESOURCE_AWARE_MODE_DESIGN.md#everyday-ram-range-and-system-headroom)** for the roughly 1–3 GiB planning range and physical laptop results.
- **[Phase policy](docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)** for the installer freeze, owner approvals and closure criteria.
- **[Documentation index](docs/DOCUMENTATION_INDEX.md)** for current references and historical audits.
- **[21 November documentation and direction audit](docs/DOCUMENTATION_AUDIT_2026-11-21.md)** for verified current instructions, prior-status corrections and remaining evidence gates.
- **[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)** for chronological issue/evidence discussion.

## Verified development evidence

**Current product identity and verification:** [Live migration handoff](docs/TAB_MIGRATION_HANDOFF_CURRENT.md) and its linked active package evidence ledger. Exact-source receipts are not repeated in this README.

**Historical Package A source/integration baseline:** `60041f144a29e0c18db9c8ad1b9e07651309c7d9`: eight source workflows passed, including [P4 regression](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45378250732). [One-time locked Windows host check](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45380098568) passed; [retired workflow](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45382351664) skipped. This closes Package A at source level, not native runtime acceptance.
**Latest actual native evidence baseline, 24 November:** [G2.20 source CI #45341086645](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45341086645) passed at `8c2d456a1978145d10af1da86caf97053b07a1b3`. A subsequent [one-use actual Windows diagnostic #45342345634](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45342345634) built, started and closed the isolated app, verified both calibration bookends and write/restore, reported zero lost events/buffers, and returned BLOCKED evidence: 23 prohibited operations, 4,921 unresolved mutation credits (125 network write-path gaps); 102 bounded lexical outside-scope candidates without original-file-handle/physical destination credit. Original process identity and private child inventory remain blocked. [Full result](docs/P4_R02_5_G2_20_INTEGRATED_PASSIVE_FILEIO_PATH_DIAGNOSTIC_2026-11-24.md). The earlier [complete N12 journey #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) still governs official filesystem FAIL, network FAIL and mutation coverage BLOCKED. Neither endpoint matches nor this scoped diagnostic close acceptance. File-mutation workstream 3/4; official P4 14/20 (70%). Native workflows disarmed; the latest consent is consumed.

**Earlier evidence (historical, not the current native baseline):** The 19 November N12 run at `cd9b397` matched protected endpoints but failed filesystem/network checks with coverage blocked. Its staged egress comparison passed routine source CI separately. [19 November app audit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44440131278/job/135278609026) · [historical P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44482975206).

The owner accepted two native Ask ODIN Local analytics interactions on the physical 8 GB laptop. An updated walkthrough completed with a verified HTML export and a **735.27 MiB sampled combined working-set peak** on that workload. The 1.50 GiB QA attempt deferred Qwen and returned local rules. Physical offline bundled generation and coexistence remain open. [Physical Windows evidence](docs/SESSION_HANDOFF_CURRENT.md#physical-windows-evidence)

Hosted Windows passed the scoped [R04 docking retest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) and [R05 fitted Prepare acceptance](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43439284563). See the [P4 worklist](docs/P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) for the tested source and evidence limits.

## Development and historical material
Use the [live development guide](docs/LIVE_DEVELOPMENT.md) only when appropriate to the current authorised phase and with **disposable test data**. Do not test destructive recovery against original projects, existing Quality history or external backups. The published Tauri `Cargo.lock` is tracked and verified; preserve it and any unpublished owner-side `gen/` work. Do not overwrite local unpublished work.

The original 22 October **Master Reconstruction Blueprint**, held by the owner as a DOCX, is the normative product specification unless explicitly amended. [Complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) is the intended sequence, not proof of shipped code. Older v0.x/Build A–E README paragraphs are [preserved verbatim in the audit archive](docs/archive/ROOT_README_PRE_AUDIT_2026-11-04.md) and are not current instructions.

**Repository licence/security:** No root `LICENSE` or `SECURITY.md` existed at this audit checkpoint. Their content requires an explicit owner decision; a public repository does not imply a particular licence or security certification.
