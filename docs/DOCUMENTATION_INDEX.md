# PilotODIN | Documentation index

**Current navigation:** 12 November 2026, branch `feature/live-dev-workspace-20261023`. **P4 Target Intelligence ACTIVE**; P1, P2 and P3 closed for bounded development at their recorded modalities. **P4-R01–R06 OPEN**, real-business Gate C UNVERIFIED, historical original whole-app-data integrity STRICT FAIL, P5 NOT AUTHORISED, P8 NOT CERTIFIED. See the live documents for any subsequent state change.

## Current authoritative route, in reading order

1. [Current session handoff](./SESSION_HANDOFF_CURRENT.md) for latest specific checkpoint and next evidence requirement (chronological history, **not** short).
2. [Project status](./PROJECT_STATUS_CURRENT.md) for cross-phase disposition and release restrictions (chronological history).
3. [One-primary-phase and owner closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) for governing authorisation, build freeze and acceptance decisions.
4. [P4 owner acceptance go/no-go](./P4_23_CONSOLIDATED_WINDOWS_ACCEPTANCE_GO_NO_GO_2026-11-09.md), [P4 bounded closure proposal and owner refusal](./P4_17_BOUNDED_DEVELOPMENT_CLOSURE_DECISION_REVIEW_2026-11-09.md), and [P4 evidence/physical native intake](./P4_50_EVIDENCE_INTAKE_AND_SINGLE_NATIVE_READINESS_2026-11-12.md).
5. [Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) and [P4 owner evidence Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9). Do not mistake a draft/CI run for final owner acceptance.

## Current phase evidence and recent checkpoints

- **Prior phase closure:** [P1 development closure register](./P1_CLOSURE_REGISTER_2026-10-28.md), [P2 bounded development closure](./P2_DEVELOPMENT_CLOSURE_2026-11-06.md), [P3 bounded development closure](./P3_DEVELOPMENT_CLOSURE_2026-11-09.md). These are not release certification.
- **P4 safety and provenance:** [P4-24 historical storage drift](./P4_24_STORAGE_DRIFT_ISOLATION_SOURCE_VERIFICATION_2026-11-11.md), [P4-25 WebView process snapshot](./P4_25_WEBVIEW_PROFILE_PROCESS_OBSERVATION_2026-11-11.md), [P4-46 evidence boundary](./P4_46_CLOSURE_EVIDENCE_AND_DECISION_BOUNDARY_2026-11-12.md), [P4-47 one-use native evidence](./P4_47_ONE_APPROVED_UNPACKAGED_NATIVE_CI_ACCEPTANCE_2026-11-12.md).
- **P4-61 owner-approved manual-only Gate C candidate study:** [Frozen rule and constraints](./P4_61_OWNER_APPROVED_MANUAL_CI_GATE_C_FEASIBILITY_2026-11-12.md); [latest P4-64 exact-source study observation](./P4_64_PREPARE_AND_FEATURE_ADVICE_QUALITY_VERSION_BINDING_2026-11-12.md). **Five** GitHub-timestamped rule witnesses, 4 first P1 successes, **1 earlier P1 FAILURE preserved**, 0 independently observed human preflight actions or measured business benefit. **Gate C UNVERIFIED**.
- **P4-67 tested no-fit cross-source verifier:** [Verified P4-67 executable evidence boundaries](./P4_67_NESO_ELEXON_INDEPENDENT_VINTAGE_VERIFIER_2026-11-12.md), [qa/p4_neso standalone script and 11 synthetic tests](../qa/p4_neso/README.md). One-day official Elexon NDF request and DST-aware fail-closed NESO match logic. **No live Elexon record**, external Gate C still UNVERIFIED.
- **P4-70 independently reproduced historical NESO/Elexon as-of values:** [Full byte-hashed 48/48 source field-match and 07:45/08:16 UTC issuance breakdown](./P4_70_NESO_ELEXON_INDEPENDENT_ASOF_FIELD_MATCH_2026-11-12.md). True uploaded-byte comparison; no independent live retrieval, operational benefit, native acceptance or Gate C approval.
- **P4-68 Elexon parser correction:** [Owner-observed `boundary=N` false-negative, source fix and 14/14 local regression tests](./P4_68_ELEXON_NDF_BOUNDARY_PARSING_CORRECTION_2026-11-12.md). Direct fetch succeeded on the owner's computer; no independently reviewed raw JSON or full forecast match yet.
- **P4-66 independent vintage route and cutoff exceptions:** [Elexon historical NDF API, documented ENCC operational roles, and six source-clock exceptions](./P4_66_NESO_OPERATIONAL_OWNER_AND_ELEXON_VINTAGE_ROUTE_2026-11-12.md). External API schema proven; **zero actual cross-source rows verified**, real-business Gate C remains OPEN.
- **P4-65 NESO external case, read-only:** [Official forecast dataset integrity / DST exclusions / no-fit historical benchmark](./P4_65_NESO_DAY_AHEAD_DATA_AND_NO_FIT_PROTOCOL_2026-11-12.md). 98,350 eligible rows across 2,049 days after three quarantined dates; forecast error arithmetic and three inspected historical windows independently verified. Real-business Gate C STILL UNVERIFIED; no fit/native/installer.
- **Gate C and research:** [P4-54 historical calendar baseline](./P4_54_PUBLIC_BIKE_FIXED_ORIGIN_CALENDAR_BASELINE_2026-11-12.md), [P4-55 one approved research fit](./P4_55_ONE_PUBLIC_BIKE_RESEARCH_FIT_2026-11-12.md), [P4-56 GitHub CI use-case feasibility](./P4_56_CI_GATE_C_HISTORY_FEASIBILITY_2026-11-12.md).
- **Latest P4 Prepare source verification:** [P4-64 server/frontend version-pinned advice](./P4_64_PREPARE_AND_FEATURE_ADVICE_QUALITY_VERSION_BINDING_2026-11-12.md), [exact-source P4 CI PASS](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230241556) and [P1 CI PASS](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43230242001). All 10 naturally triggered P1/P2/P3/P4 workflows PASS. Wider BE-024/native remains open.
- **Earlier P4-63 scoped feature advice:** [P4-63 source and CI chronology](./P4_63_PREPARE_FEATURE_ADVICE_SCOPING_AND_SHADOW_OUTCOMES_2026-11-12.md), with the initial P1 FAILED run preserved and corrected test-only P1 PASS.
- **Earlier P4-62 Prepare approval and manual study:** [P4-62 focused report](./P4_62_PREPARE_EXCLUSION_REVIEW_AND_CI_SHADOW_OBSERVATIONS_2026-11-12.md). The first source SHA `bd9e098` had P4 browser-fixture **FAIL**, preserved; corrected source `d248455` [P4 CI SUCCESS](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43220367214) (180 Python, 47 Node, 10 real-HTTP browser), [P1 CI SUCCESS](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43220367222). Two timestamped shadow-rule recommendations; **Gate C still UNVERIFIED**, no owner action/benefit.
- **Earlier P4 structural correctness:** [P4-60 Code/Number-only false readiness fix](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/27d678c4e0046b0f22350367e12bce1ffbf95608), [source CI PASS](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43212425588).
- **Earlier P4 Prepare safety:** [P4-59 backend high-risk predictor acknowledgement](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1221cf9b45e5d92d1b72384f8fc40559d727617f), [exact-source CI PASS](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43210881969). BE-024 wider Prepare/native acceptance remains open.
- **Earlier P4 acceptance-support tools:** [P4-57 local shadow-log validator](./P4_57_LOCAL_SHADOW_DECISION_LOG_VALIDATION_2026-11-12.md), [P4-58 run-attribution fix](./P4_58_SHADOW_STUDY_ATTRIBUTION_IDENTITY_CORRECTION_2026-11-12.md). **No prospective owner evidence, Gate C approval or native acceptance inferred.**
- **Documentation provenance:** [4 November historical cleanup audit](./DOCUMENTATION_AUDIT_2026-11-04.md); [12 November current navigation audit](./DOCUMENTATION_CLEANING_AUDIT_2026-11-12.md).

**Index scope:** A curated current route with a preserved legacy navigation snapshot below, not an exhaustive list of the repository's Markdown files (172 at the pre-cleanup audit baseline). Newer GitHub HEAD, current handoff, owner decisions and verified CI evidence supersede historical status paragraphs. Keep chronological failures and historical acceptance observations intact.

---

## Historical navigation snapshot (4 November 2026, retained for traceability)

**As of 4 November 2026.** The following inventory predates P2/P3 closure and P4 work. It is not a current phase instruction.

**Start here:** [short continuation handoff](./SESSION_HANDOFF_CURRENT.md) · [cross-phase status](./PROJECT_STATUS_CURRENT.md) · [P1 closure matrix](./P1_CLOSURE_REGISTER_2026-10-28.md) · [audit](./DOCUMENTATION_AUDIT_2026-11-04.md).

The 22 October owner-held Master Reconstruction Blueprint is the product specification; do not infer implementation or release acceptance from a design. The 24 October owner-held roadmap DOCX is dated planning. At this historical 4 November checkpoint, the 28 October owner-adopted [phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) recorded **P1 active**; that historical fact is superseded by the current P4 status at the top of this index.

## Current status and governance
- [`SESSION_HANDOFF_CURRENT.md`](./SESSION_HANDOFF_CURRENT.md)
- [`P1_CLOSURE_REGISTER_2026-10-28.md`](./P1_CLOSURE_REGISTER_2026-10-28.md)
- [`PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md`](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md)
- [`PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md`](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md)

## Dated project history and prior entry points
- [`README.md`](../README.md) — historical; not a current task list
- [`STUDIO_README.md`](../STUDIO_README.md) — historical; not a current task list
- [`CONTINUE_HERE.md`](./CONTINUE_HERE.md) — historical; not a current task list
- [`SESSION_HANDOFF_P1_LATEST_2026-10-27.md`](./SESSION_HANDOFF_P1_LATEST_2026-10-27.md) — historical; not a current task list
- [`PILOTODIN_STATUS_REFLECTION_2026-10-26.md`](./PILOTODIN_STATUS_REFLECTION_2026-10-26.md) — historical; not a current task list

## P0 and P1 acceptance / DEV evidence
- [`P0_A2_A3_UI_CLOSEOUT.md`](./P0_A2_A3_UI_CLOSEOUT.md)
- [`P0_A4_SINGLE_PASS_VERIFICATION.md`](./P0_A4_SINGLE_PASS_VERIFICATION.md)
- [`P0_INTERACTIVE_ML_JOURNEY_CURRENT.md`](./P0_INTERACTIVE_ML_JOURNEY_CURRENT.md)
- [`P1_IMPORT_RECOVERY_AND_E2_SPIKE.md`](./P1_IMPORT_RECOVERY_AND_E2_SPIKE.md)
- [`P1_NATIVE_ACCESSIBILITY_QA_2026-11-03.md`](./P1_NATIVE_ACCESSIBILITY_QA_2026-11-03.md)
- [`P1_NATIVE_CLOSE_WINDOWS_ACCEPTANCE_2026-10-28.md`](./P1_NATIVE_CLOSE_WINDOWS_ACCEPTANCE_2026-10-28.md)
- [`P1_RELOCATED_SOURCE_RECOVERY_2026-11-03.md`](./P1_RELOCATED_SOURCE_RECOVERY_2026-11-03.md)
- [`P1_UPLOAD_STAGING_ACCEPTANCE.md`](./P1_UPLOAD_STAGING_ACCEPTANCE.md)

## P2 Deliver, PDF and reporting acceptance
- [`MACRO_A4_DELIVER_ACCEPTANCE.md`](./MACRO_A4_DELIVER_ACCEPTANCE.md)
- [`P2_COMPOSER_BATCH_ACCEPTANCE.md`](./P2_COMPOSER_BATCH_ACCEPTANCE.md)
- [`P2_DEVQA_NATIVE_CHAIN_ACCEPTANCE.md`](./P2_DEVQA_NATIVE_CHAIN_ACCEPTANCE.md)
- [`P2_MIXED_EVIDENCE_DEVQA_ACCEPTANCE.md`](./P2_MIXED_EVIDENCE_DEVQA_ACCEPTANCE.md)
- [`P2_MIXED_EVIDENCE_RISK_FIRST_PLAN.md`](./P2_MIXED_EVIDENCE_RISK_FIRST_PLAN.md)
- [`P2_NATIVE_EXPORT_ACCEPTANCE.md`](./P2_NATIVE_EXPORT_ACCEPTANCE.md)
- [`P2_NATIVE_LIVE_CHAIN_ACCEPTANCE.md`](./P2_NATIVE_LIVE_CHAIN_ACCEPTANCE.md)
- [`P2_PDF_FONT_CONSOLIDATED_RELEASE_DECISION.md`](./P2_PDF_FONT_CONSOLIDATED_RELEASE_DECISION.md)
- [`P2_PDF_FONT_RELEASE_OWNER_DECISION.md`](./P2_PDF_FONT_RELEASE_OWNER_DECISION.md)
- [`P2_PDF_FROZEN_ONEFILE_RESOURCE_DEVQA.md`](./P2_PDF_FROZEN_ONEFILE_RESOURCE_DEVQA.md)
- [`P2_PDF_PRODUCTION_SIDECAR_FONT_GATE.md`](./P2_PDF_PRODUCTION_SIDECAR_FONT_GATE.md)
- [`P2_PDF_RELEASE_FONT_APPROVAL_GATE.md`](./P2_PDF_RELEASE_FONT_APPROVAL_GATE.md)
- [`P2_PDF_UNICODE_FONT_REMEDIATION_PLAN.md`](./P2_PDF_UNICODE_FONT_REMEDIATION_PLAN.md)
- [`P2_PDF_UNICODE_PRODUCTION_INTEGRATION_GATE.md`](./P2_PDF_UNICODE_PRODUCTION_INTEGRATION_GATE.md)
- [`P2_PDF_VISUAL_ACCEPTANCE.md`](./P2_PDF_VISUAL_ACCEPTANCE.md)
- [`P2_REACT_INTEGRATION_ACCEPTANCE.md`](./P2_REACT_INTEGRATION_ACCEPTANCE.md)
- [`P2_REAL_API_INTEGRATION_ACCEPTANCE.md`](./P2_REAL_API_INTEGRATION_ACCEPTANCE.md)
- [`P2_REPORT_DISCLOSURE_AND_PDF_GATE.md`](./P2_REPORT_DISCLOSURE_AND_PDF_GATE.md)
- [`P2_REPORT_OPEN_ACCEPTANCE.md`](./P2_REPORT_OPEN_ACCEPTANCE.md)
- [`P2_REPORT_READ_SAFETY_ACCEPTANCE.md`](./P2_REPORT_READ_SAFETY_ACCEPTANCE.md)

## P3–P5 focused intelligence / task acceptance
- [`P3_DETERMINISTIC_SEMANTIC_PROFILE.md`](./P3_DETERMINISTIC_SEMANTIC_PROFILE.md)
- [`P4_BUSINESS_CONTEXT_ACCEPTANCE.md`](./P4_BUSINESS_CONTEXT_ACCEPTANCE.md)
- [`P4_PREDICTION_TIMING_REVIEW.md`](./P4_PREDICTION_TIMING_REVIEW.md)
- [`P4_TARGET_OPPORTUNITIES_ACCEPTANCE.md`](./P4_TARGET_OPPORTUNITIES_ACCEPTANCE.md)
- [`P4_TWO_AXIS_EVIDENCE_ACCEPTANCE.md`](./P4_TWO_AXIS_EVIDENCE_ACCEPTANCE.md)
- [`P5_COOPERATIVE_TRAINING_CANCELLATION.md`](./P5_COOPERATIVE_TRAINING_CANCELLATION.md)
- [`P5_DURABLE_TRAINING_PROGRESS.md`](./P5_DURABLE_TRAINING_PROGRESS.md)
- [`P5_ML_COORDINATION_FIRST_SLICE.md`](./P5_ML_COORDINATION_FIRST_SLICE.md)

## Research, design, operations and legacy releases
- [`A4_NATIVE_WINDOWS_ONE_PASS.md`](./A4_NATIVE_WINDOWS_ONE_PASS.md)
- [`BUILD_A_VALIDATION.md`](./BUILD_A_VALIDATION.md)
- [`BUILD_B_CANVAS_SPIKE.md`](./BUILD_B_CANVAS_SPIKE.md)
- [`BUILD_C_HYBRID_INTELLIGENCE.md`](./BUILD_C_HYBRID_INTELLIGENCE.md)
- [`BUILD_D_VALIDATION.md`](./BUILD_D_VALIDATION.md)
- [`DESIGN.md`](./DESIGN.md)
- [`DEVQA_PREDICTIVE_FRAMEWORK.md`](./DEVQA_PREDICTIVE_FRAMEWORK.md)
- [`ENGINEERING_EFFICIENCY_WITHOUT_QUALITY_LOSS_RESEARCH_2026-10-28.md`](./ENGINEERING_EFFICIENCY_WITHOUT_QUALITY_LOSS_RESEARCH_2026-10-28.md)
- [`LIVE_DEVELOPMENT.md`](./LIVE_DEVELOPMENT.md)
- [`MACRO_A2_CONSOLIDATED_ACCEPTANCE.md`](./MACRO_A2_CONSOLIDATED_ACCEPTANCE.md)
- [`MACRO_A3_ML_ACCEPTANCE.md`](./MACRO_A3_ML_ACCEPTANCE.md)
- [`MACRO_RELEASE_TEST_REPORT.md`](./MACRO_RELEASE_TEST_REPORT.md)
- [`MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md`](./MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md)
- [`MULTI_AI_RELEASE.md`](./MULTI_AI_RELEASE.md)
- [`PUBLIC_REPOSITORY_AUDIT_2026-11-03.md`](./PUBLIC_REPOSITORY_AUDIT_2026-11-03.md)
- [`QUALITY_INCREMENT1.md`](./QUALITY_INCREMENT1.md)
- [`QUALITY_INCREMENT1_1.md`](./QUALITY_INCREMENT1_1.md)
- [`RESOURCE_AWARE_MODE_DESIGN.md`](./RESOURCE_AWARE_MODE_DESIGN.md)
- [`TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md`](./TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md)
- [`V05_FEATURE_STATUS.md`](./V05_FEATURE_STATUS.md)
- [`V05_RELEASE_TEST_REPORT.md`](./V05_RELEASE_TEST_REPORT.md)
- [`V06_RELEASE_NOTES.md`](./V06_RELEASE_NOTES.md)
- [`V08_RELEASE_TEST_REPORT.md`](./V08_RELEASE_TEST_REPORT.md)
- [`branding/NEURAL_HORIZON_DIRECTION.md`](./branding/NEURAL_HORIZON_DIRECTION.md)

## Preserved verbatim audit-baseline logs
- [Former current handoff, unmodified bytes](./archive/SESSION_HANDOFF_PRE_AUDIT_2026-11-04.md)
- [Former P1 closure register, unmodified bytes](./archive/P1_CLOSURE_REGISTER_PRE_AUDIT_2026-11-04.md)
- [Former long CONTINUE_HERE chronology, unmodified bytes](./archive/CONTINUE_HERE_PRE_AUDIT_2026-11-04.md)
- [Former root README, unmodified bytes](./archive/ROOT_README_PRE_AUDIT_2026-11-04.md)
- [27 October P1 handoff, unmodified bytes](./archive/SESSION_HANDOFF_P1_2026-10-27_VERBATIM.md)

**Inventory note:** The audit's baseline included 69 Markdown documents; this index contains those pre-audit documents plus new audit/status/index pages and archive entries. File links were checked at the file-target level only; anchors and external websites were not verified.
