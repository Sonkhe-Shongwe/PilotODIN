# PilotODIN | Active work journal

Replace this record in place. It owns in-flight task recovery, not project progress or historical receipts. Read [live handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [protocol](./CONTINUATION_PROTOCOL_CURRENT.md).

## Active task

| Field | Value |
| --- | --- |
| Task ID | C3-EXPLICIT-STARTUP-AUTH-20261125 |
| State | VERIFYING |
| Branch | feature/live-dev-workspace-20261023 |
| Observed starting HEAD | 88348a51aee2289c30a0283e46dac0c66a31d81c; write-ahead 27dcfb98b5bb06eaf1a076d62276fc8c49648178; verified published d0818430bf1ad760fdc5fe97fbb5701624dafba2. |
| Product baseline | d0818430bf1ad760fdc5fe97fbb5701624dafba2 (A4 relay source, exact routine CI pending); 736a0fe fixed-port local QA product and 78ca6e1 correction verified. |
| Scope | C3 explicit production/dev startup and authentication contract, existing route/direct-call compatibility inventory, disposable source/HTTP negative tests; section 10 and C-D05. No expansion into C4/C5. |
| Operation ID | C3-A4-LIVE-DEV-RELAY-20261125-source |
| Operation state | RECONCILED |
| Intended files | frontend/scripts/live-dev-api-proxy.mjs, frontend/src/api.ts, frontend/src/desktopBootstrap.ts, tools/Verify_A4_Native_Windows.ps1, frontend/tests/desktop-ai-boundaries.test.cjs, frontend/tests/p1-playwright-pilot-contract.test.cjs, canonical journal. Keep existing A4 5174 origin/profile; explicitly enabled server-side relay only to existing authenticated Live Dev 5173 frontdoor; no inherited/copied capability, no direct 8000 fallback, same raw local origin/Host/marker checks, fixed destination and no redirects; authenticate readiness via 5173 marker. Do not change native compile wrapper, overlay or consent. Other hosted/native compatibility later. |
| Approval | All six native approvals consumed and disarmed. Source/docs and routine synthetic CI permitted; no new restricted operation, activation, model, owner data, OS modification or installer. |
| Verification | Seven-file diff verified at exact HEAD. A4 launcher authenticates readiness via 5173 without redirect/proxy, refuses inherited serving credentials and restores relay env. Explicit local 5174 relay validates raw origin, peer, Host, marker and forwards only to existing 5173 frontdoor, not 8000; existing live proxy adds private capability. Native smoke configures development API before health check; existing hosted legacy callers still pending. Source tests check composed two-hop plan, all five approved origins, invalid startup/mixed state, hostile cross-origin/forwarded headers. Native compilation wrapper unchanged; currently selects P4 isolated overlay instead of supplied A4 overlay. A4 actual native launch not validated; no new approval. Prior exact CI all routine jobs passed, restricted skipped. |
| Pending runs | P4 Target Review Queue and Transparent Ranking #45565819496 in_progress; P3 Real HTTP Semantic Context Browser Acceptance #45565819471 in_progress; P1 Disposable Real HTTP Browser/Backend Acceptance #45565819443 in_progress; P1 Isolated Frontend Verification #45565819480 in_progress. No restricted dispatch. |
| Unpublished work | Owner-local tree not inspected. |
| Recovery action | Reconcile exact d081843 CI, including any failures, before overlapping source pushes. Then hosted native P4-71/N12 launchers/direct HTTP clients, fixed admitted hosted home and private capability; maintain all native/trace gates and historic evidence. Address A4 existing wrapper/config compatibility at source scope without enabling native compilation; explicit in-process adapter and removal of bare runtime fallback; C3 route/caller matrix and closure. C4 deferred. |
| Resume after closure | C4, C5 in order; D separately approved. |

## Prior operation

C-DOCUMENTATION-AUDIT-20261125-clean: owner-requested documentation audit prepared at [`7b8eb7c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/7b8eb7c339987d43a601f6191571f4b1c0b7f61c); final commit identified by parent and operation marker. [Audit](./DOCUMENTATION_AUDIT_C_CONTINUITY_2026-11-25.md) records scope, changes and evidence. Original integration operation terminal failure, cleanup and disarm reconciled. No pending restricted operation.

## Unresolved or interrupted operations

C1/C2 source closed; C3 explicit authentication work next. No actual application/production or physical hardware acceptance. G2 proof blocker and physical D evidence remain outstanding. Earlier B5 approvals consumed; preserve local work. [Pre-audit journal](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/bcd3a979b1bbd30ab8cd2f60ad16b9c9e25c40cf/docs/ACTIVE_WORK_JOURNAL.md) retains prior operation detail.
