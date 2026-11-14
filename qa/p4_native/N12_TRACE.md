# N12 Windows trace

The trace answers two questions for a specific disposable run. Which processes made network connections, and did the app or any other process write outside its declared scope? The prior WebView2 port 443 observation stays unattributed until there is separate evidence for its destination and purpose.

## Status and use

The scripts prepare and reduce evidence. The regular Windows P4 job exercises the fixture, but the native trace is a separate run. Its machine needs Sysmon and Process Monitor configured and calibrated before PilotODIN launches. The scripts leave audit configuration and installed software alone.

| Input or tool | Purpose |
| --- | --- |
| n12_calibration.py | Starts one child that creates a fixture, writes in place, truncates, renames and deletes it. The child also sends one TCP and one UDP message to the parent's loopback listeners. |
| Export_P4_N12_Sysmon_Trace.ps1 | Reads an inclusive range of event record IDs from the Sysmon operational channel into a new XML file. |
| n12_trace.py check-calibration | Checks one generated fixture against both collectors before an app journey. The summary reports calibration coverage and omits raw paths and endpoints. |
| n12_trace.py snapshot | Hashes protected and synthetic paths, including relative file and directory names, before and after the test. Records an absent path distinctly and rejects reparse points. |
| n12_trace.py audit | Matches the two app launches to Sysmon image hashes, builds process lineage, checks calibration and processes the network and file records. The summary omits raw endpoints, process identifiers, command lines and file paths. |
| n12_fileio_rundown.exe | Uses native OpenTraceW/ProcessTrace and TDH to decode stop-time Kernel FileIO name records into private key/path JSONL. |
| n12_trace.py check-etw-preopened-rundown | Feeds the actual native rundown and ETW event export through strict file-mutation correlation for the generated protected/outside pre-opened controls. The redacted report separates control results from unrelated global blockers. |

## Standalone collector calibration on hosted Windows

Use a disposable hosted Windows runner with Sysmon and Process Monitor already approved and configured. Complete collector setup before starting the measured interval. Use steps 2 and 3 below for Sysmon and Procmon settings. Keep all raw output in runner temp.

1. Start Procmon capture and record the UTC window start and the next Sysmon record ID from the channel. Run the fixture once and save its JSON output as the `calibration` field in the manifest. Allow time for collector flush after the fixture parent exits.
2. Record the UTC window end and the last Sysmon record ID. Stop Procmon and export the full file-system event capture. Export the inclusive Sysmon record range using `Export_P4_N12_Sysmon_Trace.ps1`.
3. Set `schema_version` to 1 and `disposable` to true. Record `start_utc`, `end_utc`, `sysmon_first_record`, `sysmon_last_record` and the three Procmon review flags from the manifest table. The standalone check needs only those fields and the fixture JSON.

~~~powershell
python qa/p4_native/n12_trace.py check-calibration $manifest $sysmonXml $procmonCsv $summary
~~~

Exit 0 confirms both collectors recorded the declared Python parent and child, executable hashes, child loopback TCP and UDP, and the expected file creation, write, resize, rename destination and deletion in the fixture. Exit 2 indicates blocked or invalid evidence. The report keeps native N12 acceptance pending. Repeat the two calibration bookends during the separately approved native capture.

### Diagnose blocked Process Monitor coverage

- `unresolved_file_paths` groups blocking rows by process role, mutation, source or destination field, and path form. It includes counts only for those groups. Review the corresponding rows privately in runner temp before adding path handling. An unrecognised path still blocks coverage, including a rename or link that could affect a protected root.
- Record stop-command, capture-process and export outcomes separately. [Run #43458458941](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43458458941) observed capture exit code 1 despite a successful stop command, readable export and matching fixture events. Keep its diagnostic disposition. [Microsoft's stop procedure](https://learn.microsoft.com/en-us/troubleshoot/windows-client/shell-experience/troubleshoot-apps-start-failure-use-process-monitor) does not establish what that exit code means.
- Keep `procmon_loss_reviewed` false if the available evidence is a readable export and observed fixture markers. Those checks establish the presence of specific events. To evaluate a separate source for continuity, [Windows ETW exposes event and buffer loss counters](https://learn.microsoft.com/en-us/windows/desktop/ETW/event-trace-properties). A candidate file-I/O collector must demonstrate the same five mutations, process identity and path attribution, including cross-root moves and writes by other processes. Its counters describe its own trace. Require evidence for the source used in the audit before changing the coverage gate.

### Reduce combined ETW and Sysmon evidence

For a standalone collector rehearsal, the disabled [one-time workflow](../../.github/workflows/p4-n12-live-calibration.yml) is staged to provision the reviewed Sysmon binary and run the generated fixture with built-in ETW. A new owner-approved launch must bind to the reviewed parent commit. The runner checks the exact file mutations and loopback events with `check-calibration-etw`, and keeps raw evidence in runner temp. This rehearsal uses generated files and does not launch PilotODIN. It is separate from the startup-to-exit audit below.

~~~powershell
python qa/p4_native/n12_trace.py audit-etw $manifest $sysmonXml $etwJsonl $before $after $summary
~~~

The ETW input is UTF-8 JSONL in the format emitted by the synthetic Windows probe. Each row supplies `ticks` (UTC .NET ticks), `pid`, `id`, `lifecycle` and the event `data`. The manifest's `etw` section supplies `schema_version: 1`, `start_utc`, `end_utc`, `events_sha256`, `volume_devices` (drive to NT device name), and `counters` from the stopped ETW session (`events_lost`, `log_buffers_lost`, `realtime_buffers_lost`, `buffers_written`). Keep the event export and device map private. Resolve device mappings on the capture host.

The audit checks ETW loss, export integrity, completion status, and both endpoints of tracked moves. It joins scoped ETW processes to Sysmon by PID and a unique birth within 10 ms, then applies the existing write rules and before/after snapshots. A detected protected mutation fails the filesystem check even if its writer was running before capture. Missing attribution and unsupported operations can also block coverage. Drive paths, DOS extended prefixes and declared NT device names are supported. Short-name aliases and reparse-point transitions remain unsupported. Native collector orchestration and startup-to-exit acceptance remain pending.

### Strict file-key rundown input

A full strict audit may supply the native stop-time FileIO rundown as a separate JSONL file. Keep the WPR ETL and decoded paths in the disposable runner's private temp directory. Run the native consumer against that ETL:

~~~powershell
n12_fileio_rundown.exe $fileIoEtl $rundownJsonl
~~~

The WPR stop must occur while the companion ETW event session is still recording. The collector records the stop-completion upper bound as etw.rundown_stop_utc; the ETW session is stopped only afterward. Record the rundown file's SHA-256 as etw.rundown_sha256 in the capture manifest, then pass the exact file to the reducer:

~~~powershell
python qa/p4_native/n12_trace.py audit-etw $manifest $sysmonXml $etwJsonl $before $after $summary --rundown $rundownJsonl
~~~

The same optional --rundown input is supported by check-etw-preflight. The hosted pre-opened control workflow also invokes check-etw-preopened-rundown with the original probe capture JSON, the exact ETW event export and the same native rundown JSONL. The new command calls the strict inspect_etw_files reducer, verifies that both control FileKeys were actually recovered by that reducer, checks the protected-write violation and outside-root classification, and requires zero unresolved mutations for those two controls. The collector process receives a fixture-scoped known lifetime because it predates the ETW session; this is test-harness identity, not application process attribution.

The reducer accepts only recognised native decoder records (tdh+raw-schema, tdh or raw-schema-v2), verifies the manifest-pinned digest, and requires etw.start_utc <= etw.rundown_stop_utc <= etw.end_utc. A rundown outside the companion ETW observation window is rejected. Because WPR stops before the companion ETW session, the event export covers transitions after the rundown snapshot through ETW stop. Event 10 NameCreate is corroborating evidence only when its canonical path is unique and exactly matches the rundown path. A conflicting or ambiguous NameCreate, Event 11 NameDelete, or an in-window create/open, close, rename, delete, link or unsupported transition invalidates the mapping. The guard scans events through ETW stop, including events after the Sysmon audit end. Duplicate rundown records for the same canonical path are harmless; conflicting, invalid or reused keys remain unresolved.

A control integration result of PASS is not a clean global audit. The report keeps unrelated protected-root violations and unresolved mutations visible; any such records keep strict coverage BLOCKED. This is a generated hosted fixture only, not a native N12 acceptance pass.


### Hosted strict reducer control integration

The focused Windows workflow runs the following command after native ProcessTrace decoding and the independent pre-opened path report:

~~~powershell
python qa/p4_native/n12_trace.py check-etw-preopened-rundown $reducerManifest $captureJson $etwJsonl --rundown $rundownJsonl
~~~

The command uses the same strict file-mutation reducer as the audit, and checks that the two FileKeys identified by the generated control requests are among the keys the reducer actually recovered. It requires one protected pre-opened write violation, the outside control to remain outside protected roots, and no unresolved mutation for either control. The collector PID is assigned a fixture-only known lifetime because it exists before ETW starts; this does not establish a PilotODIN process identity.

The redacted report separately preserves unrelated protected-root violations and unrelated unresolved mutations. A control-specific PASS can therefore coexist with global strict coverage BLOCKED. The test is deliberately not an overall N12 acceptance pass.

## Collector requirements for the disposable Windows run

1. Finish building and staging the unpackaged app before the measured window. Use one UTC day. Use the approved exact build, fresh disposable profiles, a loopback backend and generated data. Independently take the initial snapshots and record the source commit and executable SHA-256.
2. Configure [Sysmon](https://learn.microsoft.com/en-us/windows/security/operating-system-security/sysmon/sysmon-events) to include process creation with SHA-256, process termination, TCP and UDP including loopback, and DNS if available. Keep the unfiltered sequence of operational-channel records from the initial checkpoint to the final checkpoint. A gap, in-window service/configuration change, or Sysmon error blocks clean evidence. Confirm the actual provider captures loopback TCP and UDP before relying on it.

   If stop-time path recovery is required, also run a named WPR FileIO trace across the same measured window. Stop WPR while the companion logman ETW session is still active, then stop logman; this keeps the event stream open through the rundown snapshot. Record rundown_stop_utc from the WPR stop completion, decode the ETL with n12_fileio_rundown.exe, and hash the resulting JSONL into etw.rundown_sha256. The reducer rejects a stop timestamp outside the ETW start/end window. Keep raw ETL and JSONL private. Event 10 NameCreate may corroborate a rundown path only when the canonical name is unique and exactly matches the rundown; conflicting or ambiguous names invalidate it. Event 11 NameDelete and the existing in-window open/create, close, rename, delete, link and unsupported transitions remain ineligible for rundown fallback.
3. Record the whole window with [Process Monitor](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon) using a backing file and All events. Keep file-system events from all writers, including other processes that might write to protected roots. Export an English UTF-8 CSV with the columns Time of Day, PID, Operation, Path, Result, Detail and Process Name. Use a Windows clock set to UTC with 24-hour time. Review capture continuity and loss indicators before setting the manifest coverage flags. Keep the backing file and export in runner temp.
4. Run the calibration fixture twice, once before the idle marker and again after app and backend exit. Use a fresh directory for each invocation. Add its JSON result to the process manifest and its port to the loopback allowlist. If the Sysmon export lacks either loopback protocol or the Procmon export lacks any of the five file operations, treat the capture as blocked. This includes collector configurations that omit loopback UDP.
5. Capture idle, first launch, native Quality review, close, reopen and final exit. Record each marker immediately before the action, and retain the app/backend/driver PIDs and exact executable paths. Wait for WebView descendants to terminate. For the isolated WebView2 process use the [diagnostic NetLog flags](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags) with the Default capture level. Use distinct NetLog output paths for the first launch and relaunch. Retain raw files privately and compare source port, destination, time and NetLog request dependencies to attribute recurring connections. Keep a connection unattributed when the evidence cannot establish a purpose.
6. After the second calibration and collector flush, collect the final snapshots and run the reducer. Publish only the reviewed redacted summary. The Sysmon checks cover observed connections. Blocked attempts require separate evidence, for example Windows Filtering Platform events if enabled for the approved run. The current reducer does not assign request purpose automatically or certify native N12.

## Manifest fields

| Field | Value |
| --- | --- |
| schema_version, disposable | 1 and true |
| source_sha, executable_sha256 | Exact lowercase Git commit and executable SHA-256 |
| start_utc, end_utc | ISO 8601 UTC boundaries on one day |
| markers | UTC timestamps for idle, launch, quality, close, reopen and exit, in order |
| sysmon_first_record, sysmon_last_record | Inclusive event record IDs, recorded independently of the exported file |
| procmon_all_events, procmon_loss_reviewed, procmon_clock_utc | Set true after reviewing the capture and clock settings |
| etw.rundown_sha256 | Optional lowercase SHA-256 of the native rundown JSONL when --rundown is supplied |
| etw.rundown_stop_utc | Required with rundown_sha256; WPR stop-completion timestamp inside the ETW start/end window |
| processes | Entries with role, pid and image. Provide two app entries, one backend, at least one driver, and the two complete calibration JSON objects. |
| loopback_ports | Explicit service and calibration ports |
| protected_roots, observed_roots | Maps from short neutral labels to absolute Windows paths. Include both protected app identities and an immutable synthetic import file. |
| immutable_observed | Nonempty list of labels from observed_roots |
| permitted_writes | Exact disposable paths for each applicable role: app, backend, driver, calibration, webview, webview-network, helper. A missing role has no permitted writes. |

Use separate input and output filenames. Snapshot, export and private endpoint outputs are create-new only.

~~~powershell
python qa/p4_native/n12_trace.py snapshot $manifest $before
python qa/p4_native/n12_calibration.py $firstCalibrationDirectory
python qa/p4_native/n12_calibration.py $lastCalibrationDirectory
./qa/p4_native/Export_P4_N12_Sysmon_Trace.ps1 -FirstRecord $firstRecord -LastRecord $lastRecord -OutputFile $sysmonXml
python qa/p4_native/n12_trace.py snapshot $manifest $after
python qa/p4_native/n12_trace.py audit $manifest $sysmonXml $procmonCsv $before $after $summary --private-endpoints $privateEndpointFile
~~~

The command list shows the tool entry points. Follow the numbered sequence when collecting evidence. An audit exit of 0 means both checks passed within the reducer's scope. Exit 1 means the evidence reported a failure or an unattributed connection. Exit 2 means the evidence was malformed or coverage was incomplete. Keep the scope, historical port 443 observation and original R06 result in the continuation record even if a new run passes.
