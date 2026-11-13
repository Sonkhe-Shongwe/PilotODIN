# PilotODIN 1.0 | P4-80 Acceptance worklist and independent-evidence intake

**13 November 2026 scope update:** The owner moved Gate C to approval of a specific real-world prediction use. P4 engineering closure now proceeds against R02–R06 and the phase exit criteria. [Owner decision](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md#13-november-2026--owner-decision-on-gate-c).

**Checkpoint:** 12 November 2026. **Type:** documentation-only coordination milestone, **not** a product implementation, acceptance result or authority to execute native/ML operations. **Authoritative branch:** `feature/live-dev-workspace-20261023`. **Latest checked application/test source:** [`db811488`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/db811488cef9a53b53736ff5d42d6643f4853ac3); [P4 #43299568196](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568196) passed 183 Python, 60 Node, TS/Vite, 11/11 disposable real-HTTP Chromium and synthetic Windows safety; [P1 #43299568087](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43299568087) passed 187 Node, TS/Vite, 7/7 Chromium. [Prior docs-only HEAD `d876b532`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d876b5324a62b1e546724eca3f0419d62b38d238). These do **not** establish P4 operational/native acceptance.

**Binding governance:** [P4-17 owner risk-deferral refusal](./P4_17_BOUNDED_DEVELOPMENT_CLOSURE_DECISION_REVIEW_2026-11-09.md), [P4-46 hard-stop boundary](./P4_46_CLOSURE_EVIDENCE_AND_DECISION_BOUNDARY_2026-11-12.md), [P4-50 independent evidence intake](./P4_50_EVIDENCE_INTAKE_AND_SINGLE_NATIVE_READINESS_2026-11-12.md), [P4-71 limited actual native boot](./P4_71_ONE_OWNER_APPROVED_WINDOWS_NATIVE_QA_RESULT_2026-11-12.md), [existing native test kit](../qa/p4_native/README.md) / [results template](../qa/p4_native/RESULTS_TEMPLATE.md), [master QA #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2), [owner P4 evidence #9](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/9).

## A. Single risk checklist: existing evidence is not remaining acceptance

| Gate | Existing verifiable evidence | Specific missing proof | Next safe action / dependency | Current verdict |
| --- | --- | --- | --- | --- |
| **R01 / Gate C:** real-world prediction use | Deterministic target review and historical research | Independently checkable decision owner and intervention, outcome provenance, as-of inputs, suitable evaluation, baseline and measured benefit, and permitted use | Use §B when a specific real-world prediction use is proposed | **UNVERIFIED / REQUIRED BEFORE REAL USE** |
| **R02:** native negative and Quality-version parity | N1–N11 passed earlier. [#43423213278](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43423213278) attributed a sampled port 443 connection to WebView2's Network Service. [#43427707718](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) observed zero established non-loopback connections in both snapshots | Earlier connection destination and purpose, and remaining network/write evidence | Review scoped evidence below | **N11 PASS / N12 PARTIAL** |
| **R03:** offline 8 GB coexistence | Limited hosted native boot/WebView process evidence; resource estimators are not RAM measurements | Physical 8 GB Windows, actual offline local Qwen + WebView2 + backend/analytics, sustained process/RAM and workload observations | Owner-provided eligible hardware/runtime and separately approved measured test; preagree workload, duration and stop limits | **OPEN / NOT TESTED** |
| **R04:** current native UX | Earlier target layout and archive-warning checks passed. [#43427707718](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) passed drag-to-dock, Dock beside, close and narrow-width pause/restore | Review the hosted evidence at its tested source as part of P4 signoff | See the synchronized retest below | **HOSTED RETEST PASS** |
| **R05 / BE-024:** Prepare review | Earlier native controls passed. [#43420833495](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43420833495) passed project and Quality resets plus recorded strategy display using a synthetic GET fixture | Review the required BE-024 scope. Actual saved-experiment persistence is outside the synthetic display evidence | Reconcile the case results against the acceptance scope | **TARGETED UI CASES PASS / WIDER SCOPE OPEN** |
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

**Current state:** N1–N11 passed in the consolidated hosted Windows run, including same-binary relaunch. R04 and R05 have partial results. N12 has scoped evidence. See the [consolidated results below](#13-november-2026-consolidated-hosted-windows-acceptance).

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

### 13 November 2026 project-switch follow-up

[Windows run 43392318378, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43392318378/job/131775043386) used source `57e6ff1c54b7a8eb15e76e1fb9c359f07dc38234`. Preflight and one unpackaged build passed. Executable SHA-256 `f58f2fb4c0bdf7cf651b40cd610e7e53e42ef12ee38a61fd831831e66a8b992b`, 18,353,664 bytes. The isolated profile was present, six WebView2 processes matched it, and the probe reached actual Tauri WebView2. [Synthetic P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43392318312) passed at the same source. There was no installer or artifact transfer, and the hosted runner's protected profile paths were absent after cleanup.

| Case | Follow-up observation |
| --- | --- |
| N1 | **PASS.** Verified build provenance, isolated profile, actual WebView2 and disposable backend. |
| N2–N3 | **PASS.** Verified three classification review cards, additional alternatives and the specific repeated-ID count in the evidence disclosure. |
| N4–N5 | **PASS.** Selection, defer, reselect, decline and the explicit no-objective choice behaved as expected. Defer, decline and the no-objective action cleared the target and checkpoint. |
| N7 | **BLOCKED** at the first **Stay** action. The selector entered the pending consent state, but the driver timed out waiting for the exact dialog and both named buttons in Windows UI Automation. The combined timeout cannot distinguish an absent dialog from a different UI Automation tree or button names. Neither button outcome was observed, and this is not a reproduced project-switch defect. |
| N6, N8–N11, R04 layout and R05 Prepare | **NOT TESTED** after the blocked switch. |
| N12 | **PARTIAL.** Cleanup checked the five disposable projects for zero experiments, with no reported cleanup failure. The protected paths were absent on the hosted runner. Full network and write evidence remains open. |

The next useful evidence is a desktop-level observation of the prompt and its buttons, or staged diagnostics that distinguish dialog discovery from button discovery for the same isolated app process. Continue N6–N11 and Prepare/layout once the switch can be exercised. The one-use workflow was disarmed at [`fa33d43`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/fa33d43997143945aa7b5683a918cb214cb9c5e9).

### 13 November 2026 native button fallback run

[Windows run 43399799218, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43399799218/job/131799623603) built and launched source `6824cd10e25ade9610cc34739d9f33801f648cf2` once. Executable SHA-256: `978e3dd27be1bf2a5f57862bb03f853936959f4e3d9ef30358cd53c0298cd2e6`. The isolated profile and six WebView2 processes were observed. The Vite and CDP loopback endpoints returned HTTP 200, and CDP listed one page of the expected URL class. The probe could not verify a callable Tauri bridge on its first check, so it stopped before creating any QA project. The log does not distinguish delayed initialization from a bridge that stayed unavailable.

The Windows native-button fallback remains verified on the [synthetic form](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43395617425/job/131785679826). Both actual app button actions and subsequent native cases remain unobserved in the fallback run. The [parallel synthetic P4 workflow](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43399799126) passed. The fallback workflow was disarmed after dispatch.

The revised probe uses the existing 20-attempt discovery loop to wait for both a unique approved loopback page and a callable Tauri bridge before creating fixtures. It now reports a distinct bridge-unverified status. Local tests cover delayed initialization, a persistently missing bridge, ambiguity and a page that leaves the approved origin. This revision awaits Windows app verification.

### 13 November 2026 bridge-ready Windows run

[Windows run 43402454805, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43402454805/job/131808523703) compiled and launched one unpackaged debug app from `904d773064acc402f68af9cfd8cbb854f3145a18`. Executable SHA-256: `d421fe0317f4a47a783a2fc59b4bf626ab864cf6b1d57b380a47ae177cf60205`. The isolated profile, six WebView2 processes and a callable Tauri bridge were observed. The probe created the synthetic projects, then timed out waiting for the Prepare target-review section. The WebView snapshot showed Prepare selected and the project picker still on “No projects imported yet.” Neither project-switch action ran. The [parallel P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43402454748) passed. The one-use workflow was disabled after dispatch.

The probe had written the project ID into storage and navigated to a hash-only route on an already loaded shell. That navigation can retain the mounted empty catalogue. The revised harness seeds the fixture project and Prepare tab, then opens a new document so the shell fetches the catalogue again. The shared setup is exercised in real-HTTP browser CI from an initially empty catalogue. Native verification of that transition and the two dialog actions remains open.

### 13 November 2026 catalogue-ready Windows run

[Windows run 43404155763, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43404155763/job/131814284211) compiled one unpackaged app from `96c17d672714c107aad32f3796144a16771397d0`. Executable SHA-256: `bb47548abaa0f2b0e04b05073c1f5c199563773995e4e83bdebc4f976287ed78`. Six isolated WebView2 processes and the callable Tauri bridge were observed. The refreshed catalogue loaded the synthetic fixture, and N1–N5 passed in the desktop app.

N7 stopped at the first **Stay** action. The PowerShell dialog driver hit the 20-second process timeout without a stage diagnostic. The run did not observe the result of either button. The updated driver finds the same process-owned, exact-title dialog via native window enumeration and invokes only the requested button after both exact labels are present. It avoids the UI Automation calls that could outlast the helper's polling deadline. The revised test records whether Windows sees the app window, dialog and button handles. N6, N8–N11, R04 and R05 did not run. The [parallel P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43404155710) passed. No installer or binary artifact was produced for distribution, and the one-use workflow was disabled after dispatch.

### 13 November 2026 direct Windows dialog run

[Windows run 43405531132, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43405531132/job/131818934269) compiled one unpackaged app from `f7a1a0f6b3715b86cfad72c8d244960a4bce124f`. Executable SHA-256: `97f3dcbf0bd0d2aa4eddcac4b3bfc34d1a02fe6182a0c59ec6661499719d18b4`. The synthetic catalogue loaded and **N1–N10 passed** on actual WebView2. The direct Windows driver invoked both native button labels. **Stay** preserved the project and edited target. **Switch project** loaded the destination and cleared the old target and Prepare review state. Regression selection and all three blocked-target cases also passed.

N11 stopped at HTTP 422. The harness omitted the mandatory `target` query parameter, so request validation prevented the version check from running. The revised harness shares its request builder with the real-HTTP test, verifies the current plan at version 0 and requests version 1 to verify the 409 conflict. These are API checks. The native Quality edit, stale-view behavior and relaunch sequence remain open. The `finally` block checked the synthetic projects for experiments without reporting an error. Full N12 network and write evidence remains open. R04 and R05 did not run. [Parallel P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43405530967) passed. No installer or binary artifact was produced for distribution. The one-use workflow was disabled after dispatch.

### 13 November 2026 Windows Quality version transition

[Windows run 43408216925, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43408216925/job/131827825936) compiled one unpackaged app from `ba4895d94faf0c99261d03286abf3f106d2594da`. Executable SHA-256: `e4382ee708b8f6b40e2586958ec44c648137ef85c7d09d00dd23dbbad8f88b42`. The isolated WebView2 profile was present and N1–N10 passed again. On the disposable Quality fixture, the app approved the one-cell whitespace correction, displayed working version 1, and both version-0 Prepare and target-review requests returned HTTP 409. A direct version-1 Prepare request returned the expected plan. Returning to Prepare in the mounted desktop app still showed a version conflict. WebView reload and native process relaunch were not reached.

The browser test had opened the Quality fixture directly. The desktop test reached it through the project selector, which hydrates the new Studio from a verified project snapshot. React Strict Mode replays mount effects in development. The cleanup invalidated the operation guard, and the handoff skipped the initial project load that would otherwise re-establish its scope. The revised mount effect re-establishes the handed-off project's scope. The browser regression now switches projects before applying the same Quality edit. The [parallel P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43408216797) passed at the native run source. The one-use workflow was disabled after dispatch. No installer or executable was transferred.

### 13 November 2026 Windows Quality refresh retest

[Windows run 43409810256](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43409810256/job/131833224767) compiled one unpackaged app from `4c20567c101297bea4b8b2a6a9db1997c7f0336e`, SHA-256 `1bc175ab8dc360ee552407c938bf56c4747ca0e6d98d46024a820467fc314011`. N1–N10 passed again. N11 passed through the actual Windows WebView: one-cell Quality approval, rejection of version-0 requests with HTTP 409, current Prepare version 1, and persistence after WebView reload. N12 verified the experiment count remained zero.

The Windows close request was accepted and the original app process exited. The harness then reported an unsuccessful exit without logging a numeric code and stopped before starting the second process. The close check now retains the Windows process handle before posting the close request and reports the actual exit code. The corresponding synthetic Windows check covers both zero and nonzero codes. A second app process and its restored Prepare view are still unverified. The one-use workflow was disabled after dispatch.

### 13 November 2026 consolidated hosted Windows acceptance

[Windows #43414850207, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43414850207) at `ebeb44fc0da1b4086026b7690d82c3b2923d24c9` passed preflight and compiled one unpackaged debug app. Executable SHA-256 `0ee78d27cad5c4cce2a65af341efe39fc24b1e27c9d806995b50d01227dcd604`, 18,353,664 bytes. Six isolated WebView2 processes and the callable Tauri bridge were observed. The workflow finished **FAIL** at R04. It was disarmed at `ede22ef0fcadd48f586abc831a113cb5cf88624a`.

| Check | Hosted result |
| --- | --- |
| N1–N11 | **PASS.** Quality approval, stale version-0 HTTP 409, Prepare refresh, WebView reload, normal process shutdown and a new process from the verified executable. The reopened app restored the selected project and Quality version 1, cleared the draft target and loaded the version-1 plan on explicit selection. |
| R04 layout | **PARTIAL / FAIL at docking.** The WebView measured 1028 × 749 CSS pixels at scale 1. At overridden widths of 1440 and 1100, the checkpoint was visible without horizontal overflow and no archive warning appeared. [Synthetic checkpoint captures](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43414850207/artifacts/14030424728). After the automated drag, the dock selector was absent. Close, reopen and narrow pause/restore did not run. The corresponding Linux Chromium test passed in [P1 #43414850442](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43414850442). The Windows evidence establishes neither the exact drag event path nor the cause. |
| R05 Prepare | **PASS for exercised controls.** Per-field numeric and categorical audit, global median/mean and mode/missing-marker switches, manual exclusion, cancel/apply of additive high-risk exclusions, one remaining predictor, version-0 plan/advice and reset on target change. Project/Quality-change strategy resets and native saved-experiment provenance were not tested. Wider BE-024 remains open. |
| N12 | **PARTIAL.** Zero experiments across seven synthetic projects before and after relaunch. After CDP attachment, the browser intercepted exactly the two intended Quality POSTs and blocked five stylesheet requests (four before and one after relaunch). No other external or unexpected loopback requests were recorded by that interceptor. The final inventory counted 11 files in the disposable QA home and 323 in the isolated WebView profile. Both protected identities were absent. Whole-process network and file-write tracing was outside this evidence. |
| R03 and R06 | Physical offline 8 GB test **NOT TESTED**. Historical original full-tree **STRICT FAIL** with 74 differences and unknown writer remains open. |

[P4 #43414850160](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43414850160) and [P1 #43414850442](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43414850442) passed at the same source. No installer or executable was transferred, and the run used synthetic data on a hosted runner.

### 13 November 2026 remaining P4 Windows acceptance

[Hosted Windows #43420833495, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43420833495) passed preflight and used one unpackaged build at `258a859122f57f1c1cd2238ef2c08554bdd9c3c4`. Executable SHA-256 `5138b4121b277a27a6cd1fbeb7e8a06b862bff7a6fa90a737da4fc6e5c766eb9`, 18,353,664 bytes. The workflow ended **FAIL** at R04 drag-to-dock. The [workflow was disarmed](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e25bb81abebbe7e0199c5dc3e5402f756ba8efbf).

| Case | Observed result |
| --- | --- |
| R04 drag | **FAIL.** The native WebView measured 1028 × 749 CSS pixels at scale 1 before overriding the viewport. The automated gesture emitted 1 drag start, 1 drag over carrying the workspace-tab type, 0 drops and 1 drag end. The dock did not appear after dragging. The run did not resolve why the drop was absent. |
| R04 explicit controls and responsive layout | **PASS.** Dock beside opened Your data, the dock closed, narrowing the WebView viewport paused the split, and widening restored it. |
| R05 Prepare resets | **PASS.** Both imputation choices reset to defaults after a consented Windows project switch and after a Quality edit advanced the working version from 0 to 1. |
| R05 recorded choices | **PASS for display.** Evaluate and Predict showed the synthetic record's mean and reserved missing marker and its version 0. The fixture was served through read-only GET overrides. No real experiment was fitted or persisted. |
| N12 | **PARTIAL.** Zero experiments across two disposable projects. The WebView intercepted the two intended Quality POSTs and blocked five font requests. The scoped process TCP snapshots counted 2 loopback / 1 other before and 21 loopback / 2 other after, across eight processes per snapshot. The run did not resolve the non-loopback endpoints, purpose or process within the group. The post-run inventory found 3 files in the disposable QA home and 306 in the isolated WebView profile. Both protected identities were absent. These samples do not prove system-wide network or file-write isolation. |

[P4 #43420833547](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43420833547) and [P1 #43420833501](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43420833501) passed at the launch source. The earlier N11 relaunch evidence remains on its recorded SHA. The physical R03 offline run was outside scope. R06 historical strict fail remains open. No installer or executable was transferred.

### 13 November 2026 focused Windows docking and TCP attribution

[Hosted Windows #43423213278, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43423213278) passed preflight and compiled one unpackaged debug app at `ef6bd3748eb13935ed894fd79d8eeb685a4f6172`. Executable SHA-256 `6c33c955aacec27790119247bfb3dbc72d46806bd44f00f7d84a402327d354d3`, 18,353,664 bytes. Six isolated WebView2 processes were observed. The workflow ended **FAIL** at R04. [Workflow disarm](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6b1c1520a171a292cb399fcc3f756b695726b584).

| Case | Observed result |
| --- | --- |
| R04 drag | **FAIL.** The two-move pointer gesture emitted one drag start, two drag-overs carrying the workspace-tab type, zero drops and one drag end. The last drag-over was unaccepted and the drag-end effect was `none`. The logs do not establish which guard or event path explains the result. |
| R04 explicit dock controls | **PASS.** Dock beside, close and responsive pause/restore passed again. |
| N12 sampled TCP ownership | **PARTIAL.** One non-loopback IPv4 connection to remote port 443 appeared in each snapshot, owned by the isolated WebView2 Network Service (PID 3012). The snapshots counted 2 loopback before and 3 after. They do not prove the same socket persisted or identify its remote host, initiating request or purpose. |
| N12 synthetic data and scoped writes | **PARTIAL.** The one project held zero experiments. The WebView interceptor recorded zero writes, blocked one font request and found no other unexpected requests. The post-run inventory found 2 files in the disposable home and 297 in the isolated profile, with both protected identities absent. Full-system file and network tracing was outside scope. |

[Regular P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43423212865) passed at the launch source. The earlier R05 passes and native restart evidence remain on their recorded sources. No installer or executable was transferred.

### 13 November 2026 synchronized Windows docking retest

[Hosted Windows #43427707718, attempt 1](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707718) passed both jobs at `f9ef20b76dc42f29c0f7a866c1d1c0538c0113b1`. One unpackaged debug build, SHA-256 `74922bf499c5a3dc0f4bf36d9a67c68852d1de8be131f3b61dafdce86028bb94`, 18,353,664 bytes. Six isolated WebView2 processes and the callable Tauri bridge were observed. [Workflow disarm](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5f1302e919716beb9decc64654a048c44a4bc2c8).

| Case | Observed result |
| --- | --- |
| R04 synchronized drag | **PASS.** One drag start, two drag-overs, two pane bubble events, one drop and one drag end. The last drag-over was accepted with Prepare active and the final effect was `move`. The correct dock opened. |
| R04 controls and responsive layout | **PASS.** Dock beside, close, narrow WebView pause and wide WebView restore. The initial native viewport was 1028 × 749 CSS pixels at scale 1. |
| N12 TCP and writes | **PARTIAL.** Eight-process TCP snapshots counted 2 loopback / 0 non-loopback before and 21 loopback / 0 non-loopback after. One font request was blocked, with zero writes and zero other unexpected intercepted requests. The one disposable project passed the zero-experiment assertion. Final inventory counted 2 files in the disposable QA home and 258 in the isolated profile. Both protected identities were absent. The two snapshots cannot establish session-wide network isolation or resolve the earlier port 443 observation. |

[Regular P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43427707627) passed at the launch source. No installer or executable was transferred. Physical offline operation (R03) and the historical original-data result (R06) remain open.

## E. Practical order for the next sessions

| Priority | Next deliverable | Who supplies the missing fact | Stop / done rule |
| --- | --- | --- | --- |
| **Remaining Windows evidence** | Review the hosted R04/R05 passes and outstanding N12 write and network evidence | Current-source evidence and owner review | Keep the prior failed runs and report the scope of each test |
| **R06 evidence** | Assess any already-existing incident-time writer evidence if available | Owner or existing evidence records | With current evidence, retain historical **STRICT FAIL** and writer **UNKNOWN**. |
| **Native and physical acceptance** | One isolated current-source Windows session, plus a physical offline 8 GB check when the prerequisites are met | Suitable environment and existing authorisation requirements | Record each result. Missing prerequisites leave the applicable checks **BLOCKED / NOT TESTED**. |
| **P4 engineering closure** | Review R02–R06 and the phase exit criteria | Owner signs off on the recorded results and any explicit risk dispositions | P4 closure requires a separate decision. |
| **Before real-world prediction use** | Verify one proposed decision using §B | Accountable decision owner and independently checkable evidence | Gate C stays **UNVERIFIED** until the evidence supports use. |

**P4 status after the 13 November scope decision:** ACTIVE. R02–R06 are open, Gate C is unverified for real use, and the historical whole-tree result is STRICT FAIL. P5 is not authorised and P8 is not certified.
