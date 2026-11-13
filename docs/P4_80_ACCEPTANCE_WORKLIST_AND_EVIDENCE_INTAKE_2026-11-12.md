# PilotODIN 1.0 | P4-80 Acceptance worklist and independent-evidence intake

**13 November 2026 scope update:** The owner moved Gate C to approval of a specific real-world prediction use. P4 engineering closure now proceeds against R02–R06 and the phase exit criteria. [Owner decision](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md#13-november-2026--owner-decision-on-gate-c).

**Checkpoint:** 12 November 2026. **Type:** documentation-only coordination milestone, **not** a product implementation, acceptance result or authority to execute native/ML operations. **Authoritative branch:** `feature/live-dev-workspace-20261023`. **Latest checked application/test source:** [`db811488`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/db811488cef9a53b53736ff5d42d6643f4853ac3); [P4 #43299568196](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568196) passed 183 Python, 60 Node, TS/Vite, 11/11 disposable real-HTTP Chromium and synthetic Windows safety; [P1 #43299568087](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568087) passed 187 Node, TS/Vite, 7/7 Chromium. [Prior docs-only HEAD `d876b532`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d876b5324a62b1e546724eca3f0419d62b38d238). These do **not** establish P4 operational/native acceptance.

**Binding governance:** [P4-17 owner risk-deferral refusal](./P4_17_BOUNDED_DEVELOPMENT_CLOSURE_DECISION_REVIEW_2026-11-09.md), [P4-46 hard-stop boundary](./P4_46_CLOSURE_EVIDENCE_AND_DECISION_BOUNDARY_2026-11-12.md), [P4-50 independent evidence intake](./P4_50_EVIDENCE_INTAKE_AND_SINGLE_NATIVE_READINESS_2026-11-12.md), [P4-71 limited actual native boot](./P4_71_ONE_OWNER_APPROVED_WINDOWS_NATIVE_QA_RESULT_2026-11-12.md), [existing native test kit](../qa/p4_native/README.md) / [results template](../qa/p4_native/RESULTS_TEMPLATE.md), [master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2), [owner P4 evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9).

## A. Single risk checklist: existing evidence is not remaining acceptance

| Gate | Existing verifiable evidence | Specific missing proof | Next safe action / dependency | Current verdict |
| --- | --- | --- | --- | --- |
| **R01 / Gate C:** real-world prediction use | Deterministic target review and historical research | Independently checkable decision owner and intervention, outcome provenance, as-of inputs, suitable evaluation, baseline and measured benefit, and permitted use | Use §B when a specific real-world prediction use is proposed | **UNVERIFIED / REQUIRED BEFORE REAL USE** |
| **R02:** native negative and Quality-version parity | P4 source/browser tests including rare class 4/80, sparse labels 24/80, unnamed target, 409 and project isolation; partial owner and hosted Windows observations | Current-source N8–N11 and incomplete N4/N7/N12 | Continue the existing N1–N12 kit in a separately authorised isolated session with native dialog input | **OPEN / PARTIAL NATIVE EVIDENCE** |
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

**Current state: partial Windows observations recorded.** The approved 13 November run reached the actual Tauri WebView2. It stopped at the first project switch with the native consent path pending. See the run record below. Both one-use workflows are disarmed and the build approvals have been consumed.

1. **Prerequisite:** explicit separate owner approval for any fresh unpackaged native compilation; maintain the owner's **no intermediate installers through P4–P7** directive. A new distributed EXE, MSI or NSIS is not authorised. Record any outstanding cases as **BLOCKED / NOT TESTED** until they are observed.
2. **Preflight before any future permitted run:** freeze exact source commit and trusted native binary SHA; prove unique QA app ID, WebView profile, disposable `PILOTODIN_HOME`, no original-root paths, no inherited user data, no unintended cloud access. If any mismatch: **STOP**.
3. **Single bounded native journey:** use [existing N1–N12 kit](../qa/p4_native/README.md) and [result template](../qa/p4_native/RESULTS_TEMPLATE.md), not new CSV imports against owner projects. Include R04 UX and R05 Prepare controls. Record case-level exact source/native SHA, timestamps, actual observed PASS/FAIL/BLOCKED/NOT TESTED.
4. **Physical R03 check separately conditional:** genuine 8 GB hardware with available, permitted local Qwen + WebView2 + backend under offline conditions, agreed resource thresholds and workload. If prerequisites unavailable, it stays **NOT TESTED**, not a proxy PASS.
5. **Prospective R06 only on distinct separate authorisation:** original baseline remains read-only and immutable; pre/post comparison is prospective, not historical explanation. Record a potential new FAIL immediately.
6. **After observations:** attach only redacted, non-sensitive evidence references to [P4 owner Issue #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9), confirmed defects to [QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2), update status/handoff; require a new explicit **owner P4 closure decision** before P5 could be separately authorised.

### Current-source Windows checklist, 13 November 2026

Use the existing kit for synthetic fixtures, N1–N12 case IDs and the result template. Use this section for current execution scope and the Gate C decision at the top of this worklist for phase closure. The [12 November Windows run](./P4_71_ONE_OWNER_APPROVED_WINDOWS_NATIVE_QA_RESULT_2026-11-12.md) stopped at UI discovery before fixture creation. The revised discovery and bridge guard reached actual WebView2 in the 13 November run. The [P4 synthetic CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43387057176) passed at the exact Windows build source.

If discovery or the Tauri bridge check blocks, the revised probe records the Vite loopback response and redacted WebView2 debugger page counts/categories. The probe returns a distinct non-zero blocked result before fixture creation. A diagnostic response confirms only what the local endpoints reported. The original P4-71 workflow is disarmed and its preflight is pinned to the consumed source approval. A future session needs its own approved source pin and run configuration.

| Order | What to do on current-source Windows | What to record |
| --- | --- | --- |
| **1. N1: identity and preflight** | Confirm the exact source/build, executable SHA-256, isolated QA app ID and disposable home and WebView2 profile. Confirm that the local development UI opens inside the selected WebView2 and exposes the Tauri bridge before creating any fixture. Stop if identity, isolation or UI discovery cannot be confirmed. | Source and executable hashes, redacted profile/home evidence and bridge outcome. If blocked, record which checks never ran. |
| **2. N2–N7: target review and project state** | On the classification fixture, inspect the ranked review, alternative candidates and repeated-account warning. Select a target, defer, reselect and decline. Verify each resulting target and Prepare state. Exercise the explicit no-objective choice. Switch to the regression fixture, review and manually select `future_cost`, then return to the classification project and check for carried-over selection, disposition or Prepare state. | Ranking and alternatives, repeated-ID warning and the selected target, disposition and Prepare state at each transition and project switch. |
| **3. N8–N10: blocked targets and decision evidence** | Verify that the rare-class fixture (4/80 minority labels) explains the minimum of six labelled rows per class, the sparse-label fixture (24/80 labels) explains the minimum of 30 labelled rows, and the unnamed-outcome fixture abstains. Manually select its `generic_measure` field and inspect the evidence and block. | The specific reason shown for each fixture, no recommendation where the review abstains, and a screenshot of the blocked manual selection showing whether the evidence and available actions are readable. |
| **4. N11: Quality version boundary** | Keep a version-0 review open while committing a permitted Quality edit on the same disposable fixture. Verify that the old-version request returns HTTP 409, the stale view cannot proceed on outdated evidence, and the version-1 review loads and remains current after relaunch. | Before/after version numbers, the redacted stale response and the actual Windows UI behavior on refresh and relaunch. |
| **5. R04: Windows layout** | On a fresh disposable workspace with no archived projects, check that no archive warning appears. Check the target strip, decision evidence and disclosure controls at normal and narrow widths and record Windows display scale. Drag **Your data** beside Prepare, close it, reopen it with the dock control and verify narrow-view behavior. | The archive state, actual dimensions and display scale, and redacted captures of the evidence panel, controls and docking results. [Browser layout checks](../frontend/e2e/isolated-workspace.spec.ts) provide comparison cases. |
| **6. R05 / BE-024: Prepare** | Record the per-field audit, compare global median/mean and mode/missing-marker choices, and confirm that the displayed field treatments match those choices. Use a manual exclusion, preview the high-risk changes, cancel once, then confirm the additive changes and recheck included predictors. Check that the plan and feature advice use the active Quality version and that expert choices reset on project, target or Quality version change. If a permitted disposable saved-experiment fixture is available, open it and check its recorded strategy values against the current Prepare choices. | Audit fields actually shown, strategy labels, preview diff, retained exclusion, predictor count and Quality version. Record fixture provenance and whether it was a synthetic saved record. For any unexercised part, record the specific remaining BE-024 criterion. |
| **7. N12: evidence at exit** | Check the disposable project experiment list and available QA-path and process/traffic evidence for the actual session. Account for the intended synthetic project and Quality writes. | Experiment count, observed write locations and the scope of network observation. Mark claims outside the observation scope **NOT TESTED**. The separate prospective R06 comparison is the check for original-tree preservation. |

[BE-024](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2#be-024-prepare-workspace-acceptance-criteria) requires per-column treatment visibility, safe analyst overrides, fold-local preprocessing and immutable experiment configuration. It does not specify whether overrides must be selectable on each individual field. The implemented numeric and categorical choices apply across fields of the matching type. The [saved-experiment browser check](./P4_79_SAVED_EXPERIMENT_READ_ONLY_BROWSER_ACCEPTANCE_2026-11-12.md) used synthetic GET responses. A Windows display result for that fixture can establish rendering and provenance display. End-to-end fitted experiment persistence requires separate evidence.

R03 still needs the separately approved physical offline measurement. R06 remains historically **STRICT FAIL**, with the writer **UNKNOWN**. Neither is covered by the Windows cases above.

### 13 November 2026 native run record

[Windows run 43387057193, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43387057193/job/131757987632) used source `50b683f0f87797fe2efe7a34dfca85a31507a0d0`. Preflight and one unpackaged build passed. Executable SHA-256 `acf6a3c468916731e4fdd8bc56264f76f65bc465a255850e640c0cc2d1764bc8`, 18,353,664 bytes. The isolated profile was present, six WebView2 processes matched its app identity, and the WebView exposed the callable Tauri bridge. The hosted runner's protected profile paths were absent after cleanup. No installer or build artifact was transferred.

| Case | 13 November observation |
| --- | --- |
| N1 | **PASS** for build provenance, isolated profile and actual WebView2 with a disposable backend. |
| N2–N4 | **PARTIAL** against this checklist. Classification opportunity, a repeated-ID count, and defer/review/clear were exercised. Full alternatives, selection-to-defer and decline were outside the observed sequence. |
| N7 | **BLOCKED** in the automation at the first switch. The selector remained disabled on the original synthetic project and timed out after five seconds. Source review traced that disabled state to the awaited native project-switch consent. The probe used WebView2 CDP and had no interaction with the OS dialog. The log did not capture the dialog itself or prove a project-switch product defect. |
| N5–N6, N8–N11, R04 layout and R05 Prepare | **NOT TESTED** in this run. |
| N12 | **PARTIAL**. The probe's cleanup checked the five disposable projects for zero experiments, with no reported cleanup failure. The PowerShell postrun check verified absence of the protected hosted-runner paths. Full network and write evidence was outside this observation. |

For a future isolated Windows session, verify the native **Stay** and **Switch project** actions using desktop-level input on the test machine and capture the resulting project and draft states. Keep the product consent prompt in place. [Existing source tests](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43386014036/job/131754560680) cover the asynchronous consent branches using a simulated native response. R03 and the original-device R06 comparison were outside the hosted run.

## E. Practical order for the next sessions

| Priority | Next deliverable | Who supplies the missing fact | Stop / done rule |
| --- | --- | --- | --- |
| **Resume Windows QA** | Exercise the Windows-native project-switch prompt with a desktop-level input driver or an operator in a future isolated session, then continue the remaining cases in §D | Current-source native observations | Record Stay and Switch project outcomes and report unexecuted cases individually. |
| **R06 evidence** | Assess any already-existing incident-time writer evidence if available | Owner or existing evidence records | With current evidence, retain historical **STRICT FAIL** and writer **UNKNOWN**. |
| **Native and physical acceptance** | One isolated current-source Windows session, plus a physical offline 8 GB check when the prerequisites are met | Suitable environment and existing authorisation requirements | Record each result. Missing prerequisites leave the applicable checks **BLOCKED / NOT TESTED**. |
| **P4 engineering closure** | Review R02–R06 and the phase exit criteria | Owner signs off on the recorded results and any explicit risk dispositions | P4 closure requires a separate decision. |
| **Before real-world prediction use** | Verify one proposed decision using §B | Accountable decision owner and independently checkable evidence | Gate C stays **UNVERIFIED** until the evidence supports use. |

**P4 status after the 13 November scope decision:** ACTIVE. R02–R06 are open, Gate C is unverified for real use, and the historical whole-tree result is STRICT FAIL. P5 is not authorised and P8 is not certified.
