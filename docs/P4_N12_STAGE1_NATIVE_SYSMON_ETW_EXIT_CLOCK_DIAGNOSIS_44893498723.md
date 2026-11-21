# PilotODIN P4 N12 | Exact native Sysmon/ETW exit mismatch, 21 November 2026

**Strict actual result: STAGE 1 BLOCKED.** The owner authorized **exactly one** unpackaged, source-pinned, no-CDP Windows startup/shutdown and Sysmon/ETW diagnostic on a disposable GitHub-hosted Windows runner. [Native run #44893498723](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44893498723), job `136814139499`, **COMPLETED FAILURE** because the N12 Stage 1 reducer correctly returned **BLOCKED**. This scoped experiment is **not** the full R02.5 FileIO/network acceptance and did not run an installer, touch the owner's device or protected owner data, change the firewall or begin Stage 2.

## Provenance, one-use boundary and build

- **Exact tested and compiled reviewed source:** `41eaa3b240d621491ed0aec3a7a8ae227d92a626`, the documentation-only child of the [4/4 successful diagnostic-code CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44891619664) source `c07d93fda2b36bbfa5e275e5ef1c327a31cbead1`.
- **One-use activation commit:** `d55a956fd4f691f91549fb574507325fad506505`, the approved source's direct child, changing **only** the lifetime workflow and adding the source/one-scope approval marker. The hosted workflow independently verified the parent, changed paths, first attempt and GitHub-hosted Windows identity before detaching to the exact reviewed source, with the separate no-CDP consent.
- **Immediate disarm:** `b94d0e73360e19981f857e1fc1fa1022b2176d6f`, restoring the **exact prior disabled workflow** and deleting the single-use marker. Confirmed workflow `if: false`, marker absent. No second run or replay authorized.
- **Real unpackaged Rust/Tauri compilation and staging: PASS.** Disposable QA identifier `com.pilotodin.p4isolatednativedev`; executable SHA-256 `c8f64822e1420b961d549474d05b5b2f8d47b9264c4dd7239f09d9a6fd27b83f`; Cargo.lock SHA-256 `6fda67bc612a241200d7a644e01f00d299ce7b38221caa032e686cedd195339d`. Startup, ready, ordinary close, export and reducer completed.

## What the actual no-CDP diagnostic isolated

The new `no_cdp_sysmon_diagnostic`, introduced at `c07d93f`, checks the **same eight original** source and lifetime prerequisites used for the fail-closed native gate and separately reports relative tick differences. **1 tick = 100 ns.** All failures below came from the original exact Sysmon-versus-ETW process-exit equality condition; **no other named Sysmon checks failed** for app or launcher.

| Scoped process | ETW birth minus Sysmon birth | ETW ExitTime minus Sysmon Event 5 UtcTime | Sysmon exit minus retained original handle exit | Failed check |
| --- | ---: | ---: | ---: | --- |
| Launcher | +6,393 ticks (+0.6393 ms) | **+32,932 ticks (+3.2932 ms)** | -32,932 ticks (-3.2932 ms) | `etw-exit-exactly-matches-sysmon` |
| PilotODIN app | +8,582 ticks (+0.8582 ms) | **+77,625 ticks (+7.7625 ms)** | -77,625 ticks (-7.7625 ms) | `etw-exit-exactly-matches-sysmon` |
| Six WebView children | role-aggregate only | all **six** nonzero, exact deltas not individually disclosed | no independent child handles | `etw-exit-exactly-matches-sysmon` (6) |
| One WebView network child | role-aggregate only | nonzero, exact delta not individually disclosed | no independent child handle | `etw-exit-exactly-matches-sysmon` (1) |

**Independent handle countercheck:** ETW payload birth and ETW ExitTime matched the retained original Windows handles' birth and exit **exactly (0 ticks)** for both app and launcher. The Sysmon birth join was within the existing 1 ms bound for both, not exactly equal. Neither Sysmon exit was missing or disputed; the ETW pair, sequence, full start executable image and capture bounds were not the failing named checks. For every one of the nine scoped lifetimes, only **`etw-exit-exactly-matches-sysmon`** failed among the diagnostic predicate checks. The different event-header timestamps and shortened stop executable prefixes still require independent safeguards; these observations cannot establish child identity alone.

Other actual evidence:
- Captured **one app, six WebView, one WebView network** scoped process, plus the launcher.
- App, launcher and all seven child ETW **start images exact-path-match**.
- ETW counters `events_lost=0`, `log_buffers_lost=0`, `realtime_buffers_lost=0`, `buffers_written=5`.
- **Protected snapshots MATCH**, with no unexpected changes; changes to disposable QA home/WebView/local were expected.
- Final reducer `issues`: `app-or-launcher-handle-unverified`, `no-cdp-prior-lifetime-evidence-unverified`, `no-cdp-sysmon-lifetime-unverified`. These are downstream blocked gates, **not** proof of an app crash.
- `no_cdp_profile_identity.status=BLOCKED` because earlier lifetime proof was rejected; `timing_comparisons=[]`; `native_N12_acceptance=NOT_EVALUATED`, `file_event_coverage=NOT_EVALUATED`, `network_isolation=NOT_EVALUATED`.

## Timestamp source semantics and what is not yet proven

The repository's `qa/p4_native/n12_trace.py` intentionally parses Sysmon Event ID 5 **EventData `UtcTime`**, **not** channel metadata `SystemTime`. Its `Process.end` is keyed to the GUID/PID and verified image, when available. The ETW stop event exposes provider `ExitTime` as FILETIME; the original app/launcher Windows-handle times also corroborate the ETW payload independently. [Microsoft Sysmon documentation](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon) documents Event 5's process termination event and its `UtcTime`, ProcessGuid and ProcessId. [Microsoft's Sysmon event manifest](https://github.com/microsoft/SysmonCommon/blob/main/manifest.xml) separately defines Event 5's UtcTime string; [Microsoft's GetProcessTimes documentation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes) documents actual process handle exit FILETIME; [ETW kernel-process manifest field schema](https://github.com/nasbench/EVTX-ETW-Resources/blob/main/ETWProvidersManifests/Windows10/22H2/W10_22H2_Pro_20221115_19045.2251/WEPExplorer/Microsoft-Windows-Kernel-Process.xml) lists provider ExitTime FILETIME.

These references **do not promise cross-source tick-for-tick equality**. The measured divergences could reflect different capture/termination timestamps or measurement semantics; that remains a **hypothesis**, not proof of harmlessness, a certified maximum deviation or a reason to silently weaken the test. A `+7.7625 ms` app difference is observed; it must **not** become a blanket 8 ms acceptance tolerance.

## Correct next engineering action

**Source-only timestamp contract and independent witness design review.** Preserve GUID/PID/full-path, unique ETW start/stop sequence and ancestry, capture bounds, loss controls, original app/launcher handle equality and protected snapshots. Assess what can independently confirm the complete child lifetimes, not merely a Sysmon Event 5 clock value. Write negative fixtures for missing/disputed Sysmon exits, PID reuse, duplicate ETW sequences, wrong child executable, incompatible chronology and overlap, along with the observed **3.2932 ms and 7.7625 ms** signed relative offsets. The reviewer must explicitly justify any alternative cross-source clock relationship rather than setting a tolerance from this small sample. **No verifier relaxation, new native capture, native build, Stage 2, firewall or installer is authorized by this documentation.**

**Ledger unchanged:** Stage 1 **BLOCKED**; file mutation **3/4 (75%)**, R02.5 **0/5**, desktop network **2/3**, N12 **0/2**; P4 **14/20 (70%)**. Latest approved **complete** native N12 [#44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains filesystem **FAIL**, network **FAIL**, FileIO mutation coverage **BLOCKED**.
