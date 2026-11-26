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


C-D08-R2-PUBLIC-ONLY (26 November; owner decision reaffirmed and controlling): [public-only development route](./C5_PUBLIC_REPOSITORY_LICENCE_EVIDENCE_REVIEW_2026-11-26.md#9-controlling-public-only-development-route-26-november). Supersedes section 7 local custody preference and R8 request for a route decision. No private infrastructure prerequisite. Prepare bounded hosted discovery-only synthetic adapter; no evidence-method relaxation, no blanket publication or acquisition approval. Existing public repository stays public until completion; later private full repo and separate public demo remain separately scoped.


C-D08-R2-EXACT-PATH (26 November; PROPOSED, owner policy decision pending): [bounded real-policy integration design](./C5_PUBLIC_REPOSITORY_LICENCE_EVIDENCE_REVIEW_2026-11-26.md#19-bounded-real-policy-integration-design-26-november). Exact artifact/ordinary-member-only exception, isolated versioned source/receipt binding, strict non-target/historical replay, no path normalization or broad allowlist. Synthetic prototype verified 279 tests per platform, not actual member confirmation. Narrow 15-row discovery suffix proposed, not full evidence or execution approval. Preserve all C-D08, public-only direction and independent raw evidence/disclosure requirements. Adoption for disarmed source integration requires explicit owner decision; actual acquisition separately authorised after readiness. No source/acceptance credit.


C-D08-R2-EXACT-PATH approval (26 November): owner explicitly stated "I approve the exact-artifact SciPy path exception for disarmed source integration and synthetic verification only. No actual acquisition or activation is authorised." This adopts only the narrow disarmed source design in section 19, not the proposed live suffix, separate diagnostic cap, publication, evidence-method change or actual execution. All 19 restricted approvals remain consumed/disarmed. Prepared operation C5-R2-EXACT-PATH-INTEGRATION-20261126 in journal; historical proposed decision retained above.


C-D08-R2-EXACT-PATH source integration checkpoint (26 November; approved disarmed scope, first batch verified): [exact results and outstanding contract work](./C5_PUBLIC_REPOSITORY_LICENCE_EVIDENCE_REVIEW_2026-11-26.md#20-owner-approved-disarmed-source-integration-26-november). 296 tests per platform, pinned real plan and synthetic-only settlement/receipt, real frontdoor refuses. Complete real receipt/settlement and transitive hosted pin contract before readiness review. No actual acquisition approval, publication, or acceptance change.
