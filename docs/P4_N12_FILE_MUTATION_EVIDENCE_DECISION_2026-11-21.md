# PilotODIN P4 | N12 file-mutation evidence architecture decision

**Date:** 21 November 2026  
**Branch:** `feature/live-dev-workspace-20261023`  
**Status:** Engineering direction recorded, **not** permission to execute native capture, change ACLs, alter user data, reclassify a failure or close P4.

## Decision

**Stop trying to qualify complete filesystem preservation solely through Process Monitor (ProcMon) CSV and process exit.** Keep ProcMon as a *positive-observation and path-attribution diagnostic*. Design the final protected-data case as three independent claims:

1. **Prevention:** on a disposable Windows fixture, a process running under a *deliberately restricted identity* cannot write, delete, rename or replace a fabricated protected file, while it can write to an explicitly permitted QA data home. An ACL denied to the same fully privileged owner identity alone is not adequate proof of process containment. The isolation mechanism, supported host and account model need design and fresh owner approval before execution.
2. **Preservation:** compare independent, full-tree before/after inventories and hashes of protected disposable roots, including a *positive write-and-restore control* that verifies the audit can detect transient mutation. Equal endpoint hashes alone do **not** prove that no transient write occurred.
3. **Observation / attribution:** use the existing ETW FileIO collector with independently verified loss counters, process identities, file-object/handle lifetime, rundown and operation classification; reject unresolved mutation paths and untracked actors. Use ProcMon as corroborating positive evidence, never as an independent proof of complete absence of writes.

**The existing N12 rules remain strict** until the acceptance approach is reviewed and explicitly authorized. The three claims above are a proposed architecture, **not** a substitute acceptance result.

## Source-level finding: the current A/B comparison cannot qualify under the current native capture wrapper

- `qa/p4_native/Invoke_P4_N12_Live_Calibration.ps1` currently writes `procmon_loss_reviewed = $false` in the focused storage window, with no verified path that changes it to true.
- `qa/p4_native/n12_trace.py::load_capture` flags incomplete ProcMon coverage on that manifest.
- `qa/p4_research/n12_webview_storage_probe.py::reduce` deliberately removes that issue when producing a **positive-path diagnostic**, while retaining `procmon_loss_reviewed: false`. Consequently its `REPRODUCED` means an observed positive destination, not a complete trace.
- `qa/p4_research/n12_webview_storage_compare.py::_verify` requires `procmon_loss_reviewed is True`, clean unresolved paths, verified shutdown, and a browser environment receipt. **Therefore the A/B comparator's `COMPARABLE_DIAGNOSTIC` condition is structurally unreachable with the present native collector configuration.** This is an incompatible *test contract*, not a new PilotODIN application defect. Do not run an ostensibly comparable second native arm until the proof contract has a viable implementation and a documented reason to perform that run.
- Do **not** set `procmon_loss_reviewed = true` merely to satisfy the comparison, ignore named pipes, convert a nonzero collector exit into success without evidence, or equate `REPRODUCED` with N12 acceptance.

## Verified observations and their limits

| Evidence | What was observed | What it does **not** prove |
| --- | --- | --- |
| [Generated ProcMon environment control #44678676279](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44678676279) | The pinned ProcMon exported both assigned `TMP` and `TEMP` values for the generated child, including a tab-delimited format. Recorder exit code 1; control BLOCKED on shutdown/loss. | That all browsers' inherited environment values are always visible in CSV, or exit 1 is a successful shutdown. |
| [Collector-only ProcMon #43458458941](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43458458941) | Recorder exit code 1 occurred without PilotODIN startup, after a quiet stop and readable exports. Window-close controls also reproduced exit code 1. | That PilotODIN caused the recorder status, or that a readable PML/CSV is complete. |
| [Focused WebView native #44847306630](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44847306630) | Unpackaged app built, launched and closed. Protected endpoint snapshots MATCHED. Two browser `CreateFile` events targeted ambient user-temp, one at startup and one at readiness. Browser `debug-netlog` flags corroborated. | Cause of the writes, absence of transient protected mutation, inherited `TEMP`, `TMP` or UDF contents, or complete trace coverage. |
| [Governing complete N12 #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) | Strict filesystem FAIL, network FAIL, file-mutation coverage BLOCKED despite equal protected endpoints; outside-path mutations and non-loopback browser activity were detected. | A complete negative protection guarantee. |

In the focused native capture, **10,231 named-pipe operation records** were unresolved by the drive-file path parser. Named pipes are not automatically disk-file mutations, but **their classification and process identity must be independently supported** before a future rule change. Do not suppress those events to obtain a green percentage.

The Process Monitor help documents `/WaitForIdle` and `/Terminate`, and notes that the latter commits outstanding buffered data before exit. It does **not** document that exit code 1 under the exact hosted workflow establishes complete capture. Official Windows process exit semantics alone cannot explain what ProcMon internally intended by exit 1. See [Microsoft Sysinternals ProcMon](https://learn.microsoft.com/sysinternals/downloads/procmon), [historical ProcMon scripting reference](https://documentation.help/Process-Monitor/Scripting_Process_Monitor.htm) and [Windows process exit semantics](https://learn.microsoft.com/windows/win32/procthread/terminating-a-process).

## Options compared

| Approach | Strength | Weakness / limit | Disposition |
| --- | --- | --- | --- |
| A. Continue making ProcMon the universal negative-coverage oracle | Existing positive filenames, process and operations are useful | No independent loss review in current wrapper; exit 1 recurs without app; unknown browser environment export; repeated tests cannot meet the A/B prerequisite | **Do not pursue as the principal safety gate** |
| B. Protected generated fixture under separate security principal with controlled file rights, plus file-integrity evidence | Can directly exercise actual *denial*, not just observe after-the-fact writes | Requires carefully designed identity, permission and cleanup guarantees. An admin or ownership-reclaim-capable process invalidates a simplistic deny ACL; no owner roots may be touched | **Design first, then seek fresh isolated-control approval** |
| C. ETW FileIO with independently validated loss and path attribution, alongside inventory and optional ProcMon positive diagnostics | Existing N12 groundwork and generated FileIO controls are strong; permits transparent strict incomplete-coverage verdicts | Path recovery for preopened handles, background writers and unclassified operations remains technically difficult; endpoint hashes do not replace ETW | **Use as measurement arm of B** |
| D. Separate Windows Sandbox or isolated VM | Strong host separation, useful for disposable adverse writes | May lack compatibility, nested virtualization or precise equivalence to the target standard Windows desktop deployment | **Future alternative, not presumed supported on hosted CI** |

Microsoft's [file access control](https://learn.microsoft.com/windows/security/identity-protection/access-control/access-control), [file system auditing](https://learn.microsoft.com/windows/security/threat-protection/auditing/audit-file-system) and [Windows Sandbox isolation](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-overview) documentation support these categories of controls. They do not certify this particular PilotODIN implementation.

## Next genuinely useful micro-step, source-only

**Specify the smallest disposable protected-root fixture and proof obligations, without running it:**

1. Exactly two synthetic folders: one nominal *protected* root with a known hash inventory and one *permitted* QA data home. No physical owner-app roots or original project data.
2. A generated writer under a proposed separate, least-privileged identity attempts a known **create, overwrite, truncate, rename, delete and write-and-restore** into the protected root. Only expected denials count. The same writer must successfully create in the permitted QA home.
3. Independently read the protected file's before/after identity, content hashes and metadata; use ETW known controls to prove the attempted mutation was observed. If ETW coverage, identity or required operation-path attribution is missing, keep **coverage BLOCKED** even if file protection denied the attempted write.
4. Demonstrate reliable permission reversion and disposable cleanup on a non-owner test environment. Only after source review, a one-use approval and verification of host support may that Windows control be activated.

**Stop rules:** no more full N12 runs solely to compare ProcMon environment parsing or to normalize its exit 1; no automatic A/B netlog follow-up; do not broaden permitted paths or suppress unknown actors. A future comparison requires an independently verifiable coverage mechanism, not a hard-coded true flag.

## Unchanged program status

- Official P4: **14/20 (70%)**.
- File-mutation: **3/4 (75%)**.
- N12: **0/2**; governing filesystem **FAIL**, network **FAIL**, coverage **BLOCKED**.
- R06 historical 74-file difference: unresolved, historical writer unknown.
- Native WebView one-use approval: consumed; workflow disarmed.
- No installer through P4–P7, no owner-device modification, no P5/P8 release authorization.
