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
| P1-Q3 | Complete approval/undo/restore/persistence across native error/restart | **HOSTED PASS / NATIVE OPEN** | [CI #41815871774](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815871774), actual Uvicorn/Chromium synthetic C: cancel without write, single-cell approved v1, receipt replay 409, undo v2, restore v1 as v3, immutable original+history across backend restart. **No real native WebView2 approval, error/restart acceptance**. |
| P1-K1–K4 | Keyboard navigation, dock resizing and edited narrow window | **OWNER PASS, scoped** | [Native accessibility matrix](./P1_NATIVE_ACCESSIBILITY_QA_2026-11-03.md), 3 Nov DEV ONLY |
| P1-S1 | Actual native baseline physical scale / no clipping | **DEFERRED BY OWNER / UNVERIFIED** | Native Windows screenshot and observed scale/usable controls |
| P1-S2 | Actual native 125% scale (if supported) | **DEFERRED BY OWNER / UNVERIFIED** | Observed native result or documented UNSUPPORTED hardware |
| P1-S3 | Actual native 150% scale (if supported) | **DEFERRED BY OWNER / UNVERIFIED** | Observed native result, original scale restored |
| P1-S4 | Windows Snap / minimum-width handling | **DEFERRED BY OWNER / UNVERIFIED** | Native observed window behaviour or legitimate unsupported resolution |
| P1-A1 | Native reduced-motion / focus behaviour | **DEFERRED BY OWNER / UNVERIFIED** | Observed Windows behaviour; badge alone does not prove compliance |
| P1-A2 | Narrator/screen-reader traversal of primary UI and consent | **OPEN / UNVERIFIED** | Real hosted Chromium revealed focus did not return after Escape on earlier source; production fix [`2cbd3e751f18`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2cbd3e751f183db4b0dc8beb16e5adc881c89a5e) captures opener before disabling, adds focusable fallback. New CI #41815871774 tests mounted dialog Tab/Shift+Tab, Escape, focus restore **PASS in Chromium**; **not Windows Narrator/WebView2**. |
| P1-N1 | Latest integrated native DEV project + Quality + failed switch + restart journey | **PARTIAL** | Scenarios pass on hosted Uvicorn/Chromium; selected native fragments PASS but no equivalent complete current WebView2 chain |
| P1-R1 | Resource policy/settings and truthful memory controls | **PARTIAL** | Scoped resource admission and read-only E2 inventory; real simultaneous AI + ML 8 GB feasibility **UNDETERMINED**; P5/P8 gates remain independent |
| P1-C1 | Explicit closure acceptance and no open critical/high P1 data-loss, correctness, security defect | **OPEN** | Review Issue #2 + source defects; record scope approval, evidence and owner deferrals before sign-off |

## Current automated verification, with exact scope
- [P1 Isolated Frontend #41815871607](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815871607), exact tested SHA `570d98f0d57496a3a7dddb9ed6a5dab5192a9450`: **139/139 Node PASS, TypeScript/Vite build PASS, 5/5 isolated Chromium PASS**. Production fix at source ancestor `2cbd3e751f18`.
- [P1 Disposable Real HTTP #41815871774](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815871774), **same tested SHA**: **two separate Playwright/Uvicorn scenarios both 1/1 PASS**. (1) Previously accepted A/B project import/read-only Quality/failed switch/two tabs/backend restart; (2) new generated C Quality approval modal and actual version-bound write, replay rejection, undo, restore and restart with unchanged original. All browser POST routes in C are exact project/operation/receipt permits; never claim native Windows approval.
- **Intermediate failures retained**: [#41814947968](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41814947968) exposed genuine focus-restore bug plus per-suite shared disposable state. [#41815412856](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815412856) rejected overly strict Playwright grep selectors before executing tests. [#41815629923](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815629923) passed the original A/B scenario, then failed an ambiguous version-badge locator in new C scenario (real v1 approval had succeeded). All test/config issues corrected before the final green run. Previous green CI remains historical evidence, not replaced or concealed.

## 4 November 2026 | Current native acceptance blocker and QA reconciliation
- Latest authoritative source evidence: tested `570d98f0d57496a3a7dddb9ed6a5dab5192a9450` with [frontend 139/139 + 5/5](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815871607) and [two real-HTTP synthetic scenarios](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41815871774), all green. No subsequent application code change or test execution is being asserted by this decision.
- **P1 OPEN / native acceptance BLOCKED**: owner-deferred physical S1..S4 and reduced-motion A1 are not PASS or signed waivers; native Narrator A2, full Quality Q3, complete N1 and the phase closure decision C1 remain unverified. R1 still partial. Accepted K1..K4 must not be redundantly repeated.
- QA Issue #2 `BE-033` now correctly records **SOURCE-FIXED / native multi-project acceptance OPEN**: the current authoritative `UnifiedShell.tsx` already provides a disabled placeholder and a dedicated import action; hosted project import/recovery proof exists. No additional source patch is indicated by the historical single-project screenshot.
- This is an evidence and decision reconciliation, not Windows execution, an approval of further deferrals, or permission to start P2. The next legitimate closure input is actual owner-authorised disposable native Windows evidence or explicit impact-assessed owner closure/deferral direction.

## Closure decision, not a percentage
**P1 is OPEN.** No official percent complete is computed because the baseline requirements are not weighted and the owner has not signed a frozen matrix. Native display scaling, Snap, reduced motion and screen reader evidence cannot be represented as PASS. Under [closure policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md), a documented owner-approved deferral requires explicit impact and follow-up owner; a missing mandatory native check otherwise blocks closure.

**Highest-value next step:** reconcile the native P1 gates and the remaining full DEV journey in one bounded acceptance decision, not an indefinite series of new source-polish tasks. Do **not** ask the owner to repeat previously reported K1–K4 solely for documentation. Do **not** run installers or touch protected original data to prove the phase.
