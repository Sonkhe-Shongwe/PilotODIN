# PilotODIN | Engineering decision index and cross-cutting decisions

This is an index of decisions, not a parallel requirements document. The Master Reconstruction Blueprint and explicit owner decisions remain normative. The relevant specification owns technical contracts; the phase policy owns permissions; the live handoff owns next work.

## Existing controlling decisions

| Area | Authoritative record |
| --- | --- |
| Product scope and remediation sequence | [Product-first directive](./PILOTODIN_PRODUCT_FIRST_IMPLEMENTATION_DIRECTIVE_CURRENT.md) and [architecture review](./PILOTODIN_PRODUCT_ARCHITECTURE_REVIEW_AND_REMEDIATION_2026-11-24.md) |
| Storage and lifecycle | [Package A specification](./PILOTODIN_PACKAGE_A_STORAGE_LIFECYCLE_IMPLEMENTATION_SPEC_2026-11-24.md) |
| Durable data integrity | [Package B specification](./PILOTODIN_PACKAGE_B_DURABLE_DATA_INTEGRITY_SPEC_2026-11-24.md) |
| Resource/trust and build inputs | [Package C specification](./PILOTODIN_PACKAGE_C_RESOURCE_TRUST_SPEC_2026-11-24.md), [C-D08 build inputs](./PILOTODIN_PACKAGE_C_RESOURCE_TRUST_SPEC_2026-11-24.md#7-c5-reproducible-build-inputs) |
| G2 blocked evidence method | [G2 consolidated decision](./P4_R02_5_G2_CONSOLIDATED_CLOSURE_DECISION_2026-11-24.md) |
| Acceptance and approval boundaries | [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md), [scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) |

## CONT-D01 | Interruption-resilient continuation

- **Date / status:** 24 November 2026; adopted by owner request to implement the proposed continuity improvements.
- **Problem:** planned handoff was strong, but important in-flight work might exist only in an interrupted chat. The prior documentation audit demonstrated status drift caused by repeated receipts.
- **Decision:** one replace-in-place work journal, pre-operation intent, stable task and operation IDs, Git evidence reconciliation, and single canonical receipt. The protocol requires a checkpoint before consequential actions and a post-operation checkpoint. Permanent decision rationale stays in its owning specification or this index for cross-cutting process decisions.
- **Alternatives considered:** transcript-dependent recovery (fragile and context-heavy); duplicate full histories in all live documents (drift); new database/service or automatic native operation (unnecessary scope and dependencies). Retain the existing Git-backed documentation and add minimal structured state.
- **Limits:** no guaranteed recovery of private reasoning, unsaved local edits, inaccessible tools, or external actions that leave no verifiable receipt. Expected-HEAD checks are optimistic concurrency controls, not exclusive locks. Ambiguous restricted dispatch is treated as potentially consumed, not permission to retry.
- **Verification:** [recovery checks](./CONTINUATION_RECOVERY_CHECKS.md); [journal](./ACTIVE_WORK_JOURNAL.md); [protocol](./CONTINUATION_PROTOCOL_CURRENT.md). No product or acceptance change.

## Decision recording rule

For a material design, safety, scope or evidence-method decision, record an ID, date, status (proposed/accepted/superseded/blocked), question, selected option, rejected alternatives, rationale, affected invariants, limitations, evidence, approval requirement and reopen condition. Write it before a consequential action where feasible; link from the journal. If an existing specification already owns it, update that specification and add a link here only if cross-cutting navigation needs it. Preserve superseded decisions and point to the replacement. A proposed method or agent recommendation never substitutes for owner acceptance or new authority.

## Package C decision references

[Integrated Package C specification](./PILOTODIN_PACKAGE_C_RESOURCE_TRUST_SPEC_2026-11-24.md) owns C-D01 through C-D09: coordinator, owned control bridge, data priority, async inference, explicit dev trust, settings writer, consent correction, build inputs and the owner-approved pinned own-job observation mechanism. These are bounded engineering design decisions with compatibility gates, not implementation/acceptance or new authority. [Evidence ledger](./PILOTODIN_PACKAGE_C_EVIDENCE_2026-11-24.md).

C-D08-R1 (26 November; planning adopted, shared-core implementation PROPOSED pending exact synthetic CI): [26 November C5 architecture/readiness review](./C5_ARCHITECTURE_READINESS_REVIEW_2026-11-26.md#2-layered-architecture-and-trust-boundary-specification) records responsibility separation, narrow shared-core proposal and evidence/byte-cache boundaries. Existing C-D08 remains normative; no new execution authority or score. Alternatives and reopen condition are in the linked review. [Consistency audit](./DOCUMENTATION_AUDIT_C5_R1_READINESS_2026-11-26.md).

C-D08-R2-RETENTION (26 November; design selected, actual custody/publication BLOCKED): [durable notice evidence custody](./PILOTODIN_C5_REPRODUCIBLE_BUILD_INPUTS_IMPLEMENTATION_SPEC_2026-11-25.md#c5-r2--durable-notice-evidence-custody-26-november). Original exact receipt ZIP plus independently verified settlement and backup in approved private storage; public artifact/log disclosure requires prior separate review. No automatic publication, retry or destination assumption. R3 blocked pending viable route and exact provisioning; normative C-D08 unchanged.

C-D08-R2-FINAL (26 November; engineering review complete, operational NO-GO): [final C5-R2 readiness audit](./C5_R2_FINAL_READINESS_AUDIT_2026-11-26.md). Exact disarmed source/synthetic evidence accepted within scope; no new acceptance points. Private execution and custody route preferred but not authorised; conditional public route requires independently reviewed disclosure rights before upload. Independent expectation provisioning, prelaunch/source/trigger review and exact disarm required. No fresh acquisition proposal before these prerequisites; C-D08 unchanged.

C-D08-R2-PUBLIC-ROUTE (26 November; owner repository strategy reaffirmed, public evidence route selected for further review): [focused public licence/evidence review](./C5_PUBLIC_REPOSITORY_LICENCE_EVIDENCE_REVIEW_2026-11-26.md). Supersedes default private execution/vault preference in C-D08-R2-RETENTION and C-D08-R2-FINAL. Keep existing repo public during development; at project completion full repo private and separate public demo, separately approved. No blanket raw notice publication clearance or new evidence-method/operation authority; exact independent replay/provisioning unchanged. No new repo or private infrastructure by default.
