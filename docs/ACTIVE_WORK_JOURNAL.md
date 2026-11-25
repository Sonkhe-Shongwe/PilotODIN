# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C3-EXPLICIT-STARTUP-AUTH-20261125 |
| State | VERIFYING |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 8cc75612d1fcfdc16ee75bd0f3424c443c654544; prepared 95269d91e2140954d77564aa6ee69db9ed0c58ba; published ab9d81402c19db50eadde743da82669f53d49399. |
| Product baseline | 42533a5 verifier source; 912fa2d correction; 4ef725b target fixtures; d469652 R03; 22dbdaf P2/P3 all exact routine CI SUCCESS; ab9d81402c19db50eadde743da82669f53d49399 desktop/workspace/import test+CI migration pending terminal reconciliation. |
| Scope | C3 explicit production/dev startup and authentication contract, existing route/direct-call compatibility inventory, disposable source/HTTP negative tests; section 10 and C-D05. No expansion into C4/C5. |
| Operation ID | C3-DESKTOP-FOUNDATION-WORKSPACE-FIXTURE-20261125-test |
| Operation state | RECONCILED |
| Intended files | tests/test_desktop_foundation.py, tests/test_workspace_boundary.py, tests/test_cf01_upload_http.py, tests/test_cf02_xlsx_identifier_parity.py, .github/workflows/p1-isolated-backend.yml. Replace desktop foundation legacy global bare client with per-test explicit dev/desktop/debug immutable trust, retain protected reads/writes/origin checks, update bounded credential-free OPTIONS contract and assert actual requests remain protected. Strengthen historic debug environment test with immutable configuration despite subsequent environment changes. Update stale Rust source assertion from removed create_dir_all to actual pinned worker_data_home and verify-before-spawn ordering, retaining CWD/home checks; no Rust edit. Three workspace subprocess clients migrate, retain owned lease, scratch and interruption assertions. Five CSV/XLSX fixture clients migrate with original lifespan; register desktop foundation and CF01/02 in separate runner-owned P1 test step. No application code or restricted action. |
| Approval | All six native approvals consumed and disarmed. Source/docs and routine synthetic CI permitted; no new restricted operation, activation, model, owner data, OS modification or installer. |
| Verification | Six-file diff verified: desktop foundation, workspace boundary, CF01/02 tests, P1 isolated CI and journal. Historical global bare desktop client replaced by per-test immutable explicit dev/desktop/debug trust; missing/wrong/mixed credentials rejected, bounded credential-free OPTIONS 204, invalid negotiation 403, environment changes cannot alter captured mode. Historical Rust source assertion now checks actual pinned worker_data_home and storage_pins.verify before spawn, retaining CWD and HOME assertions. Three embedded workspace subprocess clients and five CSV/XLSX upload contexts migrated; original lease, interruption, scratch, preservation and identifier assertions retained. P1 registers three existing suites in runner-owned home. No application code change. Exact two expected workflows: P1 backend [#45585267166](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45585267166) in_progress; P4 ranking [#45585267078](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45585267078) in_progress. Jobs 139105128975 P1 backend; 139105129155 P4 synthetic; 139105129011 P4 disposable browser; 139105128768 P4 Windows synthetic; restricted collector 139105130809 SKIPPED. Previous exact 22dbdaf inventory 35 lexical transport construction paths vs 53; not count of unsafe callers. No owner/native action. |
| Pending runs | P1 backend [#45585267166](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45585267166) in_progress; P4 ranking [#45585267078](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45585267078) in_progress |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | First reconcile exact P1/P4 runs for ab9d814, preserve and correct failures; next migrate remaining A4/B5 reporting/export/Quality and historical test clients, classify isolated middleware/router test transports, audit remaining direct callers and frontend/native bootstrap, then remove legacy fallbacks and perform C3 closure matrix. No activation. |
| Resume after closure | C4, C5 in order; D separately approved. |

## Prior operation

C-DOCUMENTATION-AUDIT-20261125-clean: owner-requested documentation audit prepared at [`7b8eb7c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7b8eb7c339987d43a601f6191571f4b1c0b7f61c); final commit identified by parent and operation marker. [Audit](./DOCUMENTATION_AUDIT_C_CONTINUITY_2026-11-25.md) records scope, changes and evidence. Original integration operation terminal failure, cleanup and disarm reconciled. No pending restricted operation.

## Unresolved or interrupted operations

C1/C2 source closed; C3 explicit authentication work next. No actual application/production or physical hardware acceptance. G2 proof blocker and physical D evidence remain outstanding. Earlier B5 approvals consumed; preserve local work. [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bcd3a979b1bbd30ab8cd2f60ad16b9c9e25c40cf/docs/ACTIVE_WORK_JOURNAL.md) retains prior operation detail.
