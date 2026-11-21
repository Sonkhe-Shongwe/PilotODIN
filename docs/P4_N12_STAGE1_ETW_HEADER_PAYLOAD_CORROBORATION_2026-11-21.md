# PilotODIN P4 | Stage 1 independent ETW/Sysmon corroboration and true app launch order

**21 November 2026 | SOURCE-ONLY correction** at [code `66c785c`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/66c785cdc2a8fc3444e95cba282d366391beb996). [Exact-source CI #44889250608](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44889250608) completed **4/4 SUCCESS**: **926 Python tests passed, six skipped, 373 subtests; 104 Node tests, TypeScript/Vite build, hosted Windows synthetic controls, disposable browser and R03 Windows fixture passed.** No new native PilotODIN launch was performed.

## Actual Stage 1 blocker from the earlier native run

[Native no-CDP #44888041646](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44888041646) compiled real Windows Rust/Tauri, exercised no-CDP startup, ordinary close and complete process capture, but strict lifetime/profile verifier **BLOCKED**. Independent ETW and retained app handle birth/exit payloads matched, but ETW event-header start timestamps preceded process creation FILETIME by 237 ticks for the app and 30 to 1,816 ticks for WebView children. Some stop headers similarly preceded exit payloads by 2,975 to 3,584 ticks. Six WebView stop executable names were 14-character prefixes. All starts had full exact paths, Sysmon reported the app, six WebView and one WebView network process, ETW loss was zero and protected snapshots MATCH. The strict header-vs-payload and unhandled shortened-name requirements blocked the final process identity proof.

## Contract and basis

[Microsoft EVENT_HEADER](https://learn.microsoft.com/en-us/windows/win32/api/evntcons/ns-evntcons-event_header) documents event timestamps; [Event Metadata Overview](https://learn.microsoft.com/en-us/windows/win32/etw/event-metadata-overview) separates runtime header metadata and provider data; [the kernel-process manifest field schema](https://github.com/nasbench/EVTX-ETW-Resources/blob/main/ETWProvidersManifests/Windows10/22H2/W10_22H2_Pro_20221115_19045.2251/WEPExplorer/Microsoft-Windows-Kernel-Process.xml) separates ProcessStart CreateTime and ProcessStop CreateTime/ExitTime FILETIME fields. These sources do not state a universal strict numerical ordering between header timestamp and provider payload across every ETW environment. This is not a claim that any negative offset is harmless.

The **default** `EtwLifetimes` verifier stays unchanged. Only the distinct `n12_app_lifetime.reduction(no_cdp_profile=True)` chooses `no_cdp_sysmon_corroboration=True`, requiring independent full-image Sysmon GUID-bound non-disputed complete process exit and exact ETW ExitTime match, a unique ETW start/stop sequence, full exact ETW start image, existing 1 ms Sysmon birth join, both FILETIME payload endpoints within capture, and strict increasing ETW start/stop header order. Only with this independent corroboration can the no-CDP diagnostic reconcile negative header-vs-payload offsets and the **exact 14-character** WebView stop prefix. The prefix alone is never sufficient. Missing or disputed Sysmon exit, wrong stop image, wrong process sequence, out-of-window payload and collector loss remain BLOCKED. No arbitrary skew tolerance or accepted write root is introduced.

**Also fixed:** the browser identity source incorrectly required `app.start <= launch`, despite `journey.mark("launch")` occurring before `journey.spawn`. It now requires `launch <= app.start <= ready`, rejecting pre-existing/stale apps and apps started after readiness. The synthetic birth/handle fixture was corrected.

New tests reproduce the redacted native offset *shape* without private raw process data, verify default stricter mode remains blocked, and reject missing/incorrect Sysmon stop, wrong ETW sequence/image, and early/late app birth.

## Decision boundary

**Source-only test PASS is not native Stage 1 PASS.** The historical native run stays **BLOCKED**. A **new, separate one-use source-pinned hosted-Windows no-CDP native measurement** is required to check actual unique browser/profile ancestry and complete shutdown; it may reveal additional blockers. The native workflow remains disabled, its last approval marker removed, and no installer, owner-device work, firewall change or full FileIO/network test is authorized.

Latest complete native N12 is still filesystem **FAIL**, network **FAIL**, file mutation coverage **BLOCKED**. Score unchanged: file mutation **3/4 (75%)**, R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**.
