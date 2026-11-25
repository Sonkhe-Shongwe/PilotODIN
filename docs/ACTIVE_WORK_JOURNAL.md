# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C5-REPRODUCIBLE-BUILD-INPUTS-20261125 |
| State | PUBLISHED |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 57db2621433cd781b09b854d30d96028adb97822 |
| Product baseline | Last fully verified 898230f; 40d0e13 guard batch published, P4 Linux/Windows failed on removed SHA256 compatibility helper. |
| Scope | C-D08 and C5 exit: read-only dependency/toolchain/asset inventory, source locks and fail-closed preflight; no acquisition, packaging, installer or D activation. |
| Operation ID | C5-ASSET-HASH-COMPATIBILITY-20261125 |
| Operation state | ISSUED; recover exact correction from prepared parent 70f7221df20c5fd4bdeac4d3eeecc2a7c3f91c74. Production remains blocked. |
| Intended files | desktop/verify_inference_assets.py, tests/test_c5_build_input_preflight.py, canonical documentation only. No lock, workflow, approval or native marker changes. |
| Approval | All six native approvals consumed and disarmed. Source/docs and routine synthetic CI permitted; no new restricted operation, activation, model, owner data, OS modification or installer. |
| Verification | Exact 40d0e13 P4 #45684550154: source job 139453570467 FAILURE (two collection errors); Windows 139453569167 FAILURE after 78 C5 passed/1 skipped and 3 bundle preflight passes; shared cause missing sha256 export imported by offline_analytics_cases.py. HTTP 139453569971 still running at observation; collector skipped. |
| Pending runs | Prior HTTP 139453569971 outcome to reconcile; new exact P4 source/browser/synthetic Windows only expected. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Restore compatibility with read-only bounded-memory SHA256 function; ensure production verify continues unconditional BLOCKED. Review matching source workflow. Continue metadata research only, no artifact acquisition. |
| Resume after closure | D only after C5 source closure, G2 resolution and separately approved scope. |

## Prior operation

C4-RESEARCH-AND-IMPLEMENTATION-PLAN-20261125: [`bd7c163`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd7c1639c3b98ae93e0d83b8170e189dc042b365), documentation-only [plan](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md#25-november--c4-baseline-research-and-proposed-implementation-plan-not-implementation-or-closure); no code, test or source credit. C3 [source closure](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7db2f60e7daa4e4f975822503b4e78008f4977e2) and all exact results are preserved in the [C ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md). [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bd7c1639c3b98ae93e0d83b8170e189dc042b365/docs/ACTIVE_WORK_JOURNAL.md) retains the earlier operation receipts; [prepared audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1e950e5a8a575b710f95e26ad9a31251ef73f0fb) records this operation's intent. [Historical C4 audit](./DOCUMENTATION_AUDIT_C4_READINESS_2026-11-25.md) · [Current C5 audit](./DOCUMENTATION_AUDIT_C5_READINESS_2026-11-25.md).

## Unresolved or interrupted operations

A/B and C1–C4 source closed; C5 outstanding. Source 14/17 (82.4%), official P4 14/20 (70%). Native DPAPI, actual desktop/physical egress and durability, physical 8 GB and G2/D evidence deferred. Owner-local tree uninspected. All six native approvals consumed/disarmed; preserve local work, installer freeze unchanged. Historical failures and exact receipts retained in C ledger.
