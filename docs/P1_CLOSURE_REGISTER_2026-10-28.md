# PilotODIN P1 | Current closure matrix
**Updated:** 4 November 2026  
**Authority:** [one-primary-phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) and scoped actual evidence.  
**Phase status:** **OPEN. No owner-approved phase closure recorded.**  
**Historical full chronology:** [verbatim pre-audit closure register](./archive/P1_CLOSURE_REGISTER_PRE_AUDIT_2026-11-04.md). Never erase the historical intermediate failures.

## How to read this matrix
- **PASS, scoped:** tests/observation explicitly covered the named behaviour, at the named environment and source.
- **OWNER PASS, scoped:** owner confirmed a real Windows DEV interaction, without claiming release-wide telemetry.
- **HOSTED PASS:** verified in CI browser/real loopback backend, **not** a native WebView2 installed application.
- **PARTIAL:** implemented/tested pieces exist, but full end-to-end or native acceptance is missing.
- **OPEN / UNVERIFIED:** no adequate acceptance evidence.
- **DEFERRED BY OWNER:** explicitly not performed. Deferral is **not** a PASS or a signed waiver.

## P1 acceptance register
| Gate | Required experience or property | Status at 4 Nov | Evidence / condition to close |
| --- | --- | --- | --- |
| P1-I1 | Failed import leaves no misleading record or lost source if rollback fails | **PASS, scoped** | Owner Windows 4/4 P1 import recovery; [import/E2 record](./P1_IMPORT_RECOVERY_AND_E2_SPIKE.md) |
| P1-I2 | Upload staging, recoverable disk-write failure handling | **PASS, scoped** | [Upload staging evidence](./P1_UPLOAD_STAGING_ACCEPTANCE.md); no claim for all OS fault modes |
| P1-P1 | Primary edited Prepare project-switch Cancel and retention | **PASS, scoped** | Previous owner/dev UI and hosted synthetic journeys; no hidden data mutation |
| P1-P2 | Docked Prepare / native title-bar X, Stay, consented Leave | **OWNER PASS, scoped** | [Native close record](./P1_NATIVE_CLOSE_WINDOWS_ACCEPTANCE_2026-10-28.md); DEV ONLY, not installer |
| P1-P3 | Competing tab and failed project read keep draft, project identity and recover correctly | **HOSTED PASS** | [real-HTTP run #41802476525](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802476525) + source-extracted regression; **native multi-tab run not accepted** |
| P1-Q1 | Quality read-only snapshot/history version pairing, preview pagination and retry | **HOSTED PASS** | [frontend run #41802760086](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802760086), 130/130 Node; backend restart/retry real HTTP |
| P1-Q2 | Quality identifier, missingness, outlier diagnoses over actual local HTTP without writes | **HOSTED PASS** | [real-HTTP run #41802476525](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802476525), 1/1 integrated scenario: three distinct read-only findings, v0 unchanged |
| P1-Q3 | Complete approval/undo/restore/persistence across native error/restart | **PARTIAL** | Versioned approval code and earlier focused tests exist; **recent real HTTP Quality GET run never committed a correction**. No full latest native mutation/restart acceptance claimed |
| P1-K1–K4 | Keyboard navigation, dock resizing and edited narrow window | **OWNER PASS, scoped** | [Native accessibility matrix](./P1_NATIVE_ACCESSIBILITY_QA_2026-11-03.md), 3 Nov DEV ONLY |
| P1-S1 | Actual native baseline physical scale / no clipping | **DEFERRED BY OWNER / UNVERIFIED** | Native Windows screenshot and observed scale/usable controls |
| P1-S2 | Actual native 125% scale (if supported) | **DEFERRED BY OWNER / UNVERIFIED** | Observed native result or documented UNSUPPORTED hardware |
| P1-S3 | Actual native 150% scale (if supported) | **DEFERRED BY OWNER / UNVERIFIED** | Observed native result, original scale restored |
| P1-S4 | Windows Snap / minimum-width handling | **DEFERRED BY OWNER / UNVERIFIED** | Native observed window behaviour or legitimate unsupported resolution |
| P1-A1 | Native reduced-motion / focus behaviour | **DEFERRED BY OWNER / UNVERIFIED** | Observed Windows behaviour; badge alone does not prove compliance |
| P1-A2 | Narrator/screen-reader traversal of primary UI and consent | **OPEN / UNVERIFIED** | Source fix `6c400e02ed26` adds Quality consent dialog focus entry, Tab boundary and dismissal restoration; 9/9 related Node tests passed within frontend CI. **No native Narrator/WebView2 traversal was run**. |
| P1-N1 | Latest integrated native DEV project + Quality + failed switch + restart journey | **PARTIAL** | Scenarios pass on hosted Uvicorn/Chromium; selected native fragments PASS but no equivalent complete current WebView2 chain |
| P1-R1 | Resource policy/settings and truthful memory controls | **PARTIAL** | Scoped resource admission and read-only E2 inventory; real simultaneous AI + ML 8 GB feasibility **UNDETERMINED**; P5/P8 gates remain independent |
| P1-C1 | Explicit closure acceptance and no open critical/high P1 data-loss, correctness, security defect | **OPEN** | Review Issue #2 + source defects; record scope approval, evidence and owner deferrals before sign-off |

## Current automated verification, with exact scope
- [P1 Isolated Frontend run #41811231967](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41811231967), source SHA `6c400e02ed26f1757914913fdfffcb378b454eaf`: **139/139 Node PASS (including 9 new Quality modal keyboard tests), TypeScript/Vite build PASS and 5/5 hosted Chromium PASS**.
- [P1 Disposable Real HTTP run #41811232333](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41811232333), **same source SHA**: **1/1 integrated real-Uvicorn/Chromium PASS**. This unchanged read-only fixture covers three Quality investigation types, project switching/failure, two tabs, backend process restart and retry. **It does not exercise the new approval modal's keyboard interaction or any actual Quality correction.**
- Historical green tracks [#41802760086](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802760086) (130 Node) and [#41802476525](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41802476525) (1/1 real HTTP) remain preserved. Current docs-only changes do **not** create fresh test evidence.
- Earlier intermediate failed/cancelled runs exist; see [full archive](./archive/P1_CLOSURE_REGISTER_PRE_AUDIT_2026-11-04.md) and GitHub Actions rather than concealing them.

## Closure decision, not a percentage
**P1 is OPEN.** No official percent complete is computed because the baseline requirements are not weighted and the owner has not signed a frozen matrix. Native display scaling, Snap, reduced motion and screen reader evidence cannot be represented as PASS. Under [closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md), a documented owner-approved deferral requires explicit impact and follow-up owner; a missing mandatory native check otherwise blocks closure.

**Highest-value next step:** reconcile the native P1 gates and the remaining full DEV journey in one bounded acceptance decision, not an indefinite series of new source-polish tasks. Do **not** ask the owner to repeat previously reported K1–K4 solely for documentation. Do **not** run installers or touch protected original data to prove the phase.
