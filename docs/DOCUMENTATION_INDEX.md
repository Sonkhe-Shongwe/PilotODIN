# PilotODIN | Documentation index

**21 November 2026 navigation rule:** The handoff determines the next action, the project status owns the official score, the acceptance worklist owns check requirements, and the dated technical notes provide evidence only at their tested scope. [Documentation and direction audit](./DOCUMENTATION_AUDIT_2026-11-21.md). Older proposals below remain historical, not new permissions.

## Current authoritative route, in reading order

1. [Session handoff](./SESSION_HANDOFF_CURRENT.md) for the active branch, exact-source evidence and next engineering action.
2. [Project status](./PROJECT_STATUS_CURRENT.md) for the phase ledger and release disposition. The [P4 engineering scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) shows the evidence and points per check.
3. [Phase focus and closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) for owner decisions, the installer freeze and phase boundaries.
4. [P4 acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md) for the technical gate details and owner evidence. [N12 trace runbook](../qa/p4_native/N12_TRACE.md) for the collector and audit procedure.
5. [Master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) and [P4 owner evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) for dated issue and acceptance evidence.
6. [P4 Local analytics implementation plan](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md) for the agreed Ask ODIN milestone and its acceptance checks.
7. [Whole-app RAM range and measurements](./RESOURCE_AWARE_MODE_DESIGN.md#everyday-ram-range-and-system-headroom) for the owner-approved planning range, completed samples and next measurement.

## Current development references

- [Latest authenticated memory-only child-handle worker/reducer transport](./P4_N12_PRIVATE_CHILD_HANDLE_MEMORY_PIPE_TRANSFER_2026-11-21.md) records opt-in Windows named-pipe scope, private source-validated single-frame transfer, credential isolation, exact CI, and the remaining untested native child sampling and acceptance boundary.

- [Latest source-only private original WebView child-handle reducer handoff](./P4_N12_NO_CDP_PRIVATE_CHILD_HANDLE_REDUCER_HANDOFF_2026-11-21.md) documents an in-memory source/binary-pinned observer-to-reducer diagnostic interface, fixed-label privacy protection, capture-stage negative tests, unchanged native verdict and outstanding worker transport boundary.

- [Latest source-only guarded QA WebView child-handle observer and shadow Sysmon/ETW join](./P4_N12_NO_CDP_SCOPED_CHILD_HANDLE_OBSERVER_SOURCE_REVIEW_2026-11-21.md) details new source module, separate hosted consent, incomplete 10ms polling coverage, duplicate/PID reuse negatives, 4/4 synthetic CI and next integration boundary.

- [Stage 1 source-only original Windows handle witness shadow review](./P4_N12_STAGE1_SHADOW_HANDLE_WITNESS_DESIGN_2026-11-21.md) records the unchanged strict predicate, synthetic per-process handle-witness alternative, unresolved seven child handles, existing 10 ms Windows collector constraints and next source-only implementation boundary.

- [Latest Stage 1 actual native per-clause Sysmon/ETW exit diagnosis](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md) documents owner-approved #44893498723, sole exact exit timestamp equality failure across nine lifetimes, precise signed app/launcher clock differences, original handle corroboration, consumed one-use permission and source-only next review.

- [Newest source-only per-clause Sysmon/ETW lifetime diagnostic](./P4_N12_STAGE1_SYSMON_PER_CLAUSE_DIAGNOSTIC_2026-11-21.md) describes fixed failure categories, privacy-safe relative clock deltas, source CI 4/4, and next one-use native approval boundary, with no acceptance credit.

- [Latest Stage 1 native no-CDP retest, STRICT BLOCKED](./P4_N12_STAGE1_NATIVE_NO_CDP_RETEST_RESULT_44890538700.md) records run #44890538700, compiled source/binary identity, matched handles/ETW and snapshots, new combined Sysmon blocker, consumed one-use workflow and the next source-only diagnostic.

- [Stage 1 ETW header/payload and Sysmon lifetime corroboration](./P4_N12_STAGE1_ETW_HEADER_PAYLOAD_CORROBORATION_2026-11-21.md) documents source-only default-preserving diagnostics, the pre-spawn birth fix, exact CI and next separate native gate.

- [Stage 1 actual no-CDP hosted-Windows result, BLOCKED](./P4_N12_STAGE1_HOSTED_NO_CDP_NATIVE_RESULT_2026-11-21.md) for source-pinned Rust/Tauri compile, native startup/close, protected endpoint match, exact observed ETW header/payload timing conflicts, disarmed one-use activation and unchanged R02.5/P4 verdict.

- [Stage 1 no-CDP collector entrypoint](./P4_N12_STAGE1_NO_CDP_COLLECTOR_ENTRYPOINT_2026-11-21.md) for the bounded one-use native lifetime/profile launch entrypoint, required consents and source/non-native boundary.

- [21 November no-CDP final launch scope guard](./P4_N12_NO_CDP_FINAL_LAUNCH_SCOPE_GUARD_2026-11-21.md) for source-only prevention of direct-call WebView/temp/root bypass, generated negative tests and the precise next native approval boundary.
- [21 November documentation and direction audit](./DOCUMENTATION_AUDIT_2026-11-21.md) for the current source/native truth table, corrected README/worklist/runbook route, verified links and next approval boundary.
- [20 November code, test and direction audit](./PILOTODIN_P4_CODE_AND_TEST_AUDIT_2026-11-20.md) for reproduced product defects, the scope of the Windows failures and the corrective order.
- [Guarded no-CDP native QA lifecycle integration](./P4_N12_NO_CDP_NATIVE_LIFECYCLE_INTEGRATION_2026-11-21.md) for source-wired debugger-free startup/normal close and OS browser profile-verification, explicitly not FileIO acceptance.
- [Focused WebView storage backend-temp parity and causal boundary](./P4_N12_FOCUSED_BACKEND_TEMP_AND_WEBVIEW_CAUSAL_BOUNDARY_2026-11-21.md) covers source correction, original temp observations, and no-CDP experiment limits.
- [Product worker temp containment](./P4_R02_5_PRODUCT_WORKER_TEMP_CONTAINMENT_2026-11-21.md) documents real Rust child-process temporary-file redirection, N12 QA parity and held native acceptance.
- [Opt-in QA WebView2 ambient local-data candidate](./P4_N12_QA_AMBIENT_LOCAL_REDIRECT_CANDIDATE_2026-11-21.md) for source-only LOCALAPPDATA and APPDATA redirects inside the permitted disposable QA profile, not native acceptance.
- [R02.5 mutation gaps reconciled from original native log](./P4_R02_5_FILE_MUTATION_CREDIT_RECONCILIATION_2026-11-21.md) for 227,087 write path original gaps, 226,959 permitted path credits, 113 outside-scope credits and outstanding real blockers.
- [N12 file-mutation evidence architecture decision](./P4_N12_FILE_MUTATION_EVIDENCE_DECISION_2026-11-21.md) for why the current ProcMon A/B proof gate cannot qualify, and the planned independent prevention + preservation + ETW measurement approach.
- [N12 two-root protected fixture contract](./P4_N12_PROTECTED_FIXTURE_CONTRACT_2026-11-21.md) for the restricted-writer prevention design and source-only non-acceptance evidence-schema checks.
- [N12 restricted-token capability preflight](./P4_N12_RESTRICTED_TOKEN_CAPABILITY_PREFLIGHT_2026-11-21.md) for read-only Windows API export checks and the distinction between a generated writer fixture and real PilotODIN process confinement.
- [N12 process-boundary applicability review](./P4_N12_PROCESS_BOUNDARY_APPLICABILITY_REVIEW_2026-11-21.md) for the source-grounded Tauri/WebView2/backend execution map, rejected app-wide token approach and selected runtime-specific next action.
- [N12 production-versus-QA WebView startup and ambient-temp audit](./P4_N12_WEBVIEW_STARTUP_AND_AMBIENT_TEMP_AUDIT_2026-11-21.md) for the two observed temporary creates, safe cross-stage path correlation and the bounded UDP calibration-fixture correction.
- [N12 no-CDP close-readiness source design](./P4_N12_NO_CDP_CLOSE_READINESS_DESIGN_2026-11-21.md) for the QA-only fixed Rust log marker, preserved native close veto, and required independent process identity before any future capture.
- [N12 no-CDP bounded main-window readiness](./P4_N12_NO_CDP_BOUNDED_WINDOW_WAIT_2026-11-21.md) for clean-absence-only retries, capped startup observation, and exact-source CI evidence, not native acceptance.
- [N12 no-CDP source lifecycle observer](./P4_N12_NO_CDP_LIFECYCLE_SOURCE_STITCH_2026-11-21.md) for the fail-closed log/handle/window/close stage ordering, current CI and remaining native-proof gaps.
- [N12 no-CDP main-window identity](./P4_N12_NO_CDP_MAIN_WINDOW_IDENTITY_2026-11-21.md) for the read-only Windows window/process-handle witness and generated CI, not native acceptance.
- [N12 no-CDP whole-profile shutdown source proof](./P4_N12_NO_CDP_PROFILE_SHUTDOWN_2026-11-21.md) for child ETW exit, parent sequence and capture-loss completeness fixtures, not native acceptance.
- [N12 no-CDP OS-corroborated browser identity](./P4_N12_NO_CDP_BROWSER_IDENTITY_2026-11-21.md) for the source-only fail-closed role/profile/lifetime proof, not a native capture.
- [N12 no-CDP read-only app-log witness](./P4_N12_NO_CDP_LOG_WITNESS_2026-11-21.md) for fixed, unique, non-stale readiness receipts with a bounded prelaunch/postclose verification contract; no native acceptance.
- [21 November authorized debug-only WebView storage result](../qa/p4_research/N12_WEBVIEW_DEBUG_ONLY_RESULT_44852642468.md) for the observed ambient temp creates without netlog, incomplete collector coverage and the no-CDP next hypothesis.
- [Live development workspace](./LIVE_DEVELOPMENT.md) and [QA preflight and failure planning](./QA_PREFLIGHT_AND_FAILURE_PLANNING.md).
- [19 November work and process audit](./WORK_AND_PROCESS_AUDIT_2026-11-19.md) for the documented decision flow, hosted run analysis and evidence corrections.
- [Complexity-last roadmap](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) for the intended phase sequence.
- [P1 closure](./P1_CLOSURE_REGISTER_2026-10-28.md), [P2 closure](./P2_DEVELOPMENT_CLOSURE_2026-11-06.md) and [P3 closure](./P3_DEVELOPMENT_CLOSURE_2026-11-09.md).
- [18 November documentation audit](./DOCUMENTATION_AUDIT_2026-11-18.md) for that day's reconciliation, link inventory and archived handoff. [17 November audit](./DOCUMENTATION_AUDIT_2026-11-17.md) · [16 November audit](./DOCUMENTATION_AUDIT_2026-11-16.md)
- The owner-held 22 October Master Reconstruction Blueprint defines the product specification, subject to recorded owner amendments.

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
