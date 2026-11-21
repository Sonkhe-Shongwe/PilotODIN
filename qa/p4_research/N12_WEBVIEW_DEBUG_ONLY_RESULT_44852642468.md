# PilotODIN N12 | One-use WebView2 debug-only storage diagnostic

**21 November 2026** | [Hosted Windows Server 2022 run #44852642468](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852642468) | **COMPLETED with diagnostic BLOCKED; positive browser temp creates reproduced.**

## Approval, source, binary and guard

- Owner said **"okay next you have authorization"** after the proposal to investigate ambient WebView2 temporary-file writes. Interpreted narrowly as **one** source-pinned, hosted Windows QA *unpackaged* build and *one* startup/readiness/graceful close diagnostic, with debugger required by CDP but **without netlog**.
- Reviewed source `0e13595517c5b15501df54232ec634804693c13f`; exact-source routine preflight [#44852389277](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852389277) **4/4 green**. New wrapper `StorageVariant` is threaded identically through capture and reduce and rejects non-storage use.
- Direct child one-use activation `f30717b89d8d791799e013e9fa95de490205ab70` changed **only** the new `N12_WEBVIEW_STORAGE_DEBUG_ONLY_APPROVAL.txt` marker and the workflow's one-use gate. Native run ID `44852642468`, attempt **1**, checkout detached to reviewed source.
- Executable SHA256 `801e3f6d6317472f7d33b322f131bfa1b5666a8d7fd18b3f63fae294f2f2bbe1`; WebView2 runtime version `131.0.2903.86`. `browser_variant_corroboration=agrees`, remote debugger **present**, netlog **absent** in the independently observed browser command line.
- Workflow immediately disabled again at source `358e3bab4edfff8b8fc6ce8ac0b6cb72eea60453`. No restart or repeat and no other native app build.
- Run **conclusion FAILURE** because its strict focused reducer returned **BLOCKED**. Full N12 acceptance was **not** run. No installer, owner device/data, ACL or firewall action.

## What actually completed

The runner succeeded in approval/source validation, synthetic controls, required dependencies, Rust unpackaged QA build, Windows app startup, readiness, graceful close, app handle exit, WebView profile exit, process cleanup, and safe redacted trace reduction. Protected full-tree endpoint snapshot comparison was **MATCH**; no protected-operation details were positively identified in this focused capture, but this is **not** proof that there were no transient protected writes.

The ProcMon stop command succeeded, the capture process exited with **code 1**, and the closed PML (~297 MB) and CSV (~115 MB) were readable. The status was **`procmon_capture_exit_status=NONZERO_EXIT`** and `procmon_shutdown_verified=false`. `procmon_loss_reviewed=false`. Thus the recorder is not a trustworthy **negative complete-coverage** oracle. There was no reusable raw trace artifact attached to the GitHub run; only the redacted report in the job log.

## Positive storage observations

| Field | Observed value |
| --- | --- |
| Storage variant | `debug-only`; browser debugger flag present, **netlog absent** |
| Ambient WebView browser `CreateFile` | **2** in **user-temp** |
| File type | **temporary** (`.tmp`) |
| Stage | **2 during `ready-probe`**; none classified as startup |
| Distinct normalized path strings | **2** |
| Paths observed in multiple stages | **0** |
| Browser identity | Verified through CDP PID, role and lifetime corroboration |
| Known generated create controls | `scratch=true`, `user-temp=true` |
| TMP startup control | **Not verified** (`scratch=start-record-unobserved`, `browser=tmp-not-observed`) |
| Browser Process Start environment | Nonempty field, but **no recognizable assignment tokens** for `TEMP`, `TMP`, `WEBVIEW2_USER_DATA_FOLDER` |
| Original snapshot comparison | **MATCH**, endpoints only |
| Filesystem object identity | **Not verified** |
| Collector completeness | **Not verified** |

**Interpretation:** The measured class of browser ambient temp creates **exists without the netlog flag**. Therefore a netlog switch is **not a necessary condition for all browser ambient temp-file creation** under this debug-only QA activity. The two created path strings are different *within the new capture*, not proven distinct file objects, and no private filenames are exposed. This is **not a direct causal A/B result** because the earlier debug-netlog [#44847306630](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44847306630) used a different reviewed source/binary, different retained report fields, no independent loss review and browser TMP controls were missing.

For comparison, the historical debug-netlog positive report saw **two browser `.tmp` creates in user-temp, one startup and one ready-probe**. Under debug-only both happened during ready-probe. The timing difference could arise from CDP readiness, lifecycle, background runtime state, source differences or ordinary variability; the data cannot distinguish these. Both variants retained the CDP remote debugger for the readiness/close driver. **Do not conclude that normal production WebView2 without CDP has been tested.**

## Why verdict remains BLOCKED

- `issues=[procmon-shutdown-unverified]`: capture process exited with code 1 despite successful stop command and readable export.
- `file_coverage_issues=[file-mutation-path-unresolved, scoped-create-result-unresolved]`: unresolved path/operation evidence was **not** exempted or allowlisted.
- **10,121 unresolved named-pipe operation records**, separately counted: app write 136; webview ambiguous create 4; webview write 7,112; webview-network write 2,869. **Other unresolved path count = 0 in this focused reducer**. Named-pipe records must not be relabeled as disk mutations or silently discarded as irrelevant.
- `browser_startup_tmp=unverified` and `startup_tmp_control_verified=false`; a nonempty exported environment did not produce a verifiable browser TMP path.
- `storage_context_is_acceptance_evidence=false`; no network-isolation claim and no full-journey FileIO acceptance.

## Decision and next meaningful source-only action

**Eliminate netlog as the sole explanation**, not all debugger instrumentation. Both actual captures used **remote debugging**, and in this run the creates occurred during the **CDP readiness stage**. A higher-value next source-only micro-step is to design a **no-CDP, production-parity readiness and graceful close pathway** using existing Tauri/JS lifecycle bridge events and independently observed browser process startup, without losing close-guard behavior. Review whether this is feasible **before** building another native app. If not feasible, stop and record the limitation; do not add guessed browser flags, widen write allowlists, suppress FileIO gaps or repeat previous traces.

This design must distinguish QA driver-induced writes from baseline browser startup while retaining a separately authorized one-use native test gate. It must not claim full N12 acceptance or solve external WebView2 DNS/HTTPS/UDP egress (the prior complete N12 network **FAIL** remains). No additional owner authorization is available from this already consumed approval.

**Unchanged P4 ledger:** P4 **14/20 (70%)**; file-mutation **3/4 (75%)**; network isolation **2/3 (67%)**; N12 **0/2**; original owner data **0/2**. Governing full-journey N12 [#44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains **filesystem FAIL, network FAIL, file-mutation coverage BLOCKED**.
