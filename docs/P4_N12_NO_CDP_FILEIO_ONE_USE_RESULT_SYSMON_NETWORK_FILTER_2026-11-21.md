# P4 R02.5 | Consumed one-use no-CDP FileIO baseline, blocked at initial Sysmon network calibration

**21 November 2026 | OWNER'S ONE-USE NATIVE AUTHORIZATION CONSUMED. FULL APP NOT LAUNCHED. NO PRODUCT FILEIO EVIDENCE COLLECTED.**

This is the authoritative result of the user-approved source-pinned first hosted-Windows no-CDP Full FileIO baseline. It supersedes the future-tense assumptions in the [preauthorization proposal](./P4_N12_NO_CDP_FILEIO_ONE_USE_CAPTURE_PREAUTH_REVIEW_2026-11-21.md). This was **one attempted run**, not a native filesystem pass and not authorization to retry. Never re-use the consumed marker.

## Exact provenance and execution boundary

- Reviewed source pinned: [`c6062b5c8c1e1d75e6dab1f91d515d21bcfdd089`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c6062b5c8c1e1d75e6dab1f91d515d21bcfdd089).
- Two-file activation: [`acc5e49729d27559daff9b1ad1b72a1c48bb7e88`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/acc5e49729d27559daff9b1ad1b72a1c48bb7e88), direct child of the reviewed source, changing **only** the disarmed workflow's single job condition and adding **one** new two-line approval marker `N12_NO_CDP_FILEIO_OWNER_APPROVAL.txt`. The source-pinned trusted hosted-Windows push and first-run preflight **PASSED**.
- One [GitHub Actions run **#44932378332**](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44932378332), attempt **1**, **COMPLETED FAILURE** at **2026-11-21 approximately 17:56 UTC**. A disposable `windows-2022` runner staged the isolated unpackaged Tauri QA executable and verified source, binary digest and Cargo lock before collector start. The compilation and dependency preflight completed successfully.
- [Workflow re-disarmed in `419f3b65ff52023575b74fc440e85c879429a8ea`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/419f3b65ff52023575b74fc440e85c879429a8ea) before the one-use job completed. The historical approval marker remains **CONSUMED**. The two previous native app workflows remain disabled. **No second native attempt was made.**

## What the failed native job actually captured

1. **17:56:29 UTC**: app-lifetime source/binary preflight **COMPLETED**.
2. **17:56:30 UTC**: capture boundary opening **COMPLETED**; approximately **17:56:31 UTC**, Kernel-File/Kernel-Process ETW collector **STARTED**.
3. Initial existing generated N12 calibration ran, with generated subprocess successful enough to return its fixture record. Its *independent Sysmon channel* did **not** contain the required child-scoped loopback TCP **or** UDP events. Two bounded Sysmon channel readings reported `missing_in_child_lifetime: ["tcp", "udp"]` and no matching or rejected TCP/UDP markers.
4. **17:56:43 UTC**: initial calibration **INTERRUPTED** with `initial Sysmon calibration blocked on read 2: child-loopback-tcp-or-udp-missing`. The guarded capture **failed closed before the app-lifetime-worker stage**. Therefore **PilotODIN/Tauri/WebView2 was never launched during this attempt**, and there are **no actual WebView2 process handles, actual product file writes, effective UDF, WebView-network path credits or runtime isolation observations** from it.
5. ETW stop checkpoint **COMPLETED**; the subsequent failure-path protected/immutable endpoints comparison returned `MATCH` and `unexpected_snapshot_changes: []`. That is evidence only about the bounded **initial failed calibration**, not file-mutation containment for any app run.
6. The dedicated no-CDP FileIO report was **never produced**, because the workflow did not reach Sysmon/ETW export and strict reduction. The `if: always()` reporting step completed with the explicit **no complete redacted diagnostic receipt (BLOCKED)** message; no raw ETW/owner-path artifact was uploaded. **Do not mistake the green reporting step for a green app capture.**

## Source defect consistent with the exact failure

The reviewed PowerShell wrapper built Sysmon with an initially correct `<NetworkConnect onmatch="exclude" />` entry, but on **`-AppLifetime`** or lifetime ETW control it replaced this with an empty `<NetworkConnect onmatch="include" />`. Under Microsoft's Sysmon filter semantics, `include` logs only matching events and `exclude` logs all events except matches. With no include rules, the prior network configuration supplies **no matching Event 3 records**. This is a **source-backed, highly plausible explanation** for the complete absence of generated child-scoped TCP and UDP Sysmon events. It was NOT independently isolated by a second actual Sysmon installation or app capture under the consumed approval.

- Official Microsoft references: [Sysmon configuration filters](https://learn.microsoft.com/en-us/windows/security/operating-system-security/sysmon/sysmon-configuration-files) and [Sysinternals Sysmon](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon).
- Source-only candidate correction [`cbf02629127cb723173ce56f80b1345d1b9b7822`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cbf02629127cb723173ce56f80b1345d1b9b7822): remove the `exclude` to `include` replacement so the reviewed **unfiltered Event 3 network capture** is retained in all app-lifetime modes. Do not filter out other external or generated events. This edits no product WebView2 storage code or filesystem allowlist.
- Corrected consumed-marker/source tests [`daaa8d2b19893d548921f8a59f7abe0a521a5636`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/daaa8d2b19893d548921f8a59f7abe0a521a5636) preserve the now-existing two-line consumed owner marker and require a disarmed workflow. [Source/synthetic CI **#44933130221**](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44933130221) **4/4 COMPLETED SUCCESS**: 1,037 Python passed, 6 skipped, 528 subtests; 104 frontend passed and Vite built; disposable browser and hosted-Windows generated ETW/FileIO and R03 passed. **None** of that reran the actual PilotODIN app or independently measured a newly active Sysmon Event 3 stream with the corrected config.

## Decision and next permitted action

**The single approved baseline was attempted and is consumed.** It did not reach actual PilotODIN app launch. Do not rerun workflow #44932378332, do not flip the disarmed job again, and do not reuse the existing approval marker. A next true native capture requires **a separately requested and explicitly granted one-use owner authorization**, a **fresh exact reviewed source SHA**, a new single-use marker/workflow activation contract (the old marker is already present), and independent review of known WebView2 external traffic, public logs and generated control handling.

Until then, only source/synthetic verification and documentation are permitted. A clean next generated Sysmon TCP/UDP calibration will be **necessary but insufficient**: still require every WebView2 original child handle, complete Kernel-File FileObject/IRP path/writer attribution, positive same-capture transient restore control, verified effective browser storage, zero unresolved/prohibited mutations and separately authorized full strict N12 acceptance.

**Official ledger unchanged:** file-mutation engineering **3/4 (75%)**, R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**. Earlier full native filesystem FAIL/network FAIL/FileIO coverage BLOCKED and 113 outside-root WebView-network write credits remain historical, not replaced by this failed pre-app calibration.
