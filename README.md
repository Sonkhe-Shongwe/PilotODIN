# PilotODIN 1.0
**Local-first Windows data investigation, analytics and predictive modelling.**  
**Development status, 12 November 2026:** P1, P2 and P3 have scoped bounded-development closure records; **P4 Target Intelligence is ACTIVE, P4-R01–R06 remain OPEN**. Real-world business Gate C and original whole-app-data strict preservation are unresolved; **P5 NOT AUTHORISED**, and PilotODIN 1.0 is **not a certified offline Windows release**. For later changes consult the [live handoff](docs/SESSION_HANDOFF_CURRENT.md).

PilotODIN combines a React/TypeScript workspace, a local FastAPI/SQLite analytical engine, and a Tauri desktop shell. The intended 1.0 vision includes versioned data-quality approval, evidence-backed investigation, model evaluation, reports and a bundled locally functioning ODIN assistant. **Implemented foundations do not prove all future autonomy or packaging requirements are finished.**

## Read this first
- **[Current engineering checkpoint](docs/SESSION_HANDOFF_CURRENT.md)**: concise source SHA, verified CI and exactly one next task.
- **[P0–P8 development and release status](docs/PROJECT_STATUS_CURRENT.md)**: accepted development slices and remaining limitations.
- **[P4 owner acceptance go/no-go](docs/P4_23_CONSOLIDATED_WINDOWS_ACCEPTANCE_GO_NO_GO_2026-11-09.md)**: current open gates, owner Windows evidence and source-only boundaries.
- **[P1 prior-phase closure matrix](docs/P1_CLOSURE_REGISTER_2026-10-28.md)**: dated historical P1 acceptance.
- **[Phase policy](docs/PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)**: owner-approved one-primary-phase and closure criteria.
- **[Current documentation index](docs/DOCUMENTATION_INDEX.md)** and **[12 November navigation cleaning audit](docs/DOCUMENTATION_CLEANING_AUDIT_2026-11-12.md)**; [4 November audit](docs/DOCUMENTATION_AUDIT_2026-11-04.md) is historical.
- **[Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2)** for chronological issue/evidence discussion.

## Verified development evidence
The previous P1 verification [#41802760086](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802760086) and real-loopback browser [#41802476525](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802476525) are **historical**, not current-HEAD acceptance. A later P4 source CI [#43192250027](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43192250027), at **`5f1144ad`**, recorded 169 Python, 45 Node, TypeScript/Vite, 9 disposable Chromium and synthetic Windows integrity checks passing. Subsequent P4-57/P4-58 development documented 16 local synthetic validator tests; no fresh source-matched full application CI is claimed for those later changes.

Native Tauri and current UI, sustained offline 8 GB Qwen, real-business Gate C, and original whole app-local-data acceptance remain unresolved. GitHub CI results are not owner Windows release certification.

## Development and historical material
Use the [live development guide](docs/LIVE_DEVELOPMENT.md) only when appropriate to the current authorised phase and with **disposable test data**. Do not test destructive recovery against original projects, existing Quality history or external backups. Preserve untracked Tauri `Cargo.lock` and `gen/` work.

The original 22 October **Master Reconstruction Blueprint**, held by the owner as a DOCX, is the normative product specification unless explicitly amended. [Complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) is the intended sequence, not proof of shipped code. Older v0.x/Build A–E README paragraphs are [preserved verbatim in the audit archive](docs/archive/ROOT_README_PRE_AUDIT_2026-11-04.md) and are not current instructions.

**Repository licence/security:** No root `LICENSE` or `SECURITY.md` existed at this audit checkpoint. Their content requires an explicit owner decision; a public repository does not imply a particular licence or security certification.
