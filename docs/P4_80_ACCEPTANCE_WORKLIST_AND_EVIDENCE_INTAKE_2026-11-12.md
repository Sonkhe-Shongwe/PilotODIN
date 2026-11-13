# PilotODIN 1.0 | P4-80 Acceptance worklist and independent-evidence intake

**13 November 2026 scope update:** The owner moved Gate C to approval of a specific real-world prediction use. P4 engineering closure now proceeds against R02–R06 and the phase exit criteria. [Owner decision](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md#13-november-2026--owner-decision-on-gate-c).

**Checkpoint:** 12 November 2026. **Type:** documentation-only coordination milestone, **not** a product implementation, acceptance result or authority to execute native/ML operations. **Authoritative branch:** `feature/live-dev-workspace-20261023`. **Latest checked application/test source:** [`db811488`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/db811488cef9a53b53736ff5d42d6643f4853ac3); [P4 #43299568196](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568196) passed 183 Python, 60 Node, TS/Vite, 11/11 disposable real-HTTP Chromium and synthetic Windows safety; [P1 #43299568087](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568087) passed 187 Node, TS/Vite, 7/7 Chromium. [Prior docs-only HEAD `d876b532`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d876b5324a62b1e546724eca3f0419d62b38d238). These do **not** establish P4 operational/native acceptance.

**Binding governance:** [P4-17 owner risk-deferral refusal](./P4_17_BOUNDED_DEVELOPMENT_CLOSURE_DECISION_REVIEW_2026-11-09.md), [P4-46 hard-stop boundary](./P4_46_CLOSURE_EVIDENCE_AND_DECISION_BOUNDARY_2026-11-12.md), [P4-50 independent evidence intake](./P4_50_EVIDENCE_INTAKE_AND_SINGLE_NATIVE_READINESS_2026-11-12.md), [P4-71 limited actual native boot](./P4_71_ONE_OWNER_APPROVED_WINDOWS_NATIVE_QA_RESULT_2026-11-12.md), [existing native test kit](../qa/p4_native/README.md) / [results template](../qa/p4_native/RESULTS_TEMPLATE.md), [master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2), [owner P4 evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9).

## A. Single risk checklist: existing evidence is not remaining acceptance

| Gate | Existing verifiable evidence | Specific missing proof | Next safe action / dependency | Current verdict |
| --- | --- | --- | --- | --- |
| **R01 / Gate C:** real-world prediction use | Deterministic target review and historical research | Independently checkable decision owner and intervention, outcome provenance, as-of inputs, suitable evaluation, baseline and measured benefit, and permitted use | Use §B when a specific real-world prediction use is proposed | **UNVERIFIED / REQUIRED BEFORE REAL USE** |
| **R02:** native negative and Quality-version parity | P4 source/browser tests including rare class 4/80, sparse labels 24/80, unnamed target, 409 and project isolation; partial earlier owner-native journey | Current-source actual WebView2 N8–N11 and incomplete N4/N7/N12 | Only in **one separately authorised isolated native session** using existing N1–N12 kit | **OPEN / NATIVE NOT TESTED** |
| **R03:** offline 8 GB coexistence | Limited hosted native boot/WebView process evidence; resource estimators are not RAM measurements | Physical 8 GB Windows, actual offline local Qwen + WebView2 + backend/analytics, sustained process/RAM and workload observations | Owner-provided eligible hardware/runtime and separately approved measured test; preagree workload, duration and stop limits | **OPEN / NOT TESTED** |
| **R04:** current native UX | False archive alert and compressed decision-evidence display source-fixed, browser checks pass | Actual current-source native readability of target strip, review/abstain, archive warning and evidence panels | Capture screenshots and source/native SHA **only after authorised isolation preflight** | **OPEN / NATIVE RETEST PENDING** |
| **R05 / BE-024:** Prepare review | Additive high-risk exclusions, per-feature audit, numeric median/mean and categorical mode/marker are source/browser verified; saved-history visibility tested with synthetic GET overlays | Accepted final required scope for per-field controls, and current-source native controls/UX and versions | Confirm **exact mandatory acceptance scope** before freezing changes; test controls as part of consolidated native session; do not call global choices full per-column support | **OPEN / PARTIAL SOURCE EVIDENCE** |
| **R06:** original app-data preservation | Independent preserved backup and original EXE matched; original `data/` subtree 0 file differences in owner observation; isolated runner/WebView evidence | Whole original app-data historical **STRICT FAIL**, 320 backup vs 346 observed: 30 added + 40 modified + 4 missing = 74 differences; historical writer **UNKNOWN**. Separate prospective non-interference not proven | **Non-intrusive evidence intake in §C**. Only already-existing historical attribution if available; later separately approved independent pre/post original-tree comparison | **OPEN / HISTORICAL STRICT FAIL** |

### Rules for interpreting the matrix

- **PASS** applies only to the tested *modality and exact source*, never to a different Windows build or business use. Use **UNVERIFIED**, **NOT TESTED**, **BLOCKED** and **FAIL** distinctly.
- A later prospective no-change check cannot retroactively make the historic 74-item difference a PASS. Historical evidence and owner acceptance remain separate.
- No real model fit, app/database access, native compilation, installer work, P4 closure, P5 start or risk waiver is authorised by this worklist.
- Reopen product source changes only for a reproducible defect or independently approved necessary P4 requirement. Existing [P4-79 browser](./P4_79_SAVED_EXPERIMENT_READ_ONLY_BROWSER_ACCEPTANCE_2026-11-12.md) already covers historical strategy-panel display without fitting.

## B. Gate C owner/decision evidence intake (safe to complete without data uploads)

**Purpose:** verify one genuine, permitted workflow before its predictions inform a real decision. Fill **NOT SUPPLIED** for unknown facts. Use **NOT APPLICABLE** with a reason only where it applies. Keep personal information and proprietary records private. Initial triage may use a source citation or non-sensitive description. A PASS requires independently checkable evidence.

| Required evidence | Field to complete in a private working record | Acceptance test / responsible source |
| --- | --- | --- |
| **B1 Decision owner and rights** | Organisation/role: **NOT SUPPLIED**; permission to use the data and decision: **NOT SUPPLIED** | An accountable person with authority over the workflow and permission to use the data. The PilotODIN owner can fill this role for a workflow they actually run. |
| **B2 Action at prediction time** | Specific intervention and decision cutoff: **NOT SUPPLIED** | A decision that can actually change at the prediction moment, with known users and alternatives |
| **B3 True label and lineage** | Exact outcome unit/time, label system, reporting delay, audit reference: **NOT SUPPLIED** | Independently checkable historic outcomes, provenance and whether labels arrive after action |
| **B4 Feature availability as-of** | Cutoff clock/time zone, point-in-time field snapshots and latency: **NOT SUPPLIED** | Each candidate predictor provably available before the decision, not retrospectively revised or leaked |
| **B5 Dependence and evaluation** | Row/entity grain, repeated entities, grouping/time split, leakage controls: **NOT SUPPLIED** | Predeclared separation reflecting real deployment, no temporal or cross-entity leakage |
| **B6 Existing process baseline** | Real current policy/rule, comparable historical period, performance and evidence: **NOT SUPPLIED** | Independent non-model reference on a fair comparable horizon, not holdout-selected after seeing model outcomes |
| **B7 Costs and observed benefit** | Benefit unit and error/intervention costs, comparison design, independent observations: **NOT SUPPLIED** | Measurable *decision utility*, not just predictive MAE/F1, with owner signoff |
| **B8 Privacy, fairness, oversight** | Intended subjects, rights, explanation/appeals, potential adverse effects and safeguards: **NOT SUPPLIED** | Lawful permission and risk review, especially if real people could be affected |

**Gate C intake decision (not owner signoff):** `NOT SUPPLIED / INDEPENDENT REVIEW REQUIRED / NO SUITABLE PREDICTION OBJECTIVE / VERIFIED WITH EVIDENCE`. **Current: NOT SUPPLIED**. The public UCI bike and NESO/Elexon studies are research, not proof of an independent operational decision-owner contract or measured usefulness. Any future true verification requires a new evidence record and separate owner decision. **Do not create a training job to fill gaps.**

## C. R06 non-intrusive incident evidence intake

**Known reference, do not change:** original backup MATCH; old production EXE MATCH; original `data/` subtree scoped file comparison 0 difference; entire original app-data tree **FAIL** (320 reference files, 346 observed, 74 file differences), observed 74 path-pattern-based WebView/cache *candidates*, historical writer **UNKNOWN**. None of the folder names proves harmlessness or writer identity.

**Only optional owner evidence already created at the time of the incident:**

| Question | State without scanning/changing owner device |
| --- | --- |
| Does an **already-existing**, timestamp-relevant file-write/process audit exist? | **UNKNOWN** (none supplied in repo/QA record) |
| Was relevant object/process auditing enabled **before** the changes and retained? | **UNKNOWN** |
| Can any existing record link **event time + affected original file + executable/process identity** to the same incident? | **NOT SUPPLIED** |
| Is a verifiable chain of custody / independent source available for review without publishing raw private paths? | **NOT SUPPLIED** |
| If pre-existing evidence is unavailable, what is the proper verdict? | **HISTORICAL WRITER UNRECOVERABLE FROM CURRENT EVIDENCE; R06 OPEN; STRICT FAIL PRESERVED** |

**Do not** activate auditing retrospectively, request elevation, install forensic utilities, copy private logs into public GitHub, scan the original app tree, run the old EXE to test it, delete browser caches, restore or move data, rebaseline, rewrite the historical verdict, or run comparator scripts as a consequence of this document.

A **separate, future, explicitly approved** native isolation study may compare trusted independent read-only original EXE/full-tree snapshots before and after the disposable run. Any unexpected change means **STOP / FAIL**. Prospective no-change evidence can help incident disposition but **cannot** identify a writer from months earlier or justify a silent waiver.

## D. Consolidated native acceptance is a conditional downstream task

**Current state: BLOCKED for new execution.** [P4-71](./P4_71_ONE_OWNER_APPROVED_WINDOWS_NATIVE_QA_RESULT_2026-11-12.md) compiled a single unpackaged isolated Windows debug app and confirmed boot + five WebView processes, but UI CDP discovery blocked N2–N12. That approval was **one-use and consumed**; the workflow is disarmed. A generic `next` or this checklist does not provide new native-build authority.

1. **Prerequisite:** explicit separate owner approval for any fresh unpackaged native compilation; maintain the owner's **no intermediate installers through P4–P7** directive. A new distributed EXE, MSI or NSIS is not authorised. If no approval, keep R02/R04/R05 native evidence **BLOCKED / NOT TESTED**.
2. **Preflight before any future permitted run:** freeze exact source commit and trusted native binary SHA; prove unique QA app ID, WebView profile, disposable `PILOTODIN_HOME`, no original-root paths, no inherited user data, no unintended cloud access. If any mismatch: **STOP**.
3. **Single bounded native journey:** use [existing N1–N12 kit](../qa/p4_native/README.md) and [result template](../qa/p4_native/RESULTS_TEMPLATE.md), not new CSV imports against owner projects. Include R04 UX and R05 Prepare controls. Record case-level exact source/native SHA, timestamps, actual observed PASS/FAIL/BLOCKED/NOT TESTED.
4. **Physical R03 check separately conditional:** genuine 8 GB hardware with available, permitted local Qwen + WebView2 + backend under offline conditions, agreed resource thresholds and workload. If prerequisites unavailable, it stays **NOT TESTED**, not a proxy PASS.
5. **Prospective R06 only on distinct separate authorisation:** original baseline remains read-only and immutable; pre/post comparison is prospective, not historical explanation. Record a potential new FAIL immediately.
6. **After observations:** attach only redacted, non-sensitive evidence references to [P4 owner Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9), confirmed defects to [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2), update status/handoff; require a new explicit **owner P4 closure decision** before P5 could be separately authorised.

## E. Practical order for the next sessions

| Priority | Next deliverable | Who supplies the missing fact | Stop / done rule |
| --- | --- | --- | --- |
| **Now** | Reconcile R02–R05 source and browser coverage and identify the exact remaining Windows checks, including the required Prepare controls | Engineering review of existing evidence | Use the existing N1–N12 kit. Fix reproducible defects within scope. |
| **R06 evidence** | Assess any already-existing incident-time writer evidence if available | Owner or existing evidence records | With current evidence, retain historical **STRICT FAIL** and writer **UNKNOWN**. |
| **Native and physical acceptance** | One isolated current-source Windows session, plus a physical offline 8 GB check when the prerequisites are met | Suitable environment and existing authorisation requirements | Record each result. Missing prerequisites leave the applicable checks **BLOCKED / NOT TESTED**. |
| **P4 engineering closure** | Review R02–R06 and the phase exit criteria | Owner signs off on the recorded results and any explicit risk dispositions | P4 closure requires a separate decision. |
| **Before real-world prediction use** | Verify one proposed decision using §B | Accountable decision owner and independently checkable evidence | Gate C stays **UNVERIFIED** until the evidence supports use. |

**P4 status after the 13 November scope decision:** ACTIVE. R02–R06 are open, Gate C is unverified for real use, and the historical whole-tree result is STRICT FAIL. P5 is not authorised and P8 is not certified. This worklist update records no new application test result.
