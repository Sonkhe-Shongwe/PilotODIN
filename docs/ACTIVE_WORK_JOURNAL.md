# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C5-REPRODUCIBLE-BUILD-INPUTS-20261125 |
| State | READY |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | ccdbf4b3fca677dfb6afd83266a3f1d41783e3cc |
| Product baseline | 8da7f33cb418e453a7b5c250b960fb6370e9e9d0; exact P1/P4 SUCCESS. |
| Scope | C-D08 and C5 exit: read-only dependency/toolchain/asset inventory, source locks and fail-closed preflight; no acquisition, packaging, installer or D activation. |
| Operation ID | C5-CHECKSUM-REMAINING-REVIEW-20261126 |
| Operation state | RECONCILED: exact 17df008fe505bd9c120e6085ff5e499534fc092d, collector blob 5f65d13d657ea2455e9fcc8239b68eacb4c53d43, run 45718196315 job 139569558338 SUCCESS, 42 checks, 4 synthetic requests, prior Windows receipt independently revalidated, original refusal reproduced, live false, CLI FRESH_APPROVAL_REQUIRED; restricted job 139569560787 skipped. No live requests. |
| Intended files | New qa/c5_wheel_metadata/collect_remaining_checksums.py and dedicated offline workflow; no product or prior receipt changes. Wheel inspector remains independent. |
| Approval | Twelve restricted approvals consumed/disarmed (six native, six metadata). No additional registry/metadata requests, artifacts, installs, native/model, owner device/data or installer authorized. |
| Verification | Exact 8da7f33: P4 #45693703789 SUCCESS, 1242 Python/6 skipped/1 warning/552 subtests, 15 Rust, 161 Node/Vite, 3 bundle refusal, 13 HTTP, 155 Windows C5/1 skipped, parser, 3 refusal, 68 Windows/133 subtests; restricted collector skipped. P1 #45693704390 SUCCESS, 206 Node/TypeScript/Vite, 11 Chromium. |
| Pending runs | None for this operation. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Fresh explicit owner approval required for one remaining-three checksum-only attempt: Linux Python 3.11.18 hashes.sha256 (821 exact bytes, pinned document and target SHA256), Node 22.23.5 SHASUMS256.txt (64 KiB), Rust 1.100.0 exact channel TOML (4 MiB). Maximum four HTTPS GETs incl. one permitted authenticated GitHub redirect for Linux Python, 4260661 aggregate body bytes, 15s/request, 10min/job. No Windows checksum request, retries, binaries, signatures/keys, registry, installs, native/model, owner device or expanded scope. After explicit approval exact marker-only activation, exact commit message, attempt 1, blob pin, reconcile/disarm. Independently implement/test bounded wheel archive inspector; no wheel acquisition approved. |
| Resume after closure | D only after C5 source closure, G2 resolution and separately approved scope. |

## Prior operation

C4-RESEARCH-AND-IMPLEMENTATION-PLAN-20261125: [`bd7c163`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd7c1639c3b98ae93e0d83b8170e189dc042b365), documentation-only [plan](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md#25-november--c4-baseline-research-and-proposed-implementation-plan-not-implementation-or-closure); no code, test or source credit. C3 [source closure](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7db2f60e7daa4e4f975822503b4e78008f4977e2) and all exact results are preserved in the [C ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md). [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bd7c1639c3b98ae93e0d83b8170e189dc042b365/docs/ACTIVE_WORK_JOURNAL.md) retains the earlier operation receipts; [prepared audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1e950e5a8a575b710f95e26ad9a31251ef73f0fb) records this operation's intent. [Historical C4 audit](./DOCUMENTATION_AUDIT_C4_READINESS_2026-11-25.md) · [Current C5 audit](./DOCUMENTATION_AUDIT_C5_READINESS_2026-11-25.md).

## Unresolved or interrupted operations

A/B and C1–C4 source closed; C5 outstanding. Source 14/17 (82.4%), official P4 14/20 (70%). Native DPAPI, actual desktop/physical egress and durability, physical 8 GB and G2/D evidence deferred. Owner-local tree uninspected. All twelve restricted approvals consumed/disarmed; preserve local work, installer freeze unchanged. Historical failures and exact receipts retained in C ledger.
