# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C5-REPRODUCIBLE-BUILD-INPUTS-20261125 |
| State | PUBLISHED |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | d4b58a86b952d6db3f7514ff35a5c2cdf0bdacb7 |
| Product baseline | 9163e6c last fully verified; ec74f49 graph and Linux/HTTP pass; Windows lifecycle pending. |
| Scope | C-D08 and C5 exit: read-only dependency/toolchain/asset inventory, source locks and fail-closed preflight; no acquisition, packaging, installer or D activation. |
| Operation ID | C5-ARCHIVE-VALIDATION-20261125 |
| Operation state | ISSUED; recover exact source from prepared parent 31259021e8c3e3b7d0d9dfad33d87914eff39eb5. Candidate archive validation only. |
| Intended files | tools/c5_archive_preflight.py, tests/test_c5_build_input_preflight.py, .github/workflows/p4-target-ranking.yml, canonical documentation. No lock, marker, asset or production entrypoint changes. |
| Approval | C5 metadata-only approval CONSUMED; no replay. Exact run 45686334903 attempt 1 only. All six native approvals still consumed/disarmed. No artifact bytes, native, model, installer, owner device, OS/network change or additional metadata dispatch authorized. |
| Verification | Exact ec74f49 P4 #45687344896: Linux 1170 passed/6 skipped/552 subtests, 15 Rust, 160 Node/Vite, 3 bundle refusal, graph review PASS (59 edges/49 reachable each), HTTP 13 PASS; Windows in progress; collector skipped. |
| Pending runs | Prior graph CI #45687344896 reconcile final Windows status; expected new matching P4 routine synthetic workflow only. No metadata/native dispatch. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Use guarded bounded read_exact to hash and capture exact archive bytes; validate conservative classic ZIP layout before parser and member decompression, exact reviewed names, no links/ADS/traversal/collisions, file/total limits, independent member hashes. Inert fixtures only; production no READY or extract route. Review matching synthetic CI scope. |
| Resume after closure | D only after C5 source closure, G2 resolution and separately approved scope. |

## Prior operation

C4-RESEARCH-AND-IMPLEMENTATION-PLAN-20261125: [`bd7c163`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bd7c1639c3b98ae93e0d83b8170e189dc042b365), documentation-only [plan](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md#25-november--c4-baseline-research-and-proposed-implementation-plan-not-implementation-or-closure); no code, test or source credit. C3 [source closure](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7db2f60e7daa4e4f975822503b4e78008f4977e2) and all exact results are preserved in the [C ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md). [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bd7c1639c3b98ae93e0d83b8170e189dc042b365/docs/ACTIVE_WORK_JOURNAL.md) retains the earlier operation receipts; [prepared audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1e950e5a8a575b710f95e26ad9a31251ef73f0fb) records this operation's intent. [Historical C4 audit](./DOCUMENTATION_AUDIT_C4_READINESS_2026-11-25.md) · [Current C5 audit](./DOCUMENTATION_AUDIT_C5_READINESS_2026-11-25.md).

## Unresolved or interrupted operations

A/B and C1–C4 source closed; C5 outstanding. Source 14/17 (82.4%), official P4 14/20 (70%). Native DPAPI, actual desktop/physical egress and durability, physical 8 GB and G2/D evidence deferred. Owner-local tree uninspected. All six native approvals consumed/disarmed; preserve local work, installer freeze unchanged. Historical failures and exact receipts retained in C ledger.
