# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C3-EXPLICIT-STARTUP-AUTH-20261125 |
| State | READY |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 8cc75612d1fcfdc16ee75bd0f3424c443c654544; prepared 95269d91e2140954d77564aa6ee69db9ed0c58ba; published ab9d81402c19db50eadde743da82669f53d49399. |
| Product baseline | 42533a5 verifier source; 912fa2d correction; 4ef725b target fixtures; d469652 R03; 22dbdaf P2/P3; ab9d814 desktop/workspace/import migration all exact routine CI SUCCESS. |
| Scope | C3 explicit production/dev startup and authentication contract, existing route/direct-call compatibility inventory, disposable source/HTTP negative tests; section 10 and C-D05. No expansion into C4/C5. |
| Operation ID | C3-DESKTOP-FOUNDATION-WORKSPACE-FIXTURE-20261125-test |
| Operation state | RECONCILED |
| Intended files | tests/test_desktop_foundation.py, tests/test_workspace_boundary.py, tests/test_cf01_upload_http.py, tests/test_cf02_xlsx_identifier_parity.py, .github/workflows/p1-isolated-backend.yml. Replace desktop foundation legacy global bare client with per-test explicit dev/desktop/debug immutable trust, retain protected reads/writes/origin checks, update bounded credential-free OPTIONS contract and assert actual requests remain protected. Strengthen historic debug environment test with immutable configuration despite subsequent environment changes. Update stale Rust source assertion from removed create_dir_all to actual pinned worker_data_home and verify-before-spawn ordering, retaining CWD/home checks; no Rust edit. Three workspace subprocess clients migrate, retain owned lease, scratch and interruption assertions. Five CSV/XLSX fixture clients migrate with original lifespan; register desktop foundation and CF01/02 in separate runner-owned P1 test step. No application code or restricted action. |
| Approval | All six native approvals consumed and disarmed. Source/docs and routine synthetic CI permitted; no new restricted operation, activation, model, owner data, OS modification or installer. |
| Verification | Exact ab9d814 P1 #45585267166 job 139105128975 SUCCESS (16 desktop/import tests, 3+9 mixed report, nine PDF, prior source suites). P4 #45585267078 terminal SUCCESS: Linux 1061 passed, six skipped, one warning, 552 subtests; 126 Node; 13 Chromium; 68 Windows and 133 subtests; five model-free benchmark scenarios PASS; restricted collector 139105130809 SKIPPED. Exact scanner 877/877 decoded, 349 lexical candidates, 31 transport-construction paths (prior 35, earlier 53), 76 routes, zero AST/decode gaps. Counts are not semantic closure. Backend main legacy no-secret/testserver/env fallback and frontend apiBase default 8000 still present; native smoke bootstrap still has nonrelay branch. No new source work in status review. |
| Pending runs | None. Exact ab9d814 P1/P4 terminal SUCCESS; restricted collector SKIPPED. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Next migrate A4/B5 reporting/export/Quality and remaining historical product test callers. Classify isolated C1 component transports and deliberate negative/source assertions. Review remaining direct callers, credential confinement and native/frontend bootstrap, then remove legacy fallbacks and complete C3 closure matrix. No activation. |
| Resume after closure | C4, C5 in order; D separately approved. |

## Prior operation

C-DOCUMENTATION-AUDIT-20261125-clean: owner-requested documentation audit prepared at [`7b8eb7c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7b8eb7c339987d43a601f6191571f4b1c0b7f61c); final commit identified by parent and operation marker. [Audit](./DOCUMENTATION_AUDIT_C_CONTINUITY_2026-11-25.md) records scope, changes and evidence. Original integration operation terminal failure, cleanup and disarm reconciled. No pending restricted operation.

## Unresolved or interrupted operations

C1/C2 source closed; C3 explicit authentication work next. No actual application/production or physical hardware acceptance. G2 proof blocker and physical D evidence remain outstanding. Earlier B5 approvals consumed; preserve local work. [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bcd3a979b1bbd30ab8cd2f60ad16b9c9e25c40cf/docs/ACTIVE_WORK_JOURNAL.md) retains prior operation detail.
