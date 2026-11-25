# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C5-REPRODUCIBLE-BUILD-INPUTS-20261125 |
| State | READY |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 5ccf217105c548ee76b1211c7031e4a85eefc079 |
| Product baseline | 8da7f33cb418e453a7b5c250b960fb6370e9e9d0; exact P1/P4 SUCCESS. |
| Scope | C-D08 and C5 exit: read-only dependency/toolchain/asset inventory, source locks and fail-closed preflight; no acquisition, packaging, installer or D activation. |
| Operation ID | C5-TOOLCHAIN-PROVENANCE-MATRIX-20261125 |
| Operation state | RECONCILED: evidence-only toolchain matrix, 11 blocked rows, five invocation-version observations across rows, two pinned runner-image manifests, one older manifest unavailable (404). Zero verified distribution bytes, production version selections or installable profiles. Read-only source/log review; no new CI needed for evidence-only checkpoint. |
| Intended files | Evidence-only qa/c5_wheel_metadata/toolchain_provenance_20261125.json and canonical journal/handoff/ledger; preserve product, policy, prior receipts and approvals. |
| Approval | Eleven restricted approvals consumed/disarmed (six native, five metadata). No additional registry requests, artifacts, installs, native/model, owner device/data or installer authorized. |
| Verification | Exact 8da7f33: P4 #45693703789 SUCCESS, 1242 Python/6 skipped/1 warning/552 subtests, 15 Rust, 161 Node/Vite, 3 bundle refusal, 13 HTTP, 155 Windows C5/1 skipped, parser, 3 refusal, 68 Windows/133 subtests; restricted collector skipped. P1 #45693704390 SUCCESS, 206 Node/TypeScript/Vite, 11 Chromium. |
| Pending runs | None for this operation. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Read-only official release/checksum manifest research for exact candidate CPython Windows 3.11.9 and Linux 3.11.18, Node 22.23.5/npm 10.9.9, Rust/Cargo 1.100.0; do not equate upstream source tarball with hosted binary or select a new production toolchain. Resolve CP311 pip identity and exact Windows MSVC/SDK/redist candidates separately; preserve all null unknowns. Prepare bounded acquisition-only proposals only after independent immutable URL/hash/size/notice evidence. No live registry requests, artifact downloads, installation, native/model, owner device or installer authority. All four profiles BLOCKED. |
| Resume after closure | D only after C5 source closure, G2 resolution and separately approved scope. |

## Prior operation

C4-RESEARCH-AND-IMPLEMENTATION-PLAN-20261125: [`bd7c163`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd7c1639c3b98ae93e0d83b8170e189dc042b365), documentation-only [plan](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md#25-november--c4-baseline-research-and-proposed-implementation-plan-not-implementation-or-closure); no code, test or source credit. C3 [source closure](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7db2f60e7daa4e4f975822503b4e78008f4977e2) and all exact results are preserved in the [C ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md). [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bd7c1639c3b98ae93e0d83b8170e189dc042b365/docs/ACTIVE_WORK_JOURNAL.md) retains the earlier operation receipts; [prepared audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1e950e5a8a575b710f95e26ad9a31251ef73f0fb) records this operation's intent. [Historical C4 audit](./DOCUMENTATION_AUDIT_C4_READINESS_2026-11-25.md) · [Current C5 audit](./DOCUMENTATION_AUDIT_C5_READINESS_2026-11-25.md).

## Unresolved or interrupted operations

A/B and C1–C4 source closed; C5 outstanding. Source 14/17 (82.4%), official P4 14/20 (70%). Native DPAPI, actual desktop/physical egress and durability, physical 8 GB and G2/D evidence deferred. Owner-local tree uninspected. All eleven restricted approvals consumed/disarmed; preserve local work, installer freeze unchanged. Historical failures and exact receipts retained in C ledger.
