# PilotODIN 1.0 Build A: Desktop Foundation

This is an **engineering preview of a native Tauri 2 + React application using a bundled Python analytics sidecar**, built on the existing Studio v0.8 source. It **does not yet include a precompiled Windows installer**.

## What changes

- Windows runtime: Tauri desktop host manages the bundled Python analytics engine. No Python/Node installation is required **for users of the built installer**.
- The desktop frontend receives a private port and per-launch token from a restricted Rust command; every API request (including uploads) carries that token. The Python engine binds only to `127.0.0.1`.
- Rust starts and stops the engine with the native application's lifecycle; unexpected engine exit allows a restart.
- Project storage now resides in the user's app-local-data directory, separate from installed software.
- Existing Studio React workspaces and Python analytical functionality are preserved.
- Development browser mode is retained for testing and is separate from desktop authentication.

## Building the FIRST Windows installer

1. Back up the existing Studio v0.8 inner `PilotODIN` directory and its `data` folder. Do not overwrite it with this preview.
2. Install builder tools **only on the development computer**: Python 3.11+, Node LTS, [Rust MSVC](https://v2.tauri.app/start/prerequisites/), and Microsoft Visual Studio Build Tools **Desktop development with C++**. WebView2 comes with Windows 11.
3. Open PowerShell inside this new project and execute:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\desktop\Build_Windows_Installer.ps1
   ```

4. When successful, the NSIS `.exe` installer will be in `frontend\src-tauri\target\release\bundle\nsis\`. Inspect its size, install it on Windows, verify that it starts and run the acceptance tests below.

**Build prerequisites** are not needed by future end users of the installer. The installer has **not** yet been compiled or tested on Windows in this environment. `PyInstaller` one-file packaging may introduce a few seconds of cold-start overhead; this is for the initial desktop feasibility milestone.

## Existing projects and AI keys

The source ZIP deliberately excludes your `data` folder, project DB, model artifacts and API keys. The desktop application uses Windows app-local-data storage, rather than the old source-folder `data` path.

If you want the old projects in the native app, **before the first launch of the native app** and with old Studio closed, run:

```powershell
py .\desktop\Migrate_Existing_Workspace.py "C:\path\to\your\old\PilotODIN"
```

The script checks the source data, copies into a temporary directory, rewrites dataset paths, then places the copy in desktop storage. It refuses to overwrite an existing desktop workspace. The original remains untouched. DPAPI keys work only in the Windows account that encrypted them.

## Windows acceptance tests

1. Verify the installer launches from Start Menu **without a Python / Node development environment** installed on the test Windows profile.
2. Verify Home, file import, Data Quality, charts, ML, evaluation and prediction end-to-end.
3. Restart app and verify saved projects and AI consent/key status persist.
4. Verify port conflict immunity and that external processes without the session token cannot read or modify API data.
5. Exit PilotODIN and ensure its bundled engine process also exits; force-kill it, then use Try Again.
6. Validate project migration, audit history, selected models and DPAPI secrets on copied data.
7. Measure actual installer size, startup seconds, RAM usage and performance at 100% and 125% display scaling.

## Known limits at this milestone

- Not yet a signed product release, no auto-updater implemented.
- Not a proof of performance on an 8 GB Windows laptop.
- Rust compilation, Tauri installer integration, production CSP and frontend dependency build **require real Windows toolchain verification**.
- Actual localhost security must be independently reviewed before public distribution; no local server authentication mechanism protects against same-user malware or a fully compromised Windows account.
- Future iterations will introduce automated Windows CI, crash reporting, packaging benchmarks, native app-upgrade tests, and more autonomous ODIN investigations.
