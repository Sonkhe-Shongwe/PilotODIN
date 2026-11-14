# A4 — one-pass native Windows Save As and consolidated QA

**Checkpoint status: source committed. Actual Windows Tauri compile and user Save As evidence PENDING.** The earlier green 106 frontend / 167 backend run was against older code and does not certify the native implementation or its new regressions.

## What changed

- Native Tauri Save As code in `frontend/src-tauri/src/lib.rs` (Rust) and `frontend/src/ReportWorkspace.tsx` (React) writes **only** the validated report bytes selected by a native OS dialog. HTML/PDF signature, filename/extension and 12 MiB size are checked; saved contents are verified by SHA-256 before success is reported. Cancel returns without writing.
- Normal Chrome development keeps the existing browser download.
- **Separate native smoke configuration** `frontend/src-tauri/tauri.native-a4-smoke.conf.json` disables bundling, external sidecar references and missing AI assets *for the development run only*. It does **not** modify `tauri.conf.json` or produce an installer, and gives the native test its own app identifier.
- Only `VITE_PILOTODIN_NATIVE_SMOKE=1` **and** `import.meta.env.DEV` can bypass `launch_backend` in the native test. This uses the **already running** loopback API `127.0.0.1:8000`; production desktop builds still launch the normal session-authenticated sidecar.
- A4 native UI is served by a new localhost Vite server on port **5174**, separate from the existing browser on **5173**. Backend CORS already permits localhost 5173–5179; the development runner verifies the backend health first.

## One Windows developer action

1. In GitHub Desktop, select `feature/live-dev-workspace-20261023` and **Pull** the current development checkpoint. Preserve any local changes.
2. Keep your already working **PilotODIN Live Dev** backend running on `127.0.0.1:8000` (the browser may remain open on 5173). The native smoke runner will start its own frontend on 5174.
3. Double-click **`Run_PilotODIN_A4_Native_Smoke.bat`**. It pauses after finishing and prints a single ZIP path.
4. If a prerequisite fails, **stop** and share the ZIP instead of installing packages blindly. It identifies missing Rust MSVC / npm / running backend. The official Tauri Windows prerequisites are the Rust **MSVC** toolchain (dialog plugin requires Rust >=1.90), Microsoft C++ Build Tools with the Desktop development workload/Windows SDK, and Microsoft Edge WebView2. First native Cargo run may need online dependency resolution.
5. If preflight passes, the script automatically runs the **entire current consolidated A2/A3/A4 frontend/build/backend suite** in isolated test data. It stops on a regression failure instead of launching the native window.
6. When tests pass, it runs Tauri's development build with the separate `tauri.native-a4-smoke.conf.json` overlay. This compiles Rust and opens a genuinely native Windows WebView. **It is not Chrome and is not an installed release.**
7. In the native window: open Deliver using an existing disposable/known report, export PDF to a selected folder using Save As, then export HTML, then cancel another Save As request. Check that files were actually created/readable and cancellation did not produce a file. Close the native window.
8. The terminal asks four short yes/no/skip outcome questions **after** the native window closes, so the result records what you observed without asserting success on your behalf. Upload the **one `pilotodin-a4-native-*.zip`** it prints. Review local paths in logs before sharing if needed.

## What the ZIP contains

- `result.json`: exact git commit/branch (if git available), prerequisites, consolidated gate status, Rust/native process status, and owner-entered Save As observations.
- `p0-a4-regression.log`: consolidated Node, TypeScript, Python compilation and backend Pytest gate output.
- `p0-a4-regression-diagnostics.zip`: the existing regression runner's own JSON/JUnit/phase logs, nested inside the outer ZIP **without project data**.
- `a4-native-run.log`: output from the Rust/Tauri debug compilation and native window process.

It never includes source datasets, test project SQLite databases, model GGUF files, saved report payloads, installed-app secrets or arbitrary files from the user's computer.

## Explicit non-goals

No installer/NSIS output, no staged Qwen/llama runtime, no hosted GitHub Actions, no background tasks, no automatic approvals, no production app-data writes by the launcher. The user may explicitly choose to save a report through the OS dialog. This native smoke does not verify the production sidecar startup or offline 8 GB combined AI workload.

## Acceptance decisions

- **Source / automated**: must pass consolidated suite on the tested commit.
- **Native compilation**: Tauri dev process launches without an unresolved Rust/toolchain/build/config error. A zero exit code alone is not proof that the window rendered or Save As worked.
- **Manual native export**: user separately confirms native window, PDF, HTML and cancellation. A Cancel is neither a failed export nor a saved file.
- **Full A4 macro**: remains open until saved revision reopen/reorder and final report print/pagination review are accepted, as well as this native Save As evidence.
- **Release/Build E**: installers, assets, offline inference, real 8 GB testing and E-01..E-24 are separate mandatory gates.

See `docs/MACRO_A4_DELIVER_ACCEPTANCE.md`, `docs/CONTINUE_HERE.md` and GitHub QA Issue #2.
