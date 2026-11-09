# PilotODIN 1.0 | P4-23 Consolidated Owner Windows Acceptance Go/No-Go

**Prepared:** 9 November 2026  
**Current status:** **PLAN READY; NEW WINDOWS BUILD NOT AUTHORISED; NEW INSTALL NOT AUTHORISED; OWNER NATIVE RETEST NOT STARTED.**  
**Current branch:** `feature/live-dev-workspace-20261023`, last observed checkout/documentation HEAD `40fa5849aee478a2750cbc07aafb6d685bb93119`. A build must independently verify the **actual** source SHA at build time; this document's SHA is not a reusable build manifest.  
**Authorisation basis:** User said `next` following source-side P4-22 readiness, not explicit consent for a new ~1.5 GB Windows NSIS build, download or install. The original owner's `we shouldnt risk` decision against closure with residuals deferred remains controlling.  
**Source evidence:** [P4-22 tool/limit report](./P4_22_WINDOWS_INTEGRITY_AND_RESOURCE_READINESS_2026-11-09.md). [P4 exact-source Actions #42700800731](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42700800731) at `40fa5849...`: **COMPLETED SUCCESS** in source/real-HTTP/synthetic Windows-probe tasks. The already installed Windows QA executable remains historical source `bca3c57...`, with no newer source fixes natively verified.

## Before building: strict GO / NO-GO

| Gate | GO only when | Current state |
| --- | --- | --- |
| Owner approval for one new **CI build** | Explicit user statement authorising **one current-source side-by-side QA Windows installer build** (not necessarily a local install) | **NO AUTHORISATION** |
| Owner approval for **local install** | Distinct explicit consent AFTER source/installer provenance is known; leave existing app untouched | **NO AUTHORISATION** |
| Trusted source | GitHub `feature/live-dev-workspace-20261023`, no unexpected changes; source SHA locked before build | Pending next source freeze |
| All source and browser gates | The exact application code commit passes P4 110 Python / 28 Node / 8 real-HTTP browser, production build and Win probe CI; rerun if application changes | Last known PASS at #42700800731 |
| QA package identity | `com.pilotodin.p4nativeqa` / `pilotODIN-P4-Native-QA`, distinct from `com.pilotodin.studio` original | Existing workflow checks; must repeat at new SHA |
| Full build provenance | Windows 2022 compile SHA, installed QA executable SHA, binary/model payload hashes and installer SHA+size, separate trust-checked manifest | Not available for the **newest** source; no installer built |
| Owner data protection | Original app closed, copy retained, pre-change read-only per-file aggregate baseline outside app dirs, no source data imported to QA | Proposed; **not executed** |
| Disposable QA-only data | Use already available synthetic CSV kit and independent QA app data; no model training and no real business data | Proposal; no new owner actions |
| Offline/8 GB | Actual device specifications checked, realistic native app + sidecar + model memory/behaviour monitored offline under controlled workload | **NOT TESTED** |
| Real target/business Gate C | Independent owner, label origin, prediction timing, entity/group/time validation, baseline, measured decision benefit and fair/lawful use | **UNVERIFIED, NOT WAIVED** |

**Fail-closed policy:** If any source/package hash is inconsistent, current app identity matches original, source tests fail, old data baseline is missing, hardware headroom is insufficient, or the owner declines the next step, **STOP**. No silent fallback to old installer, no approximate provenance, no forced user test.

## One-pass owner-native scope, AFTER explicit separately approved build/install

A single batch should replace repetitive manual CSV tours. Each checked line must have actual proof; the older owner's N1–N7 screenshots from `bca3c57...` are historical, NOT retests of subsequent safety patches.

1. **Integrity/provenance before import:** verify exact new NSIS manifest bytes and source SHA, installed QA EXE hash, separate identifier and app-data location; original app EXE/data hashed **before** and **after** with the read-only [P4-22 collector](../qa/p4_native/Measure_P4_Native_Readiness.ps1). Collect only aggregate hashes/counts and sanitized screenshots. Backup restoration still not proven by the same-file comparison.
2. **Source-fixed UI regressions:** launch the new separate QA with *zero* QA projects and verify no phantom `archived in another window` warning; import synthetic classification and verify decision-usefulness evidence is vertically readable, plus selected-target strip layout. Mark unobserved controls NOT TESTED.
3. **P4 correctness and isolation spot-checks:** from the *already available synthetic kit*, check single visible classification queue and numeric regression, explicit no-objective, project switch, rare class 4/80 block, insufficient labels 24/80 block, unnamed outcomes abstain, and at least one benign stale Quality-version block if safe. These are **spot-checks**, not separate mandatory manual tours; browser/API automated evidence remains separately labelled.
4. **No unintended training/mutation:** owner approves ONLY non-training review actions; verify Home experiment counts before/after plus read-only QA data baseline if feasible. Do not infer full no-write proof from an unchanged original EXE alone. No Model Lab fit or real operational dataset.
5. **Memory and offline feasibility:** measure the *actual* machine's total and available RAM and one realistic desktop operation; sample the launched QA process group with the P4-22 script, capture task manager/system free RAM and sidecar/WebView2 observations. A sample is **PARTIAL_OBSERVATION**, not proof of sustained whole-app peak demand or offline 8 GB. Full 8 GB acceptance requires credible 8 GB Windows operation with relevant offline AI inference actually running safely and bounded; if machine differs or model not loaded, mark **NOT TESTED**.
6. **Owner decision from evidence:** record result per gate **PASS / FAIL / NOT TESTED / BLOCKED** with exact source/native SHA and no personal data. Re-triage QA issues, retain original Gate C and master release blockers. Return to owner for a separate P4 close decision. **P5 does not start automatically.**

## Why clock UI is not part of this gate

User separately asked whether a live clock is feasible and where to display it. **It is feasible but not implemented or authorised in this milestone.** The visible desktop's *persistent* top header is owned by `frontend/src/UnifiedShell.tsx` (not the embedded `App.tsx` topbar, which is hidden by shell CSS). The best candidate placement is **before the existing project switcher**, but at 52 px height and constrained width it needs responsive hiding at narrow widths. Read browser/Windows local clock, minute-level updates with cleanup, no network, no project state mutation, no seconds by default, accessibility-friendly display. This is future UX backlog, not an unclosed P4 risk or business validity gate.

## Controlling decision

**P4 ACTIVE; P4-17 OWNER CLOSURE DECLINED; P4-23 PLAN READY ONLY; NO NEW INSTALLER; OWNER NATIVE AND OFFLINE 8 GB NOT TESTED ON LATEST SHA; ORIGINAL GATE C UNVERIFIED; P5 NOT AUTHORISED; P8 NOT CERTIFIED.**

Do not post a workflow dispatch or direct a user to install anything until owner consent explicitly covers that separate action.
