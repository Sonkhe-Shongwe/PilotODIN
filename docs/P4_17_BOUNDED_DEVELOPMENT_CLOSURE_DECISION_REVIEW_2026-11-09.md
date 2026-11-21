# PilotODIN 1.0 | P4-17 Bounded Development Closure Decision Review

## Owner decision: P4 closure proposal NOT APPROVED (9 November 2026)

After reading the P4-17 proposal to close bounded development with unresolved residuals deferred, the owner explicitly replied **"we shouldnt risk"**. This is interpreted narrowly as **not accepting the proposed P4 closure/deferral now**. It does not claim the owner rejected the feature, demanded zero risk, or authorised a new phase. Do not treat the earlier reviewer recommendation as an owner acceptance.

**Binding disposition:** **P4 ACTIVE / P4-17 CLOSURE NOT APPROVED / P5 NOT AUTHORISED / P8 NOT CERTIFIED**. The original P4 real-world Gate C has **not** been amended or deferred by owner signoff; business/operational suitability remains UNVERIFIED. P4-R01–R06 remain **OPEN**, not accepted closures. Master QA #2 and P4 evidence Issue #9 remain OPEN.

**Next risk-first work, without repetitive owner manual tests:**
1. **P4 correctness and data safety first:** use the existing synthetic suites to consolidate fail-closed negative classifications (76/4, 24/80, unnamed outcomes), stale Quality-version/project isolation, and no unintended training/writes. Preserve test status distinctions: automated PASS is not physical Windows PASS; no direct user data access.
2. **Owner-native parity where unavoidable:** the two source-fixed UI defects (phantom archive banner and unreadable decision evidence), selected-target readability, old-data preservation, and offline/8 GB constraints require a **single justified later consolidated Windows candidate** with appropriate hardware/measurement checks, rather than another ~1.5 GB installer per patch. Do not build or install without explicit separate authorisation.
3. **Gate C before any operational use or P4 acceptance on original terms:** establish a truthful, independently supported decision owner, exact label origin, prediction timing, true grouping/time independence, non-model baseline and expected benefit/cost, fair/lawful purpose. If no suitable real-world case exists, record **UNVERIFIED or NO SUITABLE PREDICTION OBJECTIVE**, not a fabricated PASS or compulsory training.
4. **P4-specific defect triage:** retain medium BE-024 Prepare-controls risk and the native UX reports in master QA #2; escalate any proven high/critical P4 correctness or privacy issue immediately. Keep unrelated critical/high release blockers visible without reclassifying them as P4 defects.

**Acceptance boundary:** Owner rejected *closing with those risks deferred*; it is not permission to abandon CI-first development or to require unlimited manual validation. Resume bounded risk resolution in P4, then prepare a new evidence-based closure proposal for a separate owner decision.

**Review date:** 9 November 2026  
**Authority:** Owner said "okay lets do that" to performing a **consolidated P4 closure review**, not to an already-passed P4 closure decision or authorisation to implement P5.  
**Repository/branch:** `Sonkhe-Shongwe/PilotODIN` / `feature/live-dev-workspace-20261023`  
**Last exact CI-verified P4 application SHA:** [`c40b31c67ff09f3848d2731c0a4b1c058c45f33c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c40b31c67ff09f3848d2731c0a4b1c058c45f33c)  
**Previously completed Windows owner QA binary source:** `bca3c57b94a425cd9ef489726e721328d12c2ead` (not the same as the subsequent source-only UX corrections).  
**Decision state:** **ELIGIBLE FOR EXPLICIT OWNER DECISION ON *BOUNDED DEVELOPMENT* CLOSURE, WITH NAMED RESIDUALS. P4 IS NOT CLOSED BY THIS REVIEW.** This is not operational target suitability, production release, or P5 authorisation.

## 1. What P4 1.0 actually delivers and what it does not

**Proposed frozen P4 development scope:** local read-only, human-controlled Target Intelligence in Prepare. Given a project/Quality version, it names possible classification/regression targets; screens observed labels and structural blockers; presents a deterministic 3-primary plus bounded alternatives queue; explains timing/provenance/record-dependence and independent business-use evidence still required; supports temporary review/defer/decline/abstain and explicit selection; keeps project/version boundaries; protects manual out-of-list inspection and candidate resource limits. It **does not** infer business truth from headers, automatically select a model target, independently verify a real outcome or give permission to fit a model.

| Frozen component | Decision evidence | Reviewer disposition |
| --- | --- | --- |
| P4-01–04 named outcome discovery, classification/regression structural checks, fail-closed screening | [P4-15 regression ledger](./P4_15_CONSOLIDATED_TECHNICAL_ACCEPTANCE_AND_GAP_LEDGER_2026-11-09.md), latest P4 CI #42682493909 | **SCOPED CI PASS** |
| P4-05–06 deterministic queue, owner-described questions, alternatives without false business ranking | Latest P4 CI; owner Windows screenshots showing `churn`, `failure_flag`, `fraud_reported`, `future_cost`, `outcome` | **SCOPED CI + OBSERVED WINDOWS PASS** |
| P4-07 decision-usefulness caveats and repeated-ID aggregate | Owner N3: `account_id` 80 observations, 40 distinct, 40 extra; explicit warning that this does not prove leakage/group truth | **SCOPED CI + OBSERVED WINDOWS PASS; real dependence UNVERIFIED** |
| P4-08 explicit owner review/defer/decline/no-objective, no automatic training | Owner N4 selected `churn`, N5 no-objective cleared it; original Defer/Decline UI choices appeared, full selected-then-decline and persistence scenarios automated | **SCOPED CI + PARTIAL WINDOWS PASS** |
| P4-09 negative cases, project/Quality-version/Origin boundaries | 4/80 minority, 24/80 labels, no named target and 409/403 covered by synthetic Python/real-HTTP browser; owner N7 switch from selected `future_cost` back to unselected classification | **SCOPED CI + PARTIAL WINDOWS PASS; native negative/version cases NOT TESTED** |
| P4-10/16 disposable native QA kit and verifiable Windows package | CI source/install provenance #42621192759; owner verified installer SHA, separate install path/app-local data, old and new desktop EXE hashes, actual P4 Home/Prepare/import | **OBSERVED WINDOWS QA PROVENANCE + BASIC NATIVE INTEGRATION PASS** |
| P4-11–14 manual blocked/out-of-list disclosure and bounded candidate/row/column screening | [P4-15 consolidated automated matrix](./P4_15_CONSOLIDATED_TECHNICAL_ACCEPTANCE_AND_GAP_LEDGER_2026-11-09.md) and current CI; no separate owner-native limit-case execution | **SCOPED CI PASS; native special cases NOT TESTED** |
| P4-15 integrated acceptance and P4-17 exit assessment | Exact-source P4 CI detailed below; this report reconciles owner evidence, residuals and policy | **Engineering reviewed; owner signoff PENDING** |

**Normative distinction requiring owner review:** Original [Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9) makes independently verified real-business Gate C a **P4 closure condition**. This document proposes that **P4 bounded *development* closure** can be separated from **business/deployment suitability**, *if and only if the owner explicitly approves that deferral and residual risk*. Until then, Gate C stays **UNVERIFIED**, not silently removed or passed. No use of real predictions is justified from synthetic tests alone.

## 2. Latest exact-source automated evidence

- [P4 Target Review Queue #42682493909](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42682493909), at **`c40b31c67ff09f3848d2731c0a4b1c058c45f33c`**, **COMPLETED SUCCESS**: **96/96 Python**, **28/28 Node**, TypeScript/Vite production build **PASS**, **8/8 real-HTTP Chromium/Uvicorn** synthetic browser tests. Includes rare-label, insufficient-label, no-name abstention, wide/bounded queue, manual inspect, state/version/Origin cases and the source-layout regression.
- [P1 Isolated Frontend #42682493790](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42682493790), same application source, **COMPLETED SUCCESS**: **163/163 Node**, TypeScript/Vite **PASS**, **5/5 isolated Chromium**. No general P1 re-closure asserted.
- [Windows source-matched QA #42621192759](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42621192759), **COMPLETED SUCCESS at older installed `bca3c57...`**: Windows 2022 disposable NSIS installation, bundled inference/sidecar/loopback checks, compiled-to-installed desktop EXE SHA **MATCH**. The owner independently confirmed that same desktop EXE SHA on their physical Windows PC and preserved original binary hash. This **does not** claim newer UI source fixes ran in that installed Windows build.
- Historical CI failures on `9e6b39...` (missing archive guard declaration) and older Windows QA provenance failures remain real failures. Corrected source `84e589c...` and `c40b31c...` subsequently passed; **do not rewrite history or infer a new native installer build**.
- Subsequent documentation-only commits are not independent tested application SHAs.

## 3. Owner-native milestone evidence, with strict scope

The owner installed the separately identified `pilotODIN-P4-Native-QA` after verifying installer SHA/size and backing up the older app's separate data directory. Observed old desktop EXE SHA256 `b2b18c070214ca92c6f1513c39d1526a7a9ac821c5043c2fe09f7e8e7da63d9` stayed unchanged; installed QA desktop EXE SHA256 `7173b9c0e68295cca6bdf283daf8e61a86934d0575fac9915aea48bc9c009633` matched source-associated Windows CI. Pre-install old-data copy: 320 files / 77,897,688 total bytes, matching aggregate count/size; not an individual-file hash or tested restoration.

**Do not confuse informal N1–N7 conversation labels with the older N1–N10 table in Issue #9.** This consolidated matrix uses the stable [N1–N12 native kit](../qa/p4_native/RESULTS_TEMPLATE.md) and explicitly reconciles them:

| Native kit case | Evidence observed by owner | Honest disposition |
| --- | --- | --- |
| N1: source-provenanced app/startup | Exact old/new hashes, distinct installation and data directory, native Home/Prepare visible | **PASS for installed binary/startup/initial isolation** |
| N2: 80-row classification with alternatives | 80 rows, 7 fields; `churn`, `failure_flag`, `fraud_reported` and `future_cost`, `outcome`; no business approval claimed | **PASS for native classification review UI** |
| N3: repeated account observations | Owner expanded evidence: 80/80 rows, 1 identifier-like header, `account_id` 80 nonmissing/40 distinct/40 extra, correct uncertainty warning | **PASS for native bounded aggregate** |
| N4: choose/defer/decline/clear | Visible prior defer/decline choices, explicit `churn` selection after defer; not every sequence/clear consequence independently replayed | **PARTIAL owner-native; complete synthetic UI/backend regression PASS** |
| N5: explicit no-objective abstention | Owner saw `No prediction target selected ... Preparation is cleared`, selection checkpoint removed | **PASS for native UI; post-action experiment database audit NOT TESTED** |
| N6: numeric regression review | Separate 80-row/3-field `p4_regression.csv`, 0 experiments on Home, possible `future_cost` regression 80/0, manual selection and caveats visible | **PASS for native UI and manual review; prediction value UNVERIFIED** |
| N7: project isolation | Owner switched regression with selected `future_cost` → classification; no regression target or selection checkpoint carried into classification | **PASS for observed selection isolation; temporary disposition deep state NOT TESTED native** |
| N8: rare class 76/4 blocked | Synthetic backend/P4 real-HTTP coverage, no owner import | **AUTOMATED PASS; NATIVE NOT TESTED** |
| N9: 24/80 labelled blocked | Synthetic backend/P4 real-HTTP coverage, no owner import | **AUTOMATED PASS; NATIVE NOT TESTED** |
| N10: no named target abstains | Synthetic backend/P4 real-HTTP coverage, no owner import | **AUTOMATED PASS; NATIVE NOT TESTED** |
| N11: Quality revision and stale results | Synthetic API 409 + browser scope/refresh and version tests; no owner-native Quality revision mutation | **AUTOMATED PASS; NATIVE NOT TESTED** |
| N12: no accidental train/original writes/cloud | P4 browser checks no saved experiments, owner Home initially displayed zero; old EXE SHA unchanged and separate QA app data present; no full post-test db hash, network capture or offline memory test | **PARTIAL; full native audit/OFFLINE/8 GB NOT TESTED** |

Screenshots/observations are recorded as chronological [Issue #9 comments](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9), notably installer identity, N3 [#6749208806](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6749208806), N4 [#6749301514](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6749301514), N5 [#6749352743](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6749352743), N6 [#6749429534](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6749429534), N7 [#6749507414](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9#issuecomment-6749507414). No screenshots were fabricated or uploaded to this public repository.

## 4. Defect and risk triage before any owner closure

Master [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2) retains **35 numbered BE-001–BE-035 issues**, including serious product-wide release blockers. Within the frozen P4 **target discovery/review** scope, this audit found **no confirmed open *critical/high* Target Intelligence defect** in that issue's numbered register. This is not a proof none exists. Retain the named in-scope and adjacent risks:

| Residual | Impact, evidence and precise gate | Classification / owner |
| --- | --- | --- |
| **P4-R01: real outcome and decision evidence** | No independent ground truth for label source, point-in-time predictors, real entity/group/time independence, decision owner, non-model baseline, costs, measured benefit, fairness or lawful use. Original Issue #9 Gate C remains UNVERIFIED. **Cannot assert actual business suitability; must be a condition before real use.** | **Original phase-exit dependency requiring explicit owner deferral approval**; owner + future operational case acceptance |
| **P4-R02: native negative/version parity** | N8–N11 and parts of N4/N7/N12 not separately exercised in installed WebView2, despite green real-HTTP/browser and Python tests. A new native-specific issue would reopen the affected work. | **Untested residual**, owner; one later consolidated native/release milestone, not repeated manual kits |
| **P4-R03: offline/8 GB coexistence** | No owner-observed measured combined native AI/analytics/WebView2 memory, sustained offline performance, background model load or all-operations isolation. Source row budgets are not physical peak-RAM measurements. | **Critical feasibility follow-up**, owner + desktop integration/release milestone, early investigation permitted by policy |
| **P4-R04: two directly observed native UX defects** | False `archived in another window` on empty catalogue and crushed multi-column `Decision usefulness` evidence. Corrected in **source** [`84e589c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/84e589cd15a254d70e178135f9ee79405de321c4) / [`c40b31c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c40b31c67ff09f3848d2731c0a4b1c058c45f33c) with green tests; NOT verified on the owner's older installed QA app. Dense selected-target strip remains an additional readability concern. | **Confirmed UX issues, source-fixed/native-retest pending; medium/UX risk**, owner + next consolidated Windows candidate |
| **P4-R05: BE-024 Prepare interaction** | Legacy medium Prepare UI/expert-control gap. `applyHighRiskExclusionSuggestions()` in current source **merges** suggested exclusions into previously excluded features; old replacement failure is **source-corrected but native not verified**. Per-feature transformation preview and configurable supported preprocessing remain outside the bounded *P4 target recommendation* feature, not falsely complete. | **MEDIUM residual** requiring explicit owner deferral; Prepare/Model/Later integration review, no silent close of BE-024 |
| **P4-R06: preservation proof limit** | QA install retained old EXE SHA and separate QA data identity, old data backup matched aggregate count/bytes; not full post-install per-file database integrity or actual recovery exercise. | **Native integration/release recovery follow-up**, owner |

**Cross-phase critical/high release blockers explicitly retained:** BE-020/021 ODIN local inference/product architecture; BE-027 invalid Predict hour and semantic validity; BE-016/032 tied-median analysis interpretation; BE-028–031 reporting; BE-035 local AI health status, plus other BE issues. They are not reclassified as P4 Target Intelligence defects and are **not waived for product release**. Critical/high safety defects discovered in any previously bounded-closed phase still trigger the policy's safety exception. The master issue stays OPEN.

## 5. Six binding closure conditions, assessed honestly

| Policy exit condition | Assessment before owner decision |
| --- | --- |
| 1. Frozen scope and critical journeys mapped to evidence | **MET FOR PROPOSED BOUNDED DEVELOPMENT SCOPE**, table §1 + synthetic/native matrix §3; proposed business Gate C deferral is **not yet owner-approved** |
| 2. No open critical/high *in-scope*; medium/low residuals accepted by owner | **NO IDENTIFIED CRITICAL/HIGH IN FROZEN P4 REGISTER**, not universal proof; P4-R04/05 medium and other residuals await explicit owner acceptance |
| 3. Essential browser/native journey evidence | **MET FOR CORE OWNER WINDOWS PATHS WITH DOCUMENTED LIMITS**; physically tested N1–N3, N5–N6, N7 selected-target isolation and N4 partially; negative cases version/native not field-tested |
| 4. Changed code passed focused checks and build | **MET for `c40b31c67ff09f3848d2731c0a4b1c058c45f33c`**: 96 Python, 28 Node, Vite, 8 real-HTTP browser; adjacent P1 163 Node, Vite, 5 browser. Subsequent docs do not imply a new tested app |
| 5. Durable data/isolation/consent/cancel safety | **MET IN SCOPED SYNTHETIC API/BROWSER AND INITIAL OWNER NATIVE PROVENANCE**; physical full old-data/file audit and OS resource/offline gate open |
| 6. QA #2 + authoritative handoffs + exact SHAs + owner approval | **DOCUMENTATION/QA UPDATE REQUIRED BY THIS REVIEW**; **explicit final owner P4 close/deferral decision PENDING** |

## 6. Recommendation, owner decision and post-review boundary

**Reviewer recommendation:** Offer the owner the option to approve **P4 CLOSED FOR BOUNDED DEVELOPMENT ONLY**, subject to an express and conscious scope/risk decision:

1. Freeze P4 as a **safe, local, human-reviewed *hypothesis discovery* and *structural screening* capability**, NOT a certified business-value recommendation or permission to train/deploy.
2. Explicitly accept deferral of original real operational **Gate C** to a named future case-by-case **decision/use approval before using any real-business predictive objective**. **This is a scope change, not a claim that Gate C passed.**
3. Explicitly accept P4-R02–R06 with the named future verification gates and original issue severity intact. Any new critical/high P4 correctness, integrity or security defect reopens the relevant requirement.
4. Keep master QA #2 OPEN, owner evidence Issue #9 OPEN or marked as a **deferred phase-exit evidence register**, and P8 release NOT CERTIFIED. P5 is **not** authorised by closure itself.

**No owner approval of those conditions has been given in this turn.** The words "okay lets do that" authorised producing *this review*. Therefore the **recorded phase remains P4 ACTIVE / CLOSURE PROPOSED AWAITING OWNER DECISION**. P5 remains NOT AUTHORISED. A later explicit owner approval would require a separate closure record noting exactly what residuals were accepted and updating both handoffs and the QA register; rejection would leave P4 OPEN with a focused next dependency. No installer rebuild, model training, owner real-data operations, automatic phase transition or release is performed by this review.
