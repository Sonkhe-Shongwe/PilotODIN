# PilotODIN | Seamless continuation protocol

**Standing process | 24 November 2026.** Applies to every meaningful engineering checkpoint, chat/tab/model change and Codex handoff. This is a continuity rule, not new execution authority or a change to product scope, phase, acceptance or approval requirements.

## 1. Recover before acting

1. Query the live GitHub branch `feature/live-dev-workspace-20261023`, not default main. If working locally, independently inspect branch, HEAD and dirty state before edits; never infer that owner-local work is published or clean.
2. Read [compact current handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) and [active work journal](./ACTIVE_WORK_JOURNAL.md) first, then [product-first directive](./PILOTODIN_PRODUCT_FIRST_IMPLEMENTATION_DIRECTIVE_CURRENT.md), relevant package specification/evidence ledger, and [official scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard). The original Master Reconstruction Blueprint and explicit owner decisions remain normative; [phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) governs authority.
3. Reconcile exact published product SHA, documentation HEAD, pending CI run/job IDs and current results, consumed/disarmed approvals, blockers, open acceptance criteria and the first outstanding action. Read logs for consequential failures or claimed gate completion. A branch HEAD newer than the last tested product SHA is not evidence of a new test pass. If GitHub is inaccessible, state what is unverified; do not invent state.
4. Generic "next" or "continue" means execute the highest-value outstanding authorised task, not recap the whole project, replay history, start a new phase or grant restricted permissions.

## 2. One owner per information type

| Record | Owns | Update when |
| --- | --- | --- |
| Active work journal | In-flight task/operation identity, intent, actual or unknown outcome, recovery and permission state | Before and after consequential operations; replace in place |
| Compact migration handoff | Latest product SHA, live source progress, pending checks, blocker, approval state, precise next action and links | Meaningful checkpoint, including dispatch/result, failed or blocked work, scope change, or handoff |
| Active package evidence ledger (linked by handoff) | Exact receipts: product/test SHA, run/job IDs, result, counts, scope, limitations, artifacts, failure history | New evidence or a material correction; append a single dated receipt |
| Engineering decision index and owning specifications | Material choices, alternatives, rationale, limitations and reopen conditions | Material decisions only; link rather than duplicate |
| Official project scorecard | Earned acceptance points and required evidence | Evidence actually changes an official result or an owner-approved rule changes |
| Phase policy and live directive | Authority, fixed sequence, stop rules, exit requirements | Owner decision or genuine scoped change; not every implementation commit |
| Package specification | Design, invariants, limits, compatibility, exit criteria | Actual design or contract changes; no repeated CI diary |
| README, Continue Here, documentation index, session history | Navigation and historical context | Reference/structure changes, not ordinary implementation results |
| Audit record | Verified consistency and documented corrections | Periodic or event-triggered audit |

Avoid copying the same running status or receipt into every document. Other documents link to the canonical owner. Dated snapshots are historical even if they contain a former "next" instruction. Keep valid links/anchors or an immutable replacement, retain earlier failures, and never silently rewrite evidence. For each new package, link its ledger from the handoff and index; close the previous ledger without removing it.

## 3. Checkpoint transaction

Before a meaningful task ends or is handed off, record the minimum durable state:

- **Identity:** active branch, exact product/test commit, known documentation checkpoint or immutable reference. Do not self-reference an as-yet-unknown commit SHA. Verify actual published HEAD after push.
- **Completed:** scoped change and its outcome; distinguish completed source from pending verification, and published from local/unpublished.
- **Evidence:** exact run/job/artifact IDs, results and scope; distinguish source tests, type-check, linked native tests, actual app run and physical owner acceptance. Record failures before corrections; preserve outstanding runs even if not finished.
- **Progress:** prior and current numerator/denominator for affected source work; official score only when its criteria are met. No estimated acceptance increments.
- **Open work:** blocker, unresolved risks, pending CI and any cleanup/disarm. Include one precise immediate action and the next two or three checkpoints, in dependency order.
- **Authority:** ordinary source scope, exact approved restricted action if any, one-use consumption/disarm state, and prohibited operations. Generic continuation never broadens authority.

Update the handoff in place and append the evidence once; update the scorecard/spec/directive only if their owned facts changed. Publish with a non-force expected-HEAD check after inspecting matching workflow triggers. Reconcile CI at the next checkpoint; a running result is not a pass. If the next task is blocked on a restricted action, complete independent authorised work if useful, then present a precise approval request. If nothing changed since the last observation, report that fact without producing a redundant commit or receipt. Do not schedule background work or claim completion without evidence.

## 4. User-facing continuation format

Keep replies concise and proportional to change: completed / verification / progress delta / blockers and permission state / next action. Report links to canonical records instead of reproducing their contents. For a chat migration, a short copyable prompt plus the handoff link is sufficient; do not force the owner to paste a large transcript or repeat established details.

**Standard new-chat prompt:** Continue PilotODIN 1.0 from the current live GitHub handoff on `feature/live-dev-workspace-20261023`. Read `AGENTS.md`, `docs/TAB_MIGRATION_HANDOFF_CURRENT.md`, `docs/ACTIVE_WORK_JOURNAL.md` and the linked directive, relevant specification/evidence, scorecard and phase policy. Verify live HEAD and exact-source CI; recover any in-flight operation before continuing the first outstanding authorised task. Preserve all restrictions, reconcile any pending approvals and update canonical records before handing off. Do not repeat historical work or ask me to restate the project.

If a connector, attachment or local machine is unavailable, state the specific missing access and continue safe independent work where possible. The prompt grants no new native, installer, model, migration, owner-data, OS/network or phase authority.

## 5. Audit cadence and drift control

At each meaningful checkpoint perform a small consistency check: current handoff agrees with actual branch/product SHA and CI, first next action is genuinely outstanding, source and official counts have different evidence scopes, approval state is accurate, and current navigation links resolve. Reconcile newly contradictory instructions before continuing. Full documentation audit at each package closure or phase transition, before a significant chat/agent handoff if drift is detected, and when inconsistent status, missing evidence, changed criteria or broken navigation is discovered. A normal clean chat transition needs only the checkpoint check; do not force a full audit every time.

Audit records must specify scope, pre/post source identity, corrected documents, unresolved discrepancies, and preserved evidence. Never erase evidence or award acceptance merely because documentation was cleaned. Retain the current handoff compact (target around 2,000 words or less, not a hard limit that justifies deleting facts). Avoid adding duplicate append-only chronology to the live handoff, README, index, directive or scorecard. If history grows, archive it with immutable links and preserve existing navigational anchors.

[Prior continuity audit](./DOCUMENTATION_AUDIT_B5_CONTINUITY_2026-11-24.md) documents the drift this protocol addresses.

## 6. Active work journal and operation lifecycle

The [active work journal](./ACTIVE_WORK_JOURNAL.md) is the recovery layer between permanent knowledge, live handoff and historical evidence. Read it before the first consequential operation, including in a new chat. Keep one active task (and explicitly listed unresolved operations if any); the journal is a compact overwrite-in-place record, not a chronology. Git preserves its earlier revisions.

| Task state | Meaning |
| --- | --- |
| READY | Next authorised task identified; no consequential operation prepared |
| PREPARED | Task and operation intent durably published; outcome not yet known |
| IN_PROGRESS | Work underway; inspect existing changes before repeating |
| PUBLISHED | Exact source/QA commit is confirmed published; verification not implied |
| VERIFYING | Exact evidence outstanding or running |
| BLOCKED | Required evidence, authority or access missing; name unblock condition |
| CLOSED | Evidence reconciled at stated scope; transfer to next READY task |

For each consequential operation use a stable task ID and unique operation ID; operation states are NONE, PREPARED, ISSUED, UNKNOWN, RECONCILED. A prepared/issued record is not proof an operation happened. An operation can be reconciled as refused, failed, skipped or completed without claiming success. Record unknown outcomes explicitly, not as failed attempts that may be repeated.

**Write ahead:** before publishing a substantial source batch, activating a workflow, issuing any separately approved restricted action, or making a material decision, persist task ID, scope, starting branch/HEAD, product baseline, intended files/target, exact permission state, expected evidence, recovery action and relevant decision links. Batch ordinary small edits inside one prepared task; do not create a documentation commit for each line edit, read-only tool call or unchanged status observation. If local edits are involved, record only safe known paths/state; do not upload secrets or owner data or auto-publish unpublished local work. Keep a safe immutable checkpoint or describe what remains local; inaccessible local files are not recoverable by documentation.

**Publish and reconcile:** tag the consequential Git commit message with task/operation ID, check the expected current HEAD and actual workflow scope, then use a non-force update. Where possible, publish the journal transition and source changes together atomically. If the commit SHA cannot be self-referenced, identify it by parent, operation ID and actual diff; resolve the exact SHA from Git after publishing. For a dispatch, record the exact workflow, approved product SHA, one-use marker and run/attempt ID when known. If interrupted after a push or dispatch but before recording its result, inspect branch history, commits, runs and job logs rather than replaying it. Pending CI remains pending. A failed restricted attempt consumes its approval according to the existing policy; ambiguous dispatch is potentially consumed until independently reconciled. If an owned one-use workflow is still armed, safely disarm it using the known expected HEAD and preserve the actual run evidence; never activate it again to find out whether it ran. If a concurrent edit or unavailable evidence prevents safe disarm, report the blocker without overwriting other changes. Never treat this journal as an approval source.

**Close:** reconcile the operation and evidence, add one terminal receipt to the active package ledger when material, update compact handoff and scorecard only as warranted, then replace the journal with the next READY task. Record pending runs and unresolved operations explicitly before transition; do not close or drop them merely to simplify the handoff. If the user requests another task, checkpoint the current one as paused/blocked with recovery links before switching; resume outstanding work in authorised order.

## 7. Decision records and minimal context loading

[Decision index](./ENGINEERING_DECISIONS_CURRENT.md) links durable technical rationale. Record material decisions in the owning specification or cross-cutting index before consequential action when feasible, including alternatives, rationale, approval state, limitations and reopen condition. Do not store private internal reasoning, credentials or unnecessary personal information. Preserve an explicit distinction between proposed and adopted decisions.

On a fresh session, use AGENTS + compact handoff + active journal as the first context load. Read the applicable protocol/phase-policy and directive sections, relevant specification and exact evidence needed to resolve the current operation before acting. Do not load all historical handoffs or all past CI logs by default. Read the full scorecard only when acceptance work needs it; otherwise use its exact current rows. Retrieve historical records on demand. This compact route is not permission to skip governing constraints.

## 8. Interruption and consistency rehearsals

Use the [recovery checklist and scenarios](./CONTINUATION_RECOVERY_CHECKS.md) at meaningful checkpoints and when an unexpected session transition occurs. It describes deterministic decisions for prepared, uncertain, published, pending, failed, blocked and completed work. It is a process safeguard, not an automatic execution lock or a guarantee that future agents will comply. A new chat needs access to the repository; if that is missing, provide the exact blocker and do not guess. Periodic audits remain necessary.
