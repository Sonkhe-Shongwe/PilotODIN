# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C5-REPRODUCIBLE-BUILD-INPUTS-20261125 |
| State | PREPARED |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 216624223d16beae02275228f098654804f2586a |
| Product baseline | 8da7f33cb418e453a7b5c250b960fb6370e9e9d0; exact P1/P4 SUCCESS. |
| Scope | C-D08 and C5 exit: read-only dependency/toolchain/asset inventory, source locks and fail-closed preflight; no acquisition, packaging, installer or D activation. |
| Operation ID | C5-TOOLCHAIN-CHECKSUMS-ONCE-20261125 |
| Operation state | PREPARED: explicit owner approval received; prior exact 28 checks passed, no live activation issued. |
| Intended files | Isolated qa/c5_wheel_metadata/collect_toolchain_checksums.py and dedicated offline workflow; no product or prior receipt changes. Archive inspector remains independent. |
| Approval | Eleven prior restricted approvals consumed/disarmed. Fresh one-use approval: four exact checksum documents, six HTTPS GETs maximum including permitted redirects, 5 MiB total, 991/821 bytes exact Python, 64 KiB Node, 4 MiB Rust, 15s/request, 10min/job. No retries, binary downloads, signature/key requests, installs, registry, native/model, owner device or expanded scope. |
| Verification | Exact 8da7f33: P4 #45693703789 SUCCESS, 1242 Python/6 skipped/1 warning/552 subtests, 15 Rust, 161 Node/Vite, 3 bundle refusal, 13 HTTP, 155 Windows C5/1 skipped, parser, 3 refusal, 68 Windows/133 subtests; restricted collector skipped. P1 #45693704390 SUCCESS, 206 Node/TypeScript/Vite, 11 Chromium. |
| Pending runs | None for this operation. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Fresh explicit owner approval required for one checksum-only hosted attempt: four exact documents from pinned plan (two Actions Python hashes.sha256, Node 22.23.5 SHASUMS256.txt and Rust 1.100.0 channel TOML), max 6 HTTP GETs including one narrowly permitted authenticated GitHub redirect per Python document; 991/821 bytes exact, 64 KiB Node, 4 MiB Rust, 5 MiB aggregate, 15s/request, 10min/job. No retries, signature/key requests, binary/artifact downloads, registry, install, execution, native/model, owner device or expanded scope. After approval publish exact marker-only trigger, exact commit message, attempt 1 and blob pin; reconcile raw receipt and disarm. Independently proceed with bounded offline wheel archive inspector before separate acquisition proposal. |
| Resume after closure | D only after C5 source closure, G2 resolution and separately approved scope. |

## Prior operation

C4-RESEARCH-AND-IMPLEMENTATION-PLAN-20261125: [`bd7c163`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd7c1639c3b98ae93e0d83b8170e189dc042b365), documentation-only [plan](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md#25-november--c4-baseline-research-and-proposed-implementation-plan-not-implementation-or-closure); no code, test or source credit. C3 [source closure](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7db2f60e7daa4e4f975822503b4e78008f4977e2) and all exact results are preserved in the [C ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md). [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bd7c1639c3b98ae93e0d83b8170e189dc042b365/docs/ACTIVE_WORK_JOURNAL.md) retains the earlier operation receipts; [prepared audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1e950e5a8a575b710f95e26ad9a31251ef73f0fb) records this operation's intent. [Historical C4 audit](./DOCUMENTATION_AUDIT_C4_READINESS_2026-11-25.md) · [Current C5 audit](./DOCUMENTATION_AUDIT_C5_READINESS_2026-11-25.md).

## Unresolved or interrupted operations

A/B and C1–C4 source closed; C5 outstanding. Source 14/17 (82.4%), official P4 14/20 (70%). Native DPAPI, actual desktop/physical egress and durability, physical 8 GB and G2/D evidence deferred. Owner-local tree uninspected. All eleven restricted approvals consumed/disarmed; preserve local work, installer freeze unchanged. Historical failures and exact receipts retained in C ledger.
