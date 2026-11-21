# N12 source-level remediation | Backend working directory and WebView2 boundaries

**21 November 2026. Status: source change and routine synthetic/real-process verification complete; native retest not authorised.**

## Baseline and scope

The last owner-approved [hosted Windows N12 run 44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) completed two actual launches and a strict audit. It returned filesystem **FAIL**, network **FAIL**, mutation coverage **BLOCKED**. The ordinary reducer identified one backend `write` to a source-checkout file of unknown extension, and WebView2 ambient user-local/temp writes. The public report did not include the backend target filename or a verified relative-vs-absolute mechanism.

## Source changes

- [`75d0fc10`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/75d0fc10d74124260c66d3974d633677001e295f): the N12 synthetic/hosted backend now runs with its disposable `PILOTODIN_HOME` as current working directory. `PYTHONPATH` explicitly supplies the source repo to import `qa.p4_research.n12_backend_wakeup:app`, without inheriting the source root as its write location.
- [`54857ee5`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/54857ee5b20a89b6735f93a859a316ccc04bb379): the real Tauri desktop `launch_backend` command changes CWD to the existing, created `app_local_data_dir()/data` before spawning the analytics sidecar. The separate AI worker is unchanged. Tauri Shell v2's Rust `Command::current_dir` builder supports this setting.
- [`1960b7fe`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1960b7fe7c28d65565d6a397b15fb2af005b2e2d): the real `backend.desktop_runner` process smoke test starts with CWD at its generated home and an explicit source-only module import path, verifies authenticated loopback endpoints and data storage. A source-contract test also asserts that the Rust analytics sidecar CWD is set after directory creation but before process spawn.

The filesystem allowlist, immutable original checks, path-gap reduction, WebView2 launch environment and network policy remain unchanged. This prevents a relative write from targeting the checkout **by default**. It does not prove the previously measured write was relative or that all absolute writes are safe.

## Verification

[Exact-source routine P4 CI](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44841168894) passed all four jobs at `1960b7fe7c28d65565d6a397b15fb2af005b2e2d`. The source job passed 773 Python tests, six skips, 242 subtests, 103 frontend checks and Vite. The real-HTTP browser passed all 13 cases. The Windows synthetic FileIO fixture completed its existing controlled tests; strict app mutation coverage remains unresolved. The Windows R03 job separately passed four packaged/real-process tests, including the new data-home CWD smoke. **No new Tauri Windows compilation or native N12 acceptance capture was run.**

## Remaining WebView2 work

The capture already set `WEBVIEW2_USER_DATA_FOLDER` to a generated profile, and set `TEMP`/`TMP`/`TMPDIR` for the spawned app. Despite that, the last native audit recorded eight out-of-scope WebView creates, four overwrites, four writes and ambient user-local/temp targets, as well as four non-loopback WebView-network connections.

Do not expand `permitted_writes` to make these pass. WebView2 supports an environment override for the user data folder and additional browser arguments, but these settings are not a filesystem or network sandbox. Some browser switches, such as `--user-data-dir`, are ignored when passed as additional WebView2 arguments, and disabling background networking is not a demonstrated egress enforcement boundary. The raw target paths remain runner-local; the public evidence classifies them as `other-user-local` and `user-temp`, which is insufficient to establish their creation mechanism.

**Next bounded engineering choice:** inspect and reproduce the ambient user-local targets in disposable source-only Windows controls, retaining safe path categories and full event attribution. Design a real application isolation control or reviewed OS-enforced restriction, validate with synthetic fault cases, and then seek a *new separately approved one-use source-pinned native capture*. Any live firewall preflight/enforcement remains separately approval-gated. Until that evidence exists, preserve filesystem FAIL, network FAIL, coverage BLOCKED.

**Official workstreams unchanged:** product audit 7/7; file-mutation 3/4 (75%); desktop network isolation 2/3 (67%); N12 0/2; original app-data preservation 0/2; P4 **14/20 (70%)**.

## Source-only WebView2 containment decision (21 November 2026)

- **Observed baseline:** the N12 `44838416004` audit is **filesystem FAIL / network FAIL / coverage BLOCKED**; its one-use approval is exhausted. Source CWD changes subsequent to the tested application do not retroactively change that verdict.
- **Verified source state:** `qa/p4_research/n12_app_journey.py::app_environment` already assigns a disposable `WEBVIEW2_USER_DATA_FOLDER` and `TEMP`/`TMP`/`TMPDIR`, yet actual WebView writes reached ambient user-local/temp. The public redaction gives path *classes*, not target filenames, and cannot establish an exact creation mechanism. Existing source-level probes in `n12_webview_storage_probe.py` and tests can classify evidence, but a synthetic receipt cannot certify actual native egress or writes.
- **Platform constraint:** [Microsoft's WebView2 browser flags guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags) advises against using browser feature flags in production because support and behaviour can change. [Microsoft's WebView2 policy guidance](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-webview-policies) describes a narrow experimentation/configuration-service control, not a complete egress sandbox. Do **not** substitute `--disable-background-networking`, an inferred WebView command-line switch, CSS/CSP or a broad registry policy for an OS-enforced network boundary; do not silently alter owner machine policy. Do **not** expand `permitted_writes` to pass the audit.
- **Existing enforcement preparation:** `qa/p4_research/n12_egress.py` contains a consent-gated Windows Firewall fixture preflight. Its *unperformed* success condition is confirmed external TCP connectivity before and after the temporary program-scoped rule, access denied during it, loopback connectivity throughout, and reliable rule cleanup. A pass would establish the fixture scope **only**. It does not justify a native build or award N12 app acceptance. A live firewall rule requires separate, one-use, source-pinned owner authority specifying the disposable Windows Server 2022 runner, program, rule, capture evidence and cleanup.
- **Next file decision:** first identify the writer, operation, safe destination class and process lifecycle for the ambient creates and outstanding FileIO paths on a disposable system; do not call the CWD change a proven fix for absolute or WebView-origin writes. If a source-level containment change is justified, exercise focused generated failure controls before proposing a separately approved one-use native N12 rerun.

**Verification for this record:** source and historical evidence review only, not an executed Windows test. Exact code CI remains [44841168894](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44841168894) at `1960b7fe7c28d65565d6a397b15fb2af005b2e2d` and does not test WebView containment. **No score moved:** file-mutation 3/4 (75%), desktop network isolation 2/3 (67%), firewall preflight 2/3 (67%), N12 0/2, P4 **14/20 (70%)**.
