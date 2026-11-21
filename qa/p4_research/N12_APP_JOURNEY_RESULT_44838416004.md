# PilotODIN N12 | Second one-use hosted Windows acceptance result

**21 November 2026 checkpoint (UTC run completed 20 November).** Exact-source GitHub-hosted Windows Server 2022 [run 44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004), attempt 1: **FAILED the strict acceptance gate**, after the full application journey and combined reduction completed. This run is consumed. The workflow is disarmed again. **No automatic retry.**

## Source and evidence identity

- Reviewed code source: `e21bcdc579456bb02016fb0b2cb86744a287edb5`.
- Direct-child one-use activation: `6589ce8825c9116f102c57ca3b0c2b1c06a989cc`.
- Executable SHA-256: `b316dc6ef2111889572f6d77a67de021534b356f5e5deee1db8facc16dcbacdd`.
- ETW JSONL export SHA-256: `cfa0aa13e8ea6312d27ae548f871d5b950201bceb9ecae41ea27aa525c02957d`.
- FileIO rundown SHA-256: `3230a7307eed1a750ed152c3ae55831d43e8e95f91f58eedd7260782436c7fd9`.
- Temporary generated CSV and staged unpackaged QA identity only. No owner data, physical owner-device run, production installer or live firewall enforcement.

## What was established

| Check | Result | Evidence limit |
| --- | --- | --- |
| One-use approval, prebuild calibration, dependency checks and compiled unpackaged QA executable | PASS | Source pinned and executable digest recorded |
| Native first-launch and relaunch driver | Completed both with success | Real native driver passed; not a full acceptance decision |
| Complete protected before/after fingerprints | MATCH | No endpoint changes; does not rule out intermediate writes |
| Initial and final Sysmon calibration | PASS on read 1 | Generated calibration only |
| ETW timestamp diagnostic | 1,550,275 events in bounds, zero before/after, zero invalid tick or malformed JSON rows | No timing fault on this attempt; earlier first run's fault remains unexplained |
| Combined ETW file/network reduction | Completed | Produced definitive FAIL/BLOCKED for this run |
| FileIO rundown background comparison | Completed | Recovered some names but unresolved operations remain |
| Official N12 acceptance | **0/2** | No P4 acceptance points earned |

The previous approved [run 44817701849](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44817701849) stopped on an event timestamp outside capture. **That condition did not recur.** We did not change the strict timestamp reducer, discard any events, adjust bounds or prove a permanent fix. The digest-verified diagnostic reported `NO_TIMESTAMP_BOUNDARY_FAULT_OBSERVED`.

## Governing audit: FAIL, FAIL, BLOCKED

- **Filesystem: FAIL.** Recorded out-of-scope operations include **8 WebView creates, 4 WebView overwrites, 4 WebView writes**, **1 backend write to the source checkout**, and **23 out-of-scope unsupported WebView operations**. These are counts by reducer category, not 40 confirmed content writes. The optional WebView request-time comparison separately identified **113 out-of-scope WebView-network write candidates** in `other-path`; it did not replace the ordinary verdict.
- **File-operation coverage: BLOCKED** with issue `etw-mutation-coverage-unresolved`. The ordinary audit reported 4,190 `other:write:path-missing`, 1,327 `other:resize:path-missing`, 227,087 `webview-network:write:path-missing` and other unresolved categories. FileIO rundown corroborated 78 outside-tracked background paths but left 4,112 background write paths unresolved and 42 missing process lifetimes. Do not treat matching endpoint hashes as clean mutation coverage.
- **Network: FAIL.** Sysmon saw **4 non-loopback WebView-network events** (three UDP and one TCP), including DNS/53 and HTTPS/443. One UDP/443 event was not attributed in the browser netlog. There were also one unexpected backend loopback and three WebView unexpected loopback connections. Browser netlogs linked two DNS events and HTTPS to documented Edge service hosts, but **documentation of the service does not grant a policy exception**. Three WebView loopback connections matched QA Tauri IPC close requests.
- This run's `sysmon_and_lifecycle_issues` was **empty**, and app handles matched both native processes. Each launch still had one `etw-stop-image-conflict` among child WebView lifetimes. The previous run's `app-lifecycle-does-not-match-journey` did **not** recur. Do not erase the earlier diagnostic until reproducibility is established.

## Engineering priorities and next approval gate

1. **Fix out-of-scope writes in code or enforce the established isolation boundaries without relaxing protected-path policy.** Review WebView2's ambient user-local and user-temp targets, its isolated profile and the single backend source-checkout write. Preserve actual provenance and fail on unapproved paths.
2. **Address WebView service egress.** Distinguish permitted local Tauri IPC from external DNS/HTTPS/QUIC. An external blocking rule and its before/during/after connectivity proof require their own separately authorised live firewall test. Do not silently allow Edge service hosts.
3. **Resolve remaining FileIO attribution.** Use the completed path-gap diagnostics and rundown evidence. The scoped 78 recovered paths do not satisfy the requirement for all successful file mutations.
4. **No routine native rerun.** Only request another source-pinned one-use native approval after a named product or evidence fix predicts a measurable result. The two existing owner-approved runs are consumed.

**Score held:** product audit fixes 7/7, file-mutation coverage 3/4 (75%), network isolation 2/3 (67%), original owner-data preservation 0/2, N12 acceptance 0/2, official P4 **14/20 (70%)**.

[Source checkpoint](./N12_ETW_BOUNDARY_DIAGNOSTIC_2026-11-21.md) · [Current handoff](../../docs/SESSION_HANDOFF_CURRENT.md) · [GitHub run](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004).
