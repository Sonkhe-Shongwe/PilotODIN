# PilotODIN P4 | Product process-boundary applicability review

**21 November 2026** | Source-reviewed branch: `feature/live-dev-workspace-20261023` at `af67de3fba41529e819e3a595e49fa38c0ff55ec`.  
**Disposition:** **Reject app-wide restricted-token change as current P4 fix. Defer isolated generated-writer token fixture.** Focus on WebView2's observed ambient writes, file-event attribution and external egress. This is a source-only architecture decision, not N12 acceptance.

## What is actually running

| Runtime boundary | Source-specific finding | What is and is not protected |
| --- | --- | --- |
| Tauri host/window | `frontend/src-tauri/src/main.rs` calls `pilotodin_desktop::run()`. `frontend/src-tauri/src/lib.rs::run` uses `tauri::Builder`, shell and dialog plugins, and one configured main window from `frontend/src-tauri/tauri.conf.json`. | No source-defined restricted-token or AppContainer launch for the Tauri host. WebView2 is created/managed through the Tauri runtime, **not** launched in source by a custom constrained-token broker. |
| WebView2 browser subtree | Production `tauri.conf.json` does not specify `dataDirectory`, a custom `WebviewWindowBuilder::data_directory`, WebView2 environment overrides, or a WebView process token broker. In contrast, **QA-only** `qa/p4_research/n12_app_journey.py::app_environment` and `n12_app_lifetime.py::storage_app_environment` set `TEMP`, `TMP`, `WEBVIEW2_USER_DATA_FOLDER`, debugger port and optional netlog flags for the disposable diagnostic launch. | Per Tauri v2 docs, the **default** WebView data directory on Windows is the application local data directory; this is a data-location convention, **not** an OS-level confinement boundary. QA's explicit UDF/TEMP environment does not prove the production host inherits those variables or that WebView2 cannot write outside the UDF. WebView2 can create several runtime processes with different sandbox/integrity settings. |
| Python analytics | `lib.rs::launch_backend` calls `app.shell().sidecar("pilotodin-engine")`, sets `PILOTODIN_HOME` under `app_local_data_dir()/data`, localhost port/session secrets, `.current_dir(&data_dir)`, `.set_process_group(true)`, then `.spawn()`. `backend/desktop_runner.py` requires a session/home and binds Uvicorn to `127.0.0.1`. | Dedicated home/CWD and loopback binding are **real source-level hygiene**, but neither a shell sidecar nor a Windows process group/job object implies a restricted Windows access token. No product-specific token restriction or broker is present. QA tests sometimes start a separate development Uvicorn process, not the packaged Python sidecar. |
| Bundled inference | `lib.rs::launch_bundled_ai` calls shell sidecar `pilotodin-inference` with `--host 127.0.0.1`, model path, runtime DLL PATH, runtime DLL directory as CWD, process group, then spawn. | Cannot blindly deny model/resource reads or runtime DLL loading. Constraining this sidecar requires separate tested resource and temporary-file rules, not a blanket write denial. |
| Native report export | `lib.rs::save_report_as` opens the native file dialog and calls `report_file::publish_report` with the user-selected local path, with strict extension/size/content validation. | **Intentional** writes beyond the application's data directory exist by design. A blanket confinement rule on the Tauri host would obstruct Save As. Explicit user-approved export must remain a separate, narrow brokered write. |
| Network surface | `tauri.conf.json` CSP contains `connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:*`; backend/AI localhost flags are explicit. | CSP and localhost application services **do not prove** WebView2 runtime background connections are isolated. The prior full native audit observed four WebView2 non-loopback events. Network remains FAIL, with separate firewall enforcement approval required. |

**Source boundary:** These are code/configuration observations, not captured token SIDs, process integrity levels, effective access decisions or complete native process parentage. In particular, do not assert that all WebView2 subprocesses inherit the same identity, have full user rights or are all isolated merely because some child roles use LowIL/AppContainer.

## External platform constraints relevant to the decision

- [Tauri sidecars](https://v2.tauri.app/develop/sidecar/) document `sidecar().spawn()`. The checked-in Rust uses this API, not `CreateProcessAsUserW`.
- [Tauri v2 window configuration](https://v2.tauri.app/reference/config/) documents the default app-local-data WebView directory and `WebviewWindowBuilder::data_directory` override. **Explicitly setting the same default is not evidence it will eliminate ambient temporary files.**
- [Microsoft WebView2 process model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model) documents a browser process with associated process collection, potentially shared by WebViews using the same user data folder. Do not assume changing a single renderer token controls the full runtime.
- [Microsoft WebView2 security](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security) recommends a **standard non-elevated** hosting process, and isolating elevated work in a dedicated process. A general forced restricted token for the host is not that guidance.
- [Microsoft WebView2 security-tool guidance](https://learn.microsoft.com/en-us/deployedge/webview2-security-tools) warns that overly tight UDF ACLs can break sandboxed runtime access and cause blank windows or crashes. WebView2 subprocesses may have different integrity levels or AppContainer constraints.

## Options considered and resolution

| Option | Relevance to measured issue | Engineering risk | Decision |
| --- | --- | --- | --- |
| **A. Make the entire Tauri/WebView2 desktop run under one new restricted token** | Theoretically could constrain user writes, but does not pinpoint ambient temp cause, runtime egress or actual WebView child roles | High: OS dialogs, Save As, WebView startup, IPC, DLL/model reads and token/process propagation | **Reject as current P4 fix.** No product-side change authorized. |
| **B. Launch only the Python engine under a restricted token** | Potential extra containment for Python, **not** the observed WebView2 browser writes | Medium/high: requires replacing/wrapping Rust shell-plugin spawn; token/handle/STDIN ownership, bundled resources, port auth and shutdown integration must be preserved | **Defer as a separately designed backend hardening feature.** Does not earn the current WebView2/N12 checkpoint. |
| **C. Keep current host architecture and fix/measure the specific WebView2 writes and egress** | Directly addresses the actual native observations and current P4 blockers | Moderate: requires source-grounded WebView profile/temp configuration research, runtime-level diagnostics, strict independent FileIO and network measurement | **Selected next product direction.** No new native run without fresh one-use owner approval. |
| **D. Execute the two-root generated restricted-token writer control now** | Demonstrates a Windows capability on synthetic folders, not PilotODIN subprocess isolation | Can pass while P4 still fails, creating another test-only loop | **Defer.** The offline fixture contract and the read-only 10/10 API export check are retained as tools, but are not evidence of production containment. |

## Concrete next micro-step, before any live capture

**One source-only review of WebView2 configuration and lifecycle, not more synthetic token cases.**

1. Verify the exact *production* Tauri window/profile configuration and all runtime WebView override sources, including what differs under the approved diagnostic setup. Do not assume adding `dataDirectory` fixes a default that already resolves to app local data.
2. Trace which `TEMP`, `TMP`, UDF and `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` assignments reach the **host** versus which values are actually corroborated on the **browser** Process Start. Record missing evidence explicitly.
3. Inventory the two observed ambient-temp CreateFile events by **stage, WebView role, operation and destination family only** from the retained redacted results. Their exact raw filenames and provenance are not available from prior private runner artifacts; do not invent them.
4. Choose at most **one** justified product-level source modification or diagnostic improvement, with a falsifiable expected runtime result and a strictly bounded proof plan. If the available evidence cannot differentiate causes, label the question unresolved and stop. Do not relabel ambient writes as permissible or loosen N12 coverage.
5. Separately maintain the full N12 network FAIL (four WebView2 non-loopback events) and file-mutation coverage BLOCKED. A file-profile fix cannot be credited as network isolation.

**Stop rules:** No automatic `debug-only` A/B rerun; the current A/B comparator requires `procmon_loss_reviewed=true` that the native wrapper cannot establish. No full installers through P4-P7, no owner-device changes, restricted tokens, ACL changes, firewall enforcement or live WebView run without independently scoped explicit permission.

## Unchanged checkpoint ledger

- Official P4: **14/20 (70%)**.
- File mutation: **3/4 (75%)**.
- Desktop network isolation: **2/3 (67%)**.
- N12 acceptance: **0/2**; governing native filesystem FAIL, network FAIL and mutation coverage BLOCKED.
- Original app-data preservation: **0/2**, with the historical 74 differences and unknown writer unresolved.
- The [read-only token API preflight](./P4_N12_RESTRICTED_TOKEN_CAPABILITY_PREFLIGHT_2026-11-21.md) verified 10/10 exports in [routine CI #44850133377](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44850133377), **not** process confinement.
- No native test or product code executed or changed in this review; one-use native workflows remain disabled.
