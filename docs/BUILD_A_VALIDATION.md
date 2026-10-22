# PilotODIN 1.0 Build A: Verification record

**Version:** 1.0.0-alpha.1 desktop-foundation source preview.
**Source baseline:** Studio v0.7 full archive + all v0.8 consolidated update files.

## Implemented

- Windows Tauri v2 desktop scaffold with the original Studio interface.
- Rust lifecycle manager launches only the bundled `pilotodin-engine` sidecar, uses a randomly selected loopback port and random 64-hex-character per-launch secret, kills the engine process group on normal app exit, and permits restart after unexpected termination.
- Local desktop API protects all substantive requests with `X-PilotODIN-Session` and rejects unauthorized origins. Dedicated local-only dev workflow remains available when the secret is absent.
- React API passes authentication on GET, POST, PUT and file upload. Desktop initialisation waits for authenticated `/api/health`, with a visible retry UI.
- Persistent datasets, sqlite database, models and Windows DPAPI-protected AI keys stored in the app-local-data folder, separate from app binaries.
- Optional explicit one-way migration script copies existing dev-mode data without modifying the originals. Migration refuses an occupied destination and checks source files.
- Branded application icon reused from the existing PilotODIN identity.
- PyInstaller/Tauri/NSIS Windows PowerShell build script and optional GitHub Actions Windows build workflow. Source repository excludes runtime binaries and ML assets.

## Tests run in this environment

- Full Python suite **156 passing**: 147 Studio v0.8 tests plus 9 new Build A desktop tests.
- Python source compilation: passed.
- TS/TSX syntax/transpilation check using globally installed TypeScript: **13 source files, 0 diagnostics**.
- Live Python engine smoke test: started on ephemeral localhost port; authenticated health was HTTP 200; unauthenticated call was HTTP 401; process terminated successfully.
- Simulated migration confirmed SQLite project paths were rewritten, model artifacts copied and original database unchanged.

## NOT YET VERIFIED

- npm dependency installation and real Vite/TypeScript build: npm registry network DNS lookup failed in this container (`EAI_AGAIN`).
- Rust build: Rust compiler/Cargo unavailable in this container.
- PyInstaller Windows executable: Windows build toolchain unavailable here.
- Actual Tauri/NSIS installer or installed application: no Windows build executed yet.
- Startup timings, Windows filesystem permissions, Tauri CSP/WebView2 network access, Windows signing, Windows Defender behavior, migration from a real account, and 8 GB hardware performance: require Windows acceptance testing.

This release is **source and packaging infrastructure**, not a claim that a compiled Windows installer is already delivered. The included GitHub Actions workflow can be used to produce and test Windows preview installers without placing downloaded toolchains on the user's 8 GB laptop.
