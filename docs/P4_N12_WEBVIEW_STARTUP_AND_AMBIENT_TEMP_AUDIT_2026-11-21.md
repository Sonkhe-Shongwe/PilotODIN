# PilotODIN P4 | Production-versus-QA WebView2 startup and ambient-temp evidence audit

**21 November 2026** | Source review and one source-only diagnostic correction. **Not** a native acceptance capture or production storage remediation.

## Directly established source differences

| Dimension | Production Tauri | Approved focused QA WebView storage launch |
| --- | --- | --- |
| Application identifier | `com.pilotodin.studio` in `frontend/src-tauri/tauri.conf.json` | `com.pilotodin.p4isolatednativedev` in the isolated-native-dev overlay |
| User data folder | No explicit dataDirectory option in checked-in production window config; Tauri v2 normally uses application local data directory on Windows | `n12_app_journey.py::app_environment` sets `WEBVIEW2_USER_DATA_FOLDER` to disposable `root/webview` |
| TEMP/TMP | No explicit production startup redirection in `frontend/src-tauri/src/lib.rs::run` | QA `temporary_environment` sets `TEMP`, `TMP`, `TMPDIR` to an app-profile temp directory; focused `storage_app_environment` further changes `TMP` to a separate disposable startup witness |
| WebView2 browser flags | No explicitly configured debugger or netlog flags in production window config or Tauri host `run` function | QA `debug-netlog` explicitly requests debugger port 9331 and netlog; `debug-only` retains only the debugger flag |
| Backend | Tauri shell sidecar with app-local `PILOTODIN_HOME` and CWD; no restricted-token launcher | QA separately starts Python `uvicorn` with disposable data home and browser test server |

**Important boundary:** Checked-in production configuration does not enumerate the full environment, Windows policy/registry settings or runtime's actual command line. Lack of a checked-in flag does **not** prove the OS cannot supply an override. QA assignments to the host process do **not** prove that the WebView2 browser process inherited or used the same values. Tauri's default application-local user-data folder is a convention, not filesystem containment.

Sources reviewed: `frontend/src-tauri/tauri.conf.json`, `frontend/src-tauri/src/lib.rs`, `frontend/src-tauri/tauri.p4-isolated-native-dev.conf.json`, `qa/p4_research/n12_app_journey.py`, `qa/p4_research/n12_app_lifetime.py` and `qa/p4_research/n12_webview_storage_probe.py` at source `301e240405a2c1e17a753efcdc8c6b4d91e2e711`.

Platform references: [Tauri v2 configuration](https://v2.tauri.app/reference/config/); [Microsoft WebView2 browser flags](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags); [WebView2 environment override rules](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/webview2-idl). These references explain possible runtime configuration, **not** the private files created in our captured run.

## What the one-use native report actually observed

[Run #44847306630](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44847306630), exact code source `f77a49d6`, successfully built and launched the Windows app and closed the browser profile. Its redacted ProcMon reducer reported:

- **Two** `CreateFile` operations under the ambient **user-temp** family; component independently classified **browser**, file type **temporary** (`.tmp`).
- **One** during `startup`, **one** during `ready-probe`. Both were attributed to the uniquely identified browser process and the command line corroborated the **remote-debugging and netlog** flags.
- Process Start did **not** yield browser `TEMP`, `TMP` or `WEBVIEW2_USER_DATA_FOLDER` values. Their absence from the parsed record is **not evidence of a different inherited value**.
- Protected before/after snapshot hashes **matched**, but the recorder exited with code 1; loss/coverage review and 10,231 named-pipe operation records remained unresolved. Governing N12 remains filesystem **FAIL**, network **FAIL**, mutation coverage **BLOCKED**.

The published redacted report **does not retain private filenames or per-target identities**, and no raw reusable ProcMon CSV artifact was uploaded. It cannot establish whether the two creates concerned the same normalized pathname, different files, a netlog side effect or standard browser operation. It cannot be retroactively analyzed for that distinction. The old `debug-netlog`/ `debug-only` comparator also has an unreachable complete-capture precondition; no second arm is authorized.

## One testable diagnostic source change, not a speculative production fix

[Code commit `00a68383`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/00a68383d5337c6172f57c488f41247bd3eb2485) adds a **memory-only** set of normalized ambient-temp pathnames observed for the verified WebView2 browser `create` operations. The public report includes only:

- `observed_create_events`: how many browser ambient-temp creates the recorder positively observed.
- `distinct_normalized_path_count`: how many distinct **normalized path strings** occurred.
- `normalized_paths_seen_in_multiple_stages`: how many strings appeared in more than one stage.
- Explicit `filesystem_object_identity_verified: false` and `capture_completeness_verified: false`.

No filename, private path, pathname hash, process ID or per-target record is published. The source-only regressions exercise same-path repeated create, separate paths, case normalization, renderer-versus-browser distinction and no raw-name disclosure. Even matched path strings would **not** prove that the underlying filesystem object was the same. No change to file permissions, allowed destinations, collector failure rules, existing verdicts or production Tauri configuration.

**Falsifiable expected result of a future independently approved capture:** The two previously observed event categories, if they recur, can now be classified as repeated or distinct *normalized path strings*. This can improve mechanism triage but cannot prove the cause, prevent writes or make the capture complete. Do not authorize a new native run solely to chase these counts without a product-level hypothesis.

## Routine CI calibration failure was a separate harness defect

[First routine run #44851382639](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44851382639) had Linux Python/frontend, real-HTTP browser and R03 Windows jobs pass, plus the new focused Windows storage tests. Its **Windows FileIO job failed** at `N12 calibration failed at udp-listener`, in the generated loopback fixture. The fixture took a TCP ephemeral port and assumed its corresponding UDP port could bind. The log records the stage but not the private Windows socket error code; no specific OS cause can be proven from that message.

[Bounded fixture correction `473c06d8`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/473c06d8bc5e98abf1224997d1f6f8cdab7feaaa) retries **only a failed UDP bind** with a new TCP/UDP socket pair, at most three attempts. Every unsuccessful pair is closed. A TCP-bind error, failed marker, lost event, missing attribution or third failed UDP bind stays **BLOCKED**. Four synthetic negative/positive cases were added to routine Linux/Windows CI. This correction never touches production app/network behavior.

**Exact-source follow-up routine CI:** [#44851735583](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44851735583) at `473c06d8bc5e98abf1224997d1f6f8cdab7feaaa`: completed, 4/4 jobs SUCCESS. The updated Windows generated calibration crossed its prior UDP bind stage; no native PilotODIN app build was run. A single completed host run does not guarantee the transient issue can never recur.

## Later owner-authorized debug-only native result (21 November)

[One-use `debug-only` native run #44852642468](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852642468) was explicitly authorized after this audit, scoped to one unpackaged QA build and startup/close capture, independently source pinned to `0e135955`. It completed the build, app lifecycle and reduction but returned **BLOCKED** on ProcMon shutdown and incomplete coverage. **The browser created two distinct normalized `.tmp` path strings under user-temp, both during readiness, with `--log-net-log` absent and the CDP debugging flag present.** This rejects *netlog as a necessary condition for all observed ambient temp creation* while leaving the causality of specific files and production non-debug behavior unresolved. ProcMon returned code 1; browser `TEMP`, `TMP`, UDF values were unverified; 10,121 named-pipe operations unresolved; snapshots MATCHED endpoints. See [full redacted result](../qa/p4_research/N12_WEBVIEW_DEBUG_ONLY_RESULT_44852642468.md). The new source-pinned approval was consumed and the workflow disarmed again. No new N12 credit.

## Unchanged P4 acceptance

Official P4 **14/20 (70%)**; file-mutation **3/4 (75%)**; desktop network isolation **2/3 (67%)**; N12 **0/2**; original data preservation **0/2**. The one-use WebView native approval remains consumed and the workflow remains `if: false`. Installer freeze through P7, owner-device prohibition and separate firewall approval remain unchanged.

**Next scope:** Investigate a *specific observed WebView2 temporary-file mechanism* only when actual native evidence justifies a product-level change. Avoid changing production `TEMP`, WebView2 data directories or allowed write/network paths based on assumptions from an incomplete QA diagnostic.
