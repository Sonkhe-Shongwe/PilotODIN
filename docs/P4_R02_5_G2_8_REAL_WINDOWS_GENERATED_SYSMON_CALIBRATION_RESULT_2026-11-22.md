# PilotODIN P4 R02.5 | G2.8 real Windows generated Sysmon calibration

**22 November 2026. Evidence reconciliation of one explicitly owner-approved hosted-Windows run.** This is *collector calibration only*, not PilotODIN/No-CDP FileIO acceptance.

## Exact provenance and scope

- Owner-approved exact reviewed source: `598bb9fe80f7caca8cd20eec1ab898b9be027fc6`.
- [Direct-child activation `9de17f04525186cd76e9f9e8d4e976e5ee5bab79`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9de17f04525186cd76e9f9e8d4e976e5ee5bab79) changed **exactly two files** relative to reviewed source: a single job gate in `.github/workflows/p4-n12-generated-sysmon-bookends.yml`, and the **added** marker `qa/p4_research/N12_GENERATED_BOOKENDS_OWNER_APPROVAL_G2_6_FRESH_ONE_USE.txt`. Marker content was precisely `reviewed_source=598bb9fe80f7caca8cd20eec1ab898b9be027fc6` and `scope=n12-generated-sysmon-bookends-one-use`.
- Exactly one triggered hosted-Windows generated-only workflow: [GitHub Actions #45049623361](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049623361), **first attempt, COMPLETED SUCCESS** at the activation SHA. All visible source/consent guard, Python setup, collector invocation and final fixed-label summary steps completed successfully.
- [Immediate disarm `3ca694d086fa7ffa23cba173369a5c9fe94cdefc`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3ca694d086fa7ffa23cba173369a5c9fe94cdefc) changed **only the one workflow job gate line**, restoring `if: ${{ false }}`. It did not cancel or repeat the already pinned run. No subsequent Windows capture or retry.
- The separate [Linux source-only job #45049623353](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049623353) at the **temporarily armed activation SHA** failed a static test expecting `if: false`. That is an intentionally different source state; it is not a Windows measurement failure. Following disarm, a source-only [reconciliation commit `817161f50d1f00ae71688c29c9b4028970cfbb2b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/817161f50d1f00ae71688c29c9b4028970cfbb2b) preserved G2.6 as consumed and retargeted the **still disarmed** future trigger to the absent G2.8 marker. [Exact-source Linux CI #45049817722](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45049817722) **SUCCESS: 168/168 synthetic tests across 11 suites**.

## Native redacted result and its limits

The only relevant public fixed-label results in the hosted-Windows diagnostic logs were:

| Signal | Verified result |
| --- | --- |
| Sysmon collector provisioned | Yes, verified collector stage reached |
| Initial generated TCP/UDP Sysmon bookend | `passed on read 1` |
| Final generated TCP/UDP Sysmon bookend | `passed on read 1` |
| Generated driver receipt | `status=GENERATED_BOOKENDS_CORROBORATED` |
| Public fixed-label stage and blocker | `stage=none`, `blocker=NONE` |
| Fixture provenance | `evidence=GENERATED_FIXTURE_ONLY` |
| PilotODIN product launch | `product_launched=false` |
| Original WebView2 file-handle evidence | `NOT_COLLECTED` |
| Native N12 acceptance | `NOT_EVALUATED` |
| Uploaded raw artifacts | **0** |

- The PowerShell collector has a `finally` block that conditionally invokes signed Sysmon uninstall/cleanup. The successful workflow is consistent with normal teardown; the fixed-label public output does **not** independently prove a post-uninstall service-state check. No cleanup warning was identified in the inspected job logs. Do not overclaim an independently certified clean runner.
- Both test bookends were generated process and TCP/UDP loopback fixtures, **not authentic WebView2 application events**. The run did not build or launch PilotODIN, invoke Kernel-File ETW, inspect owner files or protected roots, upload raw traces, alter filesystem allowlists or produce a mutation closure proof.
- This real native pass supports the corrected generated-fixture collector timing, Sysmon Event 3 delivery and sequential strict bookend verification **for this isolated run**. It does **not** prove real-app original-file handles, writer FileObject/IRP/path joins, loss-reviewed successful file mutation inventory or absence of prohibited writes.

## Governing result and next engineering question

G1 remains **PASSED**. G2 remains **OPEN** because its exit requires authentic original writer and **file** handle to FileObject/IRP/path/operation attribution, original app FileIO evidence and independent loss/restore controls. An isolated generated Sysmon calibration pass is a necessary collector milestone but not the complete G2 outcome.

**Four-gate delivery 1/4 = 25%. Official R02.5 0/5, N12 0/2, P4 14/20 (70%), historical file-mutation engineering 3/4 (75%), unchanged.** No new native action is authorised by publishing this report.

Next source-only task: establish which exact original-handle witness the native no-CDP stack can safely obtain on a disposable hosted runner, with the narrowest bounded mechanism and adversarial review, before presenting any subsequent separately approved real-app native capture request.
