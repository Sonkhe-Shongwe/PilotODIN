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

## Standalone collector calibration on hosted Windows

Use a disposable hosted Windows runner with Sysmon and Process Monitor already approved and configured. Complete collector setup before starting the measured interval. Use steps 2 and 3 below for Sysmon and Procmon settings. Keep all raw output in runner temp.

1. Start Procmon capture and record the UTC window start and the next Sysmon record ID from the channel. Run the fixture once and save its JSON output as the `calibration` field in the manifest. Allow time for collector flush after the fixture parent exits.
2. Record the UTC window end and the last Sysmon record ID. Stop Procmon and export the full file-system event capture. Export the inclusive Sysmon record range using `Export_P4_N12_Sysmon_Trace.ps1`.
3. Set `schema_version` to 1 and `disposable` to true. Record `start_utc`, `end_utc`, `sysmon_first_record`, `sysmon_last_record` and the three Procmon review flags from the manifest table. The standalone check needs only those fields and the fixture JSON.

~~~powershell
python qa/p4_native/n12_trace.py check-calibration $manifest $sysmonXml $procmonCsv $summary
~~~

Exit 0 confirms both collectors recorded the declared Python parent and child, executable hashes, child loopback TCP and UDP, and the expected file creation, write, resize, rename destination and deletion in the fixture. Exit 2 indicates blocked or invalid evidence. The report keeps native N12 acceptance pending. Repeat the two calibration bookends during the separately approved native capture.

## Collector requirements for the disposable Windows run

1. Finish building and staging the unpackaged app before the measured window. Use one UTC day. Use the approved exact build, fresh disposable profiles, a loopback backend and generated data. Independently take the initial snapshots and record the source commit and executable SHA-256.
2. Configure [Sysmon](https://learn.microsoft.com/en-us/windows/security/operating-system-security/sysmon/sysmon-events) to include process creation with SHA-256, process termination, TCP and UDP including loopback, and DNS if available. Keep the unfiltered sequence of operational-channel records from the initial checkpoint to the final checkpoint. A gap, in-window service/configuration change, or Sysmon error blocks clean evidence. Confirm the actual provider captures loopback TCP and UDP before relying on it.
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
