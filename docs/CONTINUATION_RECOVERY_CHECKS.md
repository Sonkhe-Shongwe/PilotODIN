# PilotODIN | Continuation recovery checks

**Scope:** deterministic, documentation-only decision-table rehearsal, 24 November 2026, task CONT-RESILIENCE-20261124. This is not a native run, automated runtime guard, real context-exhaustion experiment or proof of tool availability. No actual duplicate push, native action, interruption or owner data access was simulated against live systems. The initial prepared journal was actually published at [`89cb4b5`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/89cb4b56ad64421887e8548b30a5261e1b188f8c); that is a real recoverable pre-operation record.

## Expected recovery decisions

| Case | Interruption or observation | Required decision | Reason |
| --- | --- | --- | --- |
| 01 Before source mutation | PREPARED; no matching commit; live HEAD and expected parent agree | `RESUME_PREPARED` | Recheck scope and apply the planned bounded change once. |
| 02 After source push, before receipt | PREPARED/ISSUED; matching task/operation commit exists | `RECONCILE_EXISTING` | Inspect diff and actual workflow runs; record existing publication without replay. |
| 03 Unknown source push response | ISSUED/UNKNOWN; Git result not established | `INSPECT_BEFORE_RETRY` | Query HEAD/history/diff; no repeated write until actual outcome is established. |
| 04 CI in progress | VERIFYING; exact matching run still in progress | `RECONCILE_PENDING` | Keep pending run ID; no PASS, no duplicate dispatch. |
| 05 CI terminal failure | VERIFYING; exact run failed | `RECORD_FAILURE` | Preserve failed evidence, diagnose the demonstrated cause and select a bounded correction. |
| 06 Approval not granted | BLOCKED; proposed native action has no fresh explicit owner approval | `AWAIT_APPROVAL` | Prepare only disabled scope; independent authorised source work may proceed. |
| 07 Uncertain restricted dispatch | ISSUED/UNKNOWN; approval may have been consumed | `PROTECT_AND_RECONCILE` | Never replay; disarm exact owned activation if applicable and safe, inspect runs and branch history; request distinct approval if required. |
| 08 Concurrent branch advance | HEAD differs from observed expected SHA | `INSPECT_CONFLICT` | Read new commits and dirty state where accessible; never force-push or overwrite. |
| 09 Unpublished local work unavailable | Local state unknown or inaccessible | `PRESERVE_LOCAL_UNKNOWN` | Do not infer clean state or reconstruct/overwrite it; use safe published work or request necessary evidence. |
| 10 Completed checkpoint | Exact result reconciled; task CLOSED | `SELECT_NEXT` | Resume first outstanding authorised handoff action, not closed work. |
| 11 Source passes but native acceptance absent | Source CI PASS; restricted verification still required | `KEEP_SCOPE_OPEN` | Record source-only result, no native or acceptance credit. |
| 12 GitHub unavailable | Authoritative branch/operation state cannot be verified | `STOP_UNVERIFIED` | State blocker; no guessed replay or destructive operation. |

The pure conditional rehearsal evaluated all 12 named cases against their expected decisions: 12/12 matched. This confirms the documented recovery branches are coherent for these fixtures, not that all possible interleavings or future agent behaviours are safe. The actual policy and evidence checks in the [continuation protocol](./CONTINUATION_PROTOCOL_CURRENT.md) remain mandatory.

## Lightweight consistency check at checkpoint

- Verify live branch and current published HEAD; distinguish product SHA and documentation commits.
- Read journal task/operation state; compare intended files/parent against actual diff and exact runs. Check that each operation has one stable ID and one terminal receipt or explicit pending/unknown state.
- Confirm live handoff points to the first outstanding task, and that journal scope and approval state do not broaden it.
- Verify source counts and official acceptance separately; preserve the scorecard and outstanding evidence.
- Resolve changed relative navigation paths and explicitly preserve historic anchors; if an old anchor cannot be verified, report it rather than claiming universal link integrity.
- Check matching workflows and actual job scope; no accidental native/installer activation.
- Check that decisions are linked once and that no repeated historical receipt was pasted into unrelated live documents.

Do not add a commit or receipt when there is no state change. For a full audit, record what was actually inspected, findings, preserved evidence and limitations. A clean checkpoint requires no new audit document.

## Recovery drill for a fresh session

Read only AGENTS, compact handoff, journal and the relevant protocol sections first. Resolve the prepared/issued operation from Git and CI before starting any other work. Consult the exact specification, decision and evidence sections for the selected task; do not ingest the full historical session handoff. Ask for new owner input only if necessary evidence or authority remains genuinely unavailable. An agent without GitHub access cannot certify current state and must not replay an uncertain operation.
