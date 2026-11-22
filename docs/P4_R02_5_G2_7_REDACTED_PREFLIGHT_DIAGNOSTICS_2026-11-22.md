# PilotODIN P4 R02.5 | G2.7 fixed-label redacted preflight diagnostics

**22 November 2026. Source-only.** This review neither approves nor executes a Windows baseline, collector, application, installer or native mutation acceptance.

## Problem and evidence boundary

The one-use, source-pinned, hosted Windows [generated Sysmon run #45046709245](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45046709245) stopped with a fixed-label `BLOCKED / preflight` receipt after approved checkout and verified Sysmon provisioning. Neither generated initial nor final TCP/UDP bookend completed. The earlier [G2.6 helper consent review](./P4_R02_5_G2_6_GENERATED_SYSMON_HELPER_CONSENT_READ_REVIEW_2026-11-22.md) isolated a probable missing permission at the separate `sysmon-tail` PowerShell reader; the original receipt alone could not identify which preflight boundary failed.

## Implementation in the generated-only Python driver

- Existing phase `preflight`, `initial`, `final`, `none` remains bounded. Add exactly one fixed-label `blocker` field, accepting `NONE`, `UNSPECIFIED`, `HOST_SCOPE`, `SOURCE_APPROVAL`, `RUNNER_PATH`, `SYSMON_CHANNEL`, `INTERNAL_PREFLIGHT`, `FIXTURE_VERIFICATION`.
- `HOST_SCOPE` rejects non-Windows or wrong argument shape **before Git or filesystem access**. `SOURCE_APPROVAL` encompasses detached Git source identity, first-attempt hosted push, branch/run fields and exact generated-only one-use consent. `RUNNER_PATH` covers the existing disposable-path proof or exclusive directory creation. `SYSMON_CHANNEL` is reserved for the first channel-tail read or malformed record number. `INTERNAL_PREFLIGHT` covers unexpected import/driver errors. `FIXTURE_VERIFICATION` covers generated fixture and strict phase-verifier failures.
- Each label is a diagnostic *location*, not an independently proved underlying root cause, approval bypass, successful collector session, permissible mutation, or original file-handle witness. Unrecognised stages and blockers become safe fixed values. Raw exception data, original user paths, Sysmon XML, event bodies, PIDs, source SHAs, network addresses and private runner paths are **never** serialized into the public receipt.
- Source identity and consent still precede any runner path creation or Sysmon channel read. The exact existing `n12_app_journey.verify_fixture_sysmon` rules, contiguous record windows and first/final fixture behavior remain unchanged. All failures remain `BLOCKED`. There is **no additional capture or new permissive exception**.

## Published source and exact-source verification

- [G2.7 implementation `3baa5f778a200533fde0a19a5f2438353eba9192`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3baa5f778a200533fde0a19a5f2438353eba9192) changes exactly three files: the generated-only driver, a new injected synthetic test suite, and the read-only Ubuntu source workflow. [Initial source CI #45049057684](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049057684) **FAILED at Python syntax validation** in the new test, before running tests. This was not a native failure.
- [Test-only syntax repair `a5e548b5c4237108346ca167408990d936f8df99`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/a5e548b5c4237108346ca167408990d936f8df99) corrects the nested context-manager statement without changing the production driver or Windows workflows.
- [Exact-source Linux Actions #45049161934](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049161934) **COMPLETED SUCCESS**, first attempt on the repaired SHA. GitHub logs show **168/168** regression tests across 11 suites: 35 destination, 43 file-pair, 3 strict integration, 12 writer identity, 25 no-CDP reducer, 8 mutation triage, 9 G2 static preflight, 4 final-window, 15 generated bookend, 5 safety source, and 9 preflight-diagnostic tests. Source AST syntax checks also succeeded.
- New negative tests exercise invalid hosted scope, source approval, Git read error, path validation, directory creation, Sysmon read failure, malformed tail, verified tail and redaction of private-looking strings. All new tests inject callbacks and mocks on Linux. No collector, native application, ETW session, user data or protected path is accessed by this CI.

## Restrictions, measurement and score

- Both existing native Windows workflows remain explicitly `if: ${{ false }}`. Previously used approval markers remain consumed and preserved; the prospective `qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_6_FRESH_ONE_USE.txt` marker is **absent**. No Workflow Dispatch, Windows run or approval reuse occurs.
- A new hosted generated Sysmon measurement requires **new, explicitly scoped, source-pinned, one-use owner approval**. If it succeeds, it would provide generated TCP/UDP collector calibration evidence **only**. It would not establish authentic original WebView2 **file** handles, real app FileObject/IRP/physical destination attribution, zero-loss FileIO, or official native mutation acceptance.
- Delivery **G1 PASSED, G2 OPEN, 1/4 = 25%**. Official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, historical file-mutation preparation **3/4 (75%)**, all unchanged.
