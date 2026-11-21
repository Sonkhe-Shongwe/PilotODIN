# PilotODIN P4 | No-CDP browser identity: source-only contract

**21 November 2026.** This is a pure read-only verifier for a future separately approved N12 capture, not evidence of native execution or filesystem/network acceptance.

## Requirement and decision

The existing storage reducer relies on `cdp_browser_pid`. Dropping CDP without replacing that identity would let a WebView renderer or reused PID masquerade as the actual browser. The selected approach uses the already implemented Sysmon GUID process tree and `EtwLifetimes` image/start/stop/parent-sequence corroboration, linked to a verified app executable SHA and Windows handle, plus an exact disposable `--user-data-dir` profile. No raw paths, PIDs or commands enter the redacted receipt.

## Code and bounded checks

- `qa/p4_research/n12_no_cdp_browser_identity.py` returns one internal browser identity only when the app, exact browser profile, process ancestry, untyped browser role, creation/exit ordering and ETW parent sequence all agree. A missing, ambiguous or duplicate browser, missing process role, missing/duplicate/malformed profile argument, changed app hash, unsupported debug switch or ETW conflict blocks.
- `tests/test_p4_n12_no_cdp_browser_identity.py` uses generated Sysmon processes and a labelled fake ETW validator. It verifies positive classification and negative cases without process launch, permission changes, proprietary data or network access.
- The code is not called from `n12_app_lifetime.py` or `n12_webview_storage_probe.py` and does not replace CDP readiness. A positive source receipt explicitly returns `native_N12_acceptance=NOT_EVALUATED`, `file_event_coverage=NOT_EVALUATED`, and `network_isolation=NOT_EVALUATED`. Real independent OS capture and collector completeness have not been established.

## 21 November exact-source test reconciliation

The previous implementation was not in the P4 CI path filter. [Source commit `969cb4b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/969cb4beffd866425b8e52188c9de7a075eeb674) added this existing module and test to the routine P4 Python and generated Windows fixture selection. [Run #44874237979](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44874237979) completed 4/4 SUCCESS. The browser identity unit tests passed at generated-fixture scope. This **does not** mean real Sysmon/ETW browser matching has passed in a no-CDP capture, nor that the native runtime accepts the assumed profile command format. [Independent main-window witness](./P4_N12_NO_CDP_MAIN_WINDOW_IDENTITY_2026-11-21.md) is also source-only.

## Exact remaining integration checkpoint

Before any native run, in a source-reviewed one-use design, provision a fresh held-open `app.log` identity before process spawn, wait for the existing guarded close-listener acknowledgement, verify unique native main-window identity, and after normal close bind the browser with real `EtwLifetimes` plus the app's original process-handle witness. Remove port-9331 readiness/exit assumptions only with an equivalent independently checked lifecycle. Do not accept unobserved browser-command profile tokens or relax the strict event-loss checks when the real WebView2 runtime uses a different command-line structure. Ambiguity is a stop condition requiring evidence, not a reason to guess.

No native capture, restricted token, ACL change, firewall change, installer, download, owner-machine action or CI workflow dispatch is authorised by this record. The historical N12 results remain filesystem FAIL, network FAIL, coverage BLOCKED. P4 14/20 (70%), file-mutation 3/4 (75%), N12 0/2 (0%).
