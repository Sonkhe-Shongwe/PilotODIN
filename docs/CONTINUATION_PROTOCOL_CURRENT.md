# PilotODIN | Seamless continuation protocol

**Standing process | 24 November 2026.** Applies to every meaningful engineering checkpoint, chat/tab/model change and Codex handoff. This is a continuity rule, not new execution authority or a change to product scope, phase, acceptance or approval requirements.

## 1. Recover before acting

1. Query the live GitHub branch `feature/live-dev-workspace-20261023`, not default main. If working locally, independently inspect branch, HEAD and dirty state before edits; never infer that owner-local work is published or clean.
2. Read [compact current handoff](./TAB_MIGRATION_HANDOFF_CURRENT.md) first, then [product-first directive](./PILOTODIN_PRODUCT_FIRST_IMPLEMENTATION_DIRECTIVE_CURRENT.md), relevant package specification/evidence ledger, and [official scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard). The original Master Reconstruction Blueprint and explicit owner decisions remain normative; [phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) governs authority.
3. Reconcile exact published product SHA, documentation HEAD, pending CI run/job IDs and current results, consumed/disarmed approvals, blockers, open acceptance criteria and the first outstanding action. Read logs for consequential failures or claimed gate completion. A branch HEAD newer than the last tested product SHA is not evidence of a new test pass. If GitHub is inaccessible, state what is unverified; do not invent state.
4. Generic "next" or "continue" means execute the highest-value outstanding authorised task, not recap the whole project, replay history, start a new phase or grant restricted permissions.

## 2. One owner per information type

| Record | Owns | Update when |
| --- | --- | --- |
| Compact migration handoff | Latest product SHA, live source progress, pending checks, blocker, approval state, precise next action and links | Meaningful checkpoint, including dispatch/result, failed or blocked work, scope change, or handoff |
| Active package evidence ledger (linked by handoff) | Exact receipts: product/test SHA, run/job IDs, result, counts, scope, limitations, artifacts, failure history | New evidence or a material correction; append a single dated receipt |
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

**Standard new-chat prompt:** Continue PilotODIN 1.0 from the current live GitHub handoff on `feature/live-dev-workspace-20261023`. Read `AGENTS.md`, `docs/TAB_MIGRATION_HANDOFF_CURRENT.md` and the linked directive, relevant specification/evidence, scorecard and phase policy. Verify live HEAD and exact-source CI; continue the first outstanding authorised task. Preserve all restrictions, reconcile any pending approvals and update canonical records before handing off. Do not repeat historical work or ask me to restate the project.

If a connector, attachment or local machine is unavailable, state the specific missing access and continue safe independent work where possible. The prompt grants no new native, installer, model, migration, owner-data, OS/network or phase authority.

## 5. Audit cadence and drift control

At each meaningful checkpoint perform a small consistency check: current handoff agrees with actual branch/product SHA and CI, first next action is genuinely outstanding, source and official counts have different evidence scopes, approval state is accurate, and current navigation links resolve. Reconcile newly contradictory instructions before continuing. Full documentation audit at each package closure or phase transition, before a significant chat/agent handoff if drift is detected, and when inconsistent status, missing evidence, changed criteria or broken navigation is discovered. A normal clean chat transition needs only the checkpoint check; do not force a full audit every time.

Audit records must specify scope, pre/post source identity, corrected documents, unresolved discrepancies, and preserved evidence. Never erase evidence or award acceptance merely because documentation was cleaned. Retain the current handoff compact (target around 2,000 words or less, not a hard limit that justifies deleting facts). Avoid adding duplicate append-only chronology to the live handoff, README, index, directive or scorecard. If history grows, archive it with immutable links and preserve existing navigational anchors.

[Prior continuity audit](./DOCUMENTATION_AUDIT_B5_CONTINUITY_2026-11-24.md) documents the drift this protocol addresses.
