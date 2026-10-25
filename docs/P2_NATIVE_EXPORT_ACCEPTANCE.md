# P2 native export command acceptance (synthetic, DEV ONLY)

**26 October 2026. Source COMMITTED on the active feature branch, Windows owner verification PENDING.**

## Accepted predecessor and evidence limits
The owner said **"all passed next"** for the updated `Run_PilotODIN_P2_Real_API_Integration.bat` gate, which requires four phases: TS/Vite, 3/3 real mounted React/FastAPI report and HTML scenarios, binary HTTP validation of both PDF revisions and original synthetic CSV checksums. No output screenshot or green ZIP was supplied, so this is **owner-reported scoped developer PASS**, not independently inspected four-phase logs. Earlier initial and second real full-stack ZIPs documented the original Chromium PDF attachment fetch failure; preserving that distinction remains important. Prior A4 actual Tauri dev window Save As/Cancel passed its own historical manual smoke, but not the newest report-specific split acceptance.

## Why the next test is necessary
A genuine Windows Tauri `save_report_as` API call and OS file dialog are separate from HTTP PDF byte delivery. We must not infer real Save As behavior from headless Chromium or plain Python HTTP. The production Tauri `save_report_as` already checks report type/size/filename before showing an OS dialog and verifies the written file hash after completion. This change tests that boundary with synthetic bytes and owner-interactive native dialogs; it changes **no production code**.

## Files and test scope
- `frontend/public/p2-native-fixtures/report.pdf` is a tiny valid one-page PDF with only synthetic text, validated for readability at source creation. `report.html` is a tiny static HTML with no user data and no script.
- `frontend/p2_native_export_test.html` and `frontend/src/p2NativeExportTest.ts` are a clearly labeled test-only view importing the existing `@tauri-apps/api/core` and calling the **real** `save_report_as` Rust command, with five owner-clicked actions:
  1. Save synthetic PDF to the temporary folder and retain `PilotODIN_P2_Synthetic.pdf`.
  2. Save synthetic HTML to the same temporary folder and retain `PilotODIN_P2_Synthetic.html`.
  3. Open PDF Save As for `PilotODIN_P2_Cancel.pdf` and click **Cancel**; status must be `cancelled`.
  4. Pass non-PDF bytes with declared format PDF; Rust must reject before opening any dialog.
  5. Pass valid PDF bytes with `.html` filename; Rust must reject extension mismatch before dialog.
- `frontend/src-tauri/tauri.native-p2-smoke.conf.json` is a separate **development-only** Tauri overlay using loopback 5175, separate test identifier and `bundle.active=false`. It does **not** alter the normal PilotODIN Tauri config or launch the engine or optional AI.
- `tools/Verify_P2_Native_Export_Local.ps1` runs on Windows from the existing repository, checks active feature branch, installed npm/Cargo and local fixture files. Runs **only** frontend TS/Vite build and the test-only Tauri dev window, setting `CARGO_NET_OFFLINE=true` to prohibit new dependency downloads. It creates a unique **Windows Temp/save-target** directory and prints its full path; only that folder is valid for these test saves. After the owner finishes the five test buttons, closes the Tauri window, and confirms the displayed status lines, it independently compares the two saved-file SHA-256 values to the committed fixtures, checks Cancel did not create the third file, and confirms the fixture originals are unchanged.
- `Run_PilotODIN_P2_Native_Export.bat` launches the interactive PowerShell test. The result is one `pilotodin-p2-native-*.zip` with JSON, frontend build log and Tauri dev log. Do NOT upload user data or files outside this temporary test suite.

## Safety and genuine acceptance boundary
The app runs an actual Tauri **development** window. It does not start the normal backend, open existing user projects, run machine learning, download/launch Qwen or build an installer. Native compilation may use local cached Rust toolchain artifacts only; if unavailable, report a real failure rather than downloading dependencies. Existing background user apps are untouched. If an unexpected native dialog or file appears, cancel, close the test window and report FAIL.

Acceptance requires TS/Vite PASS, native dev process exit PASS, owner-observed FIVE real native action results PASS, saved PDF/HTML byte hashes PASS, cancel target absent PASS and original synthetic fixture hashes unchanged PASS. The manual observation is explicitly not an automated UI test; the SHA verification is automated. No aspect of this gate proves report composer → real FastAPI → native Save As integration, interrupted native disk writes, browser PDF attachment downloads, WebView2 packaging, final installer E-01–E-24, or local-Qwen combined 8 GB memory.

**Exactly one owner action:** Pull `feature/live-dev-workspace-20261023` safely, then double-click `Run_PilotODIN_P2_Native_Export.bat` from the repo root. Use the unique temp destination path printed in PowerShell, click all five test buttons in the separate window, close it, answer the one yes/no prompt truthfully. Green send console screenshot; red upload printed `pilotodin-p2-native-*.zip`.
