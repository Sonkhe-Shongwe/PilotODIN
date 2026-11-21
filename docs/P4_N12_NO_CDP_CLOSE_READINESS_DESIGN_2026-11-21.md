# PilotODIN P4 | No-CDP native close-readiness handoff

**21 November 2026** | **Status:** Source-only acknowledgement implemented; native no-CDP capture **not** approved, run or proven.

## Source-backed reason

- Authorized native [debug-only #44852642468](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44852642468) completed a working native app lifecycle but returned filesystem-observation **BLOCKED**. It observed **two** browser ambient user-temp `.tmp` file creates, both in **ready-probe**, with `--log-net-log` absent and `--remote-debugging-port` present. The debugger remains a shared variable in both actual focused captures. No source supports claiming that it caused the writes.
- Existing `frontend/e2e/p4-n12-app-lifetime-ready.mjs` uses Playwright `connectOverCDP`, finds the exact dev page and QA peer, closes the peer, polls `data-native-close-ready`, and optionally reads the browser PID through `SystemInfo.getProcessInfo`. This cannot test the non-CDP runtime as-is.
- Existing `frontend/src/UnifiedShell.tsx` registers the Rust-emitted native close ticket listener in a `useEffect` and calls `setNativeCloseRegistered(true)` only after `listen(...).then(stop => ...)` supplies the unsubscribe function. Rust `on_window_event(CloseRequested)` always calls `api.prevent_close()` first; only the one-use `resolve_native_close_request` ticket can authorize destruction.
- `qa/p4_research/n12_app_journey.py::request_graceful_close` already uses the verified Windows executable path + exact window title, retains the process handle, delivers a normal `CloseMainWindow` request, and requires exit code zero. Therefore **the close operation itself does not require CDP**, only the current frontend listener-ready observation does.

## Chosen one-microstep implementation

[Source `f6f49313`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/f6f49313f1fc16ddf45f4026a38b0f4d10e2fca7) adds a **fixed-string, QA-only native log acknowledgement**, not a new close action or network service:

1. React invokes `acknowledge_n12_no_cdp_close_listener_ready` **only after** the existing `listen` registration succeeds, only if `isNativeA4SmokeMode()` is true, and only if the separate Vite flag `VITE_PILOTODIN_N12_NO_CDP=1` is explicitly present. The flag is absent in all currently reviewed workflows. If the acknowledgement fails, the UI shows a warning; the close veto stays in force.
2. Rust command accepts **no project fields or user parameters**. It requires the `main` WebView window, a debug build, the precise `http://127.0.0.1:5173/` dev URL (fragment allowed but **no query or alternative origin**), and the distinct runtime environment value `PILOTODIN_N12_NO_CDP_STORAGE_CONSENT=I_APPROVE_ONE_N12_NO_CDP_STORAGE`. This separate consent is **not set** by any workflow today.
3. Only on satisfying all checks, Rust writes exactly `N12 QA native close listener registered` to the app's stderr stream. No path, token, PID, raw URL, filename, report data or personal information is output. The command never closes windows, changes a native close ticket, opens a file, starts a process, changes permissions or affects WebView2 flags.
4. Source-based JS contract tests assert acknowledgement comes after listener registration, both source-level guards are present, and the original Rust close veto and one-use ticket resolution remain in place. Pure Rust unit tests cover refusal on release build, wrong URL, missing/mismatched consent, peer-page URL and wrong origin.

**Limitation:** Static JS tests and pure Rust predicates do **not** verify that the Rust Tauri command compiles and actually emits the log marker from a live native process. Exact-source routine CI can verify TypeScript/Vite and Node source contracts; **do not claim native no-CDP runtime success** until a separate, approved host test demonstrates it.

## Subsequent bounded implementation, NOT in this change

Before any future native request, build and test a **read-only Python receipt reader** for an exact, fixed app-log marker with a bounded deadline, unique source/binary identity, app-process liveness and a verified single main window. The reader must fail on missing, duplicate, out-of-order or stale markers; never parse private log lines into public output. The runner can already use `request_graceful_close`, the same native ticket veto and independent process/profile exit. **Do not** bypass the normal close listener and do **not** replace graceful close with `kill` as an acceptance action.

For future no-CDP storage attribution, the existing focused reducer uses `cdp_browser_pid` for browser identity. It must be redesigned to independently bind a **unique** WebView2 browser process to the exact app/profile from OS process-lifetime evidence and then fail closed on ambiguity. Simply omitting the PID, relaxing browser identity rules or treating unclassified writes as safe would invalidate the capture. Absence of the CDP port also requires adapting `port 9331` readiness/exit checks. The current one-use native workflow `.github/workflows/p4-n12-webview-storage.yml` is still `if: false` and still invokes the debugger-based diagnostic. **Do not activate it for this new mode**.

## Expected discriminating observation

A genuinely separate, source-pinned, no-CDP readiness and graceful-close capture could answer whether WebView2 browser ambient `CreateFile` operations occur **without either debug switch** while app readiness and OS-close protections remain verified. Even that would not prove OS-level write isolation: ProcMon exit 1 and absent independent coverage review persist, N12 full-journey network egress remains a distinct open failure, and protected endpoint snapshots do not exclude transient mutation.

## Status and strict stop rules

- P4 **14/20 (70%)**, file mutation **3/4 (75%)**, desktop network **2/3 (67%)**, N12 **0/2**, owner-data preservation **0/2**. No acceptance point earned.
- No installer until P8, no actual owner-device or original-data operations, no permission/firewall changes, no new native run, no auto-reruns.
- The previous no-netlog native authorization was **consumed**. A future one-use, source-pinned no-CDP capture requires fresh explicit approval after code, source contract, process identity and close-safety review.
