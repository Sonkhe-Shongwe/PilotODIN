# PilotODIN P4 | No-CDP browser identity: source-only contract

**21 November 2026.** This is a pure read-only verifier for a future separately approved N12 capture, not evidence of native execution or filesystem/network acceptance.

## Requirement and decision

The existing storage reducer relies on `cdp_browser_pid`. Dropping CDP without replacing that identity would let a WebView renderer or reused PID masquerade as the actual browser. The selected approach uses the already implemented Sysmon GUID process tree and `EtwLifetimes` image/start/stop/parent-sequence corroboration, linked to a verified app executable SHA and Windows handle, plus an exact disposable `--user-data-dir` profile. No raw paths, PIDs or commands enter the redacted receipt.

## Code and bounded checks

- `qa/p4_research/n12_no_cdp_browser_identity.py` returns one internal browser identity only when the app, exact browser profile, process ancestry, untyped browser role, creation/exit ordering and ETW parent sequence all agree. A missing, ambiguous or duplicate browser, missing process role, missing/duplicate/malformed profile argument, changed app hash, unsupported debug switch or ETW conflict blocks.
- `tests/test_p4_n12_no_cdp_browser_identity.py` uses generated Sysmon processes and a labelled fake ETW validator. It verifies positive classification and negative cases without process launch, permission changes, proprietary data or network access.
- The code is not called from `n12_app_lifetime.py` or `n12_webview_storage_probe.py` and does not replace CDP readiness. A positive source receipt explicitly returns `native_N12_acceptance=NOT_EVALUATED`, `file_event_coverage=NOT_EVALUATED`, and `network_isolation=NOT_EVALUATED`. Real independent OS capture and collector completeness have not been established.

## Exact remaining integration checkpoint

Before any native run, in a source-reviewed one-use design, provision a fresh held-open `app.log` identity before process spawn, wait for the existing guarded close-listener acknowledgement, verify unique native main-window identity, and after normal close bind the browser with real `EtwLifetimes` plus the app's original process-handle witness. Remove port-9331 readiness/exit assumptions only with an equivalent independently checked lifecycle. Do not accept unobserved browser-command profile tokens or relax the strict event-loss checks when the real WebView2 runtime uses a different command-line structure. Ambiguity is a stop condition requiring evidence, not a reason to guess.

No native capture, restricted token, ACL change, firewall change, installer, download, owner-machine action or CI workflow dispatch is authorised by this record. The historical N12 results remain filesystem FAIL, network FAIL, coverage BLOCKED. P4 14/20 (70%), file-mutation 3/4 (75%), N12 0/2 (0%).
