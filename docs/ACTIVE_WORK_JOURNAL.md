# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C5-REPRODUCIBLE-BUILD-INPUTS-20261125 |
| State | PREPARED |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 12751c3a3c20569683412a2ea60f15aec9c9d493 |
| Product baseline | 8da7f33cb418e453a7b5c250b960fb6370e9e9d0; exact P1/P4 SUCCESS. |
| Scope | C-D08 and C5 exit: read-only dependency/toolchain/asset inventory, source locks and fail-closed preflight; no acquisition, packaging, installer or D activation. |
| Operation ID | C5-R2-DISCOVERY-EXACT-CANDIDATE-20261126 |
| Operation state | PREPARED: owner approved unreferenced exact candidate objects only; pinned inputs and arm blobs computed. No branch activation. |
| Intended files | Docs checkpoint; unreferenced arm driver/workflow and marker-only child; no live branch ref update to either candidate. |
| Approval | Explicit preparation-only approval; 18 restricted approvals consumed/disarmed. No acquisition or repository variable change approved in this turn. |
| Verification | Exact 8da7f33: P4 #45693703789 SUCCESS, 1242 Python/6 skipped/1 warning/552 subtests, 15 Rust, 161 Node/Vite, 3 bundle refusal, 13 HTTP, 155 Windows C5/1 skipped, parser, 3 refusal, 68 Windows/133 subtests; restricted collector skipped. P1 #45693704390 SUCCESS, 206 Node/TypeScript/Vite, 11 Chromium. |
| Pending runs | None; Exact [source 09b2152](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/09b2152dd975015d94fda5522f3b2469cfd5ff18); [Run 45799165332](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45799165332): Ubuntu 139837539431 SUCCESS 240 tests, two new prelaunch tests; Windows 139837539702 success; 240 tests observed, 2 new prelaunch tests passed; live jobs 139837541917 and 139837542206 SKIPPED. [Run 45799165272](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45799165272): Ubuntu 139837539605 SUCCESS 49 tests, two new prelaunch tests; Windows 139837539250 success; 49 tests observed, 2 new prelaunch tests passed; live jobs 139837541323 and 139837541688 SKIPPED. Dedicated 49 tests overlap the full 240, not additive. qa/c5_wheel_metadata/wheel_hosted_final.py: e0501942a15d61f50bb9f3429bdee3721456461b; qa/c5_wheel_metadata/test_wheel_hosted_final.py: cb5c6bfbbc12c5c19f96ae66a0148fdf74fe0012; .github/workflows/c5-wheel-public-discovery.yml: e534daa5a945cb149ccf405c83b038e2cfb5b25a; .github/workflows/c5-wheel-hosted-final-review.yml: fb307867bcc7cd336a4f1ced979cab72ef4f7a74. Source arms false, public raw review pin absent, four literal false guards in discovery workflow, prior full-evidence workflow unchanged. |
| Unpublished work | Owner-local tree not inspected; QA implementation and correction published and exact CI reconciled. |
| Recovery action | Candidate inputs SHA256 093c2553aa4b5be20d2324ca185789d5b4cbe98585ae9919e4ceb69127e38e38, arm driver 37bdd1a1160f5bd8597df8788c7c4ce83f409c20, workflow e36f5533902a568f1d9567b5c4b6a4df5de294fe. Exact unreferenced parent/child SHAs and variable values returned in owner-facing review; recover by those identities, verify active branch unchanged. Do not advance branch or recreate candidate without reconciliation. Any extra branch commit invalidates the prepared parent relationship. Owner/admin provisioning and separate exact execution approval required. |
| Resume after closure | D only after C5 source closure, G2 resolution and separately approved scope. |

## Prior operation

C4-RESEARCH-AND-IMPLEMENTATION-PLAN-20261125: [`bd7c163`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd7c1639c3b98ae93e0d83b8170e189dc042b365), documentation-only [plan](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md#25-november--c4-baseline-research-and-proposed-implementation-plan-not-implementation-or-closure); no code, test or source credit. C3 [source closure](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7db2f60e7daa4e4f975822503b4e78008f4977e2) and all exact results are preserved in the [C ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md). [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bd7c1639c3b98ae93e0d83b8170e189dc042b365/docs/ACTIVE_WORK_JOURNAL.md) retains the earlier operation receipts; [prepared audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1e950e5a8a575b710f95e26ad9a31251ef73f0fb) records this operation's intent. [Historical C4 audit](./DOCUMENTATION_AUDIT_C4_READINESS_2026-11-25.md) · [Prior C5 audit](./DOCUMENTATION_AUDIT_C5_READINESS_2026-11-25.md) · [Current C5-R1 consistency audit](./DOCUMENTATION_AUDIT_C5_R1_READINESS_2026-11-26.md).

## Unresolved or interrupted operations

A/B and C1–C4 source closed; C5 outstanding. Source 14/17 (82.4%), official P4 14/20 (70%). Native DPAPI, actual desktop/physical egress and durability, physical 8 GB and G2/D evidence deferred. Owner-local tree uninspected. Eighteen restricted approvals consumed/disarmed; preserve local work, installer freeze unchanged. Historical failures and exact receipts retained in C ledger.
