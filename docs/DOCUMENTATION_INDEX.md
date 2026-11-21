# PilotODIN | Documentation index

**21 November 2026 | Clean authoritative route.** **One active direction:** independently establish a Stage 1 *correctness and evidence contract*, construct an honest partial golden reference, derive passing and adversarial test variations, then compare source code and collector behavior against real Windows evidence. **This audit is documentation-only, not a change of native acceptance, permissions or P4 points.**

## Current authoritative route, in reading order

1. **[Stage 1 golden-reference contract and backward test matrix](./P4_N12_STAGE1_GOLDEN_REFERENCE_AND_BACKWARD_VERIFICATION_2026-11-21.md)**: the agreed direction, independent invariants, reference evidence, traceability, test matrix and permission boundaries.
2. **[Session handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action)**: one active next engineering action, exact source CI and blockers. Historic snapshots no longer appear as competing directions.
3. **[Project status and 20-check P4 scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard)**: source of truth for official progress, acceptance and phase state.
4. **[P4 acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md#six-open-engineering-checks-and-the-next-evidence-passes)** and [N12 trace runbook](../qa/p4_native/N12_TRACE.md): unchanged technical acceptance and evidence intake, including R02.5/R02.6 and the other four open checks.
5. **[Phase focus and closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)**: one active phase, owner decisions, one-use approvals and installer freeze.
6. **[Document-direction audit](./DOCUMENTATION_DIRECTION_AUDIT_GOLDEN_REFERENCE_2026-11-21.md)**: cleanup scope, authority conflicts, preserved archive and verification limits.
7. [Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) · [P4 owner evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) · [Local analytics plan](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md) · [8 GB RAM resource evidence](./RESOURCE_AWARE_MODE_DESIGN.md#everyday-ram-range-and-system-headroom).

## Current development references

- **[New current partial real-observation Stage 1 reference and backward counterexample](./P4_N12_STAGE1_PARTIAL_REFERENCE_AND_COUNTEREXAMPLES_2026-11-21.md)**: redacted actual app/launcher handle and ETW measurements, seven explicitly missing WebView original handles, executable synthetic early-born retained-child and role-mix variants. [source `6b04a37e`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6b04a37e3868522697ee88c0699f0ce4348cace1); [routine CI #44913993754](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44913993754) (check exact-source outcome before credit). Native Stage 1 remains BLOCKED and no strict reducer predicate was changed.

- **[Latest S01-S11 source-verified Stage 1 reference evidence worksheet](./P4_N12_STAGE1_SOURCE_EVIDENCE_WORKSHEET_2026-11-21.md)**, [machine-readable JSON mapping](./P4_N12_STAGE1_SOURCE_EVIDENCE_MAP_2026-11-21.json): independent actual app/launcher partial reference, precise original-handle/ETW/SystemMonitor checks, existing fixture names, and three source-level assumptions requiring controlled counterexamples. [Exact CI #44912012772](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44912012772) 4/4; source traceability only, no native acceptance.

- **Real last approved native Stage 1 (failure, not pass):** [Sysmon/ETW exact exit timestamp mismatch #44893498723](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md); app/launcher independent original-handle agreement, seven WebView2 children without retained original handles, prior approval consumed.
- **Newest source-only/synthetic transport:** [real Windows AF_PIPE using synthetic subprocesses, interrupted-observer cleanup](./P4_N12_SYNTHETIC_WINDOWS_PIPE_AND_ABORT_SOURCE_REVIEW_2026-11-21.md); [exact CI #44903523887](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44903523887) **4/4 PASS** at `0511aca`, no native PilotODIN/WebView2 execution.
- **Diagnostic-only prior contracts:** [original child-handle observer](./P4_N12_NO_CDP_SCOPED_CHILD_HANDLE_OBSERVER_SOURCE_REVIEW_2026-11-21.md), [private reducer handoff](./P4_N12_NO_CDP_PRIVATE_CHILD_HANDLE_REDUCER_HANDOFF_2026-11-21.md), [authenticated private transport](./P4_N12_PRIVATE_CHILD_HANDLE_MEMORY_PIPE_TRANSFER_2026-11-21.md), [original-handle shadow design](./P4_N12_STAGE1_SHADOW_HANDLE_WITNESS_DESIGN_2026-11-21.md). These do not amend strict native acceptance.
- **R02.5/R02.6 downstream evidence:** [full native failure and FileIO path credit reconciliation](./P4_R02_5_FILE_MUTATION_CREDIT_RECONCILIATION_2026-11-21.md), [file-mutation evidence architecture](./P4_N12_FILE_MUTATION_EVIDENCE_DECISION_2026-11-21.md), [product worker TEMP correction](./P4_R02_5_PRODUCT_WORKER_TEMP_CONTAINMENT_2026-11-21.md). No full N12 pass.
- **Full historical technical-notes directory:** [preserved as one dated reading list and progress archive](./P4_ENTRYPOINT_PROGRESS_CHRONOLOGY_ARCHIVE_2026-11-21.md#d-original-documentation-index-development-references-retained-for-lookup). Original individual technical reports remain in place and retain their original URLs and commit/run provenance.

## Historical navigation

- [Complete pre-cleanup handoff](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/6e5bd7d1f01df28151ba3b97dcd82f0a941f9363/docs/SESSION_HANDOFF_CURRENT.md) with original November 15–18 run outcomes and provenance.
- [Complete pre-audit documentation index](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/DOCUMENTATION_INDEX.md), including prior evidence links and legacy navigation from 4 November.
- [Pre-audit handoff](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/SESSION_HANDOFF_CURRENT.md) and [pre-audit phase chronology](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/07dbaa749fea9bf90bf4debf534246f875132395/docs/PROJECT_STATUS_CURRENT.md), with the original section links and evidence text.
- [15 November repository documentation audit](./DOCUMENTATION_AUDIT_2026-11-15.md), the [4 November](./DOCUMENTATION_AUDIT_2026-11-04.md) and [12 November](./DOCUMENTATION_CLEANING_AUDIT_2026-11-12.md) audits, and the [verbatim archive files](./archive). The archive files preserve original relative links, which may require the original repository layout.
- [Documentation audit after the Local analytics decision](./DOCUMENTATION_AUDIT_LOCAL_ANALYTICS_2026-11-15.md) records the source inventory, link check and current guidance corrections.

<a name="current-phase-evidence-and-recent-checkpoints"></a>
<a name="historical-navigation-snapshot-4-november-2026-retained-for-traceability"></a>
<a name="current-status-and-governance"></a>
<a name="dated-project-history-and-prior-entry-points"></a>
<a name="p0-and-p1-acceptance--dev-evidence"></a>
<a name="p2-deliver-pdf-and-reporting-acceptance"></a>
<a name="p3p5-focused-intelligence--task-acceptance"></a>
<a name="research-design-operations-and-legacy-releases"></a>
<a name="preserved-verbatim-audit-baseline-logs"></a>
