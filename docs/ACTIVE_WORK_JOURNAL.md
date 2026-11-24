# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C3-EXPLICIT-STARTUP-AUTH-20261125 |
| State | VERIFYING |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 926c095d460fa53a03c25b9b9bf33c2e161351a2 |
| Product baseline | e0f944d2a9c14c4ae470c38c929bae249f35373c (frontend delta); native/backend runtime 388b35750316b9c5a060d603c35c7d728d5c0890; test-only native fixture 1d23ea139762d94d25e689c4c3489b72fb34acc9 |
| Scope | C3 explicit production/dev startup and authentication contract, existing route/direct-call compatibility inventory, disposable source/HTTP negative tests; section 10 and C-D05. No expansion into C4/C5. |
| Operation ID | C3-DESKTOP-OUTER-GUARD-20261125-source |
| Operation state | ISSUED |
| Intended files | backend/request_auth.py, backend/desktop_runner.py, backend/main.py, tests/test_owned_server.py, tests/test_desktop_runner_process_smoke.py, tests/test_c1_resource_host.py, continuity records. No native Rust/model changes. |
| Approval | All six native approvals consumed and disarmed. Source/docs and routine synthetic CI permitted; no new restricted operation, activation, model, owner data, OS modification or installer. |
| Verification | C1/C2 SOURCE CLOSED, unchanged. C3 kernel exact 5fc531e source job 138854868629 SUCCESS: all five named C3 cases passed, workspace/owned-server 48 tests, 1058 Python + 544 subtests (6 skipped), 112 Node, Vite; disposable browser job 138854868635 SUCCESS. Windows job SUCCESS 53 passed, 66 subtests; restricted 138854871137 SKIPPED. No live auth integration. |
| Pending runs | Desktop outer guard integration published with this checkpoint; routine exact CI pending. No Rust, installer, model or owner runtime. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Integrate immutable desktop outer ASGI guard in both runner paths before route/storage work; strict 64-hex token and mixed-mode refusal before workspace; explicit desktop-debug mode from existing Rust flag with only existing fixed development ports; no release-origin exception. Disable Uvicorn proxy rewriting, terminate preflight at guard, use private in-process proof to skip mutable legacy check only after authorization; keep old non-desktop/test compatibility until migration. Expand actual disposable process negatives, pure ASGI and bootstrap tests; reconcile matching exact CI. |
| Resume after closure | C4, C5 in order; D separately approved. |

## Prior operation

C-DOCUMENTATION-AUDIT-20261125-clean: owner-requested documentation audit prepared at [`7b8eb7c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7b8eb7c339987d43a601f6191571f4b1c0b7f61c); final commit identified by parent and operation marker. [Audit](./DOCUMENTATION_AUDIT_C_CONTINUITY_2026-11-25.md) records scope, changes and evidence. Original integration operation terminal failure, cleanup and disarm reconciled. No pending restricted operation.

## Unresolved or interrupted operations

C1/C2 source closed; C3 explicit authentication work next. No actual application/production or physical hardware acceptance. G2 proof blocker and physical D evidence remain outstanding. Earlier B5 approvals consumed; preserve local work. [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bcd3a979b1bbd30ab8cd2f60ad16b9c9e25c40cf/docs/ACTIVE_WORK_JOURNAL.md) retains prior operation detail.
