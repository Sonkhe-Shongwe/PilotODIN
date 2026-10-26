# P2 DevQA native report-chain acceptance

**26 October 2026: test-only SOURCE COMMITTED, owner Windows acceptance PENDING.** Previous DevQA foundation v1 setup Windows 10/10 PASS/REVIEW remains accepted. Do not confuse that with this new P2 gate.

## What changed and why

Previous synthetic FastAPI -> real React ReportWorkspace -> Tauri native Save As had six owner-reported PASS phases, but final Windows file checks never verified the exact two revision-2 output filenames. First runner rejected `Downloads` because it was a relative path, and read-only recovery confirmed both expected native versioned filenames missing in Downloads. Alternative browser download names are not native output evidence. **Historical old gate remains FAIL**.

One test-only runner has now been migrated to the local DevQA framework; **production Rust `save_report_as`, ReportWorkspace, FastAPI, real project data and the old runner are untouched**.

### One Windows entrypoint

`Run_PilotODIN_P2_DevQA_Native_Chain.bat` calls `tools/Start_P2_DevQA_Native_Chain_Local.ps1`. It:
1. Reuses an EXISTING `.venv-live` Python; invokes `tools/qa_foundation.py init --phase P2-NATIVE-CHAIN --json` to get a unique Windows run root automatically. No setup-folder prompt or package download.
2. Parses the P2 PowerShell runner source using the actual Windows PowerShell AST parser, runs **12** focused `tests/test_qa_foundation.py` cases and **5** `tests/test_p2_devqa_contract.py` source-contract checks, and runs conservative read-only Python source preflight. If bootstrap fails after a run was created, writes a status-only bootstrap diagnostic ZIP.
3. Starts `tools/Verify_P2_DevQA_Native_Chain_Local.ps1`, which requires a fresh DevQA run manifest with product acceptance NOT_TESTED. Reuses real synthetic report revision 2, isolated SQLite/FastAPI on random local port, test-only repeatable ReportLab PDF metadata, unchanged real React `ReportWorkspace` and existing Rust Tauri Save As. Offline Cargo; no normal backend port 8000 used.
4. Shows the exact uniquely created `%LOCALAPPDATA%\PilotODIN\DevQA\runs\P2-NATIVE-CHAIN-...\exports` folder **inside the native test page and PowerShell**. Owner selects that folder using Windows Save As for BOTH `Export HTML` and `Export PDF`, retaining their proposed versioned filenames.
5. After owner genuinely confirms both native PASS notices and closes Tauri, the runner **automatically checks** the two expected versioned filenames in that exact directory and compares full SHA-256 against independently recorded **real FastAPI** export reference bytes. Checks original synthetic source CSV SHA. If either is missing or hash mismatched, prints a distinct failure; no silent renaming, file-moving, browser download substitution or false PASS.
6. If a file is missing from the default run exports, may optionally ask whether BOTH were deliberately saved elsewhere. An owner-provided alternative must be an **absolute drive or UNC path**, not `Downloads`, `C:folder` or `\folder`. Only those exact two filenames are checked there. This is explicit owner-presented path provenance, not automatic discovery. Reparse-point folders and files are rejected.
7. Writes one run status ZIP in DevQA `archive` with JSON, **synthetic** export-reference manifest and preflight, Python, API/TS/Tauri logs. It never includes saved PDFs/HTMLs, source CSV or real datasets. Logs may include test-local paths. Stops test-owned Uvicorn, restores process env, does not clean other DevQA runs.

## Predictive failure boundaries

| Failure | Expected truthful behavior |
|---|---|
| Python/manifest/PowerShell syntax preflight | BLOCK with diagnostic after DevQA allocation, no Tauri launch |
| Wrong branch or dependencies missing | FAIL before native launch, no installation |
| ReportLab metadata or real HTTP bytes drift | FAIL strict baseline; do not weaken hash |
| A report revision cannot load or Tauri cannot open | FAIL with isolated API/frontend/native logs |
| Owner presses Cancel or doesn't get both native PASS notices | FAIL; no automatic declaration of a saved file |
| Wrong folder, missing exact version-2 name or file modified | FAIL with exact missing or SHA mismatch, no guessed recovery |
| Relative path like Downloads or drive-relative path | Reject, request full path only if alternate needed |
| Both original native outputs match backend SHA and source unchanged | **Scoped synthetic developer acceptance PASS**, not installed-release acceptance |

Scope does not prove clean installed app, arbitrary real datasets, packaged sidecar and authentication, interrupted disk writes, local licensed Qwen with combined 8 GB peak, or P8/E-01–E-24. Other prior focused P0-P5 passes are not replayed.

## Current evidence and one next action

Source committed, re-fetched and checked for expected isolation, unchanged production Rust, strict checksum and reporting invariants. New **17 focused tests have not yet been run on the owner's Windows machine**, and no live Tauri dev gate has been executed with this launcher.

GitHub Desktop: pull `feature/live-dev-workspace-20261023` preserving any uncommitted work. Double-click **`Run_PilotODIN_P2_DevQA_Native_Chain.bat`** once. Use the displayed DevQA exports directory for both native Save As operations and keep their filenames. Close test window when both real UI statuses show PASS, truthfully confirm, let the automatic file verification finish. Green share final console; red upload printed `P2-NATIVE-CHAIN-*.zip` or `*-bootstrap-fail.zip` and screenshot as relevant. **No need to rerun the separate DevQA foundation BAT.**

## 26 October 2026: blocked native filename precondition discovered in actual Windows Save As dialog

Owner screenshot demonstrates that the actual Windows HTML Save As dialog proposes **`pilotodin_report.html`**, not the strict versioned name required by the isolated report revision and accepted manifest; the DevQA exports directory contains `pilotodin_report.html` and `pilotodin_report.pdf`. Do not rename these, mark full export PASS, or suggest they prove native file integrity. This establishes a cross-layer filename contract mismatch **before** final hash comparison.

Source-traced mechanism: FastAPI report endpoint returns `Content-Disposition: attachment; filename=\"pilotodin_report_<id>_rev2.html\"`; React `downloadReportFile` reads this header but falls back silently to `pilotodin_report.html` when inaccessible. Backend CORSMiddleware previously had no `expose_headers`, so WebView2 cross-origin JavaScript cannot read `Content-Disposition` despite a successful HTTP response. Rust Tauri Save As uses `.set_file_name(filename)`, so it faithfully shows React's fallback. The earlier Python TestClient seeder incorrectly checked only raw header existence, not whether a browser could access it.

Narrow correction: expose **only** `Content-Disposition` in FastAPI CORS; frontend report export now rejects missing or unexpected revision-specific filename **before opening Save As**, never falls back; the synthetic seeder sends the real Vite `Origin` and fails unless both CORS allowed origin and `Access-Control-Expose-Headers` include the filename. Focused P2 contract test covers all four layers. The actual new Windows acceptance is still **PENDING**. Other reports, user data, ML, installers, Qt/Qwen and previous QA results are untouched. This checks a previously omitted failure boundary; it does not warrant changing the expected filename or bypassing hash validation.

## 26 October 2026: native export scoped acceptance

Final owner Windows console shows HTML and PDF SHA-256 MATCH against live API reference for revision 2, both Save As UI actions PASS, synthetic source unchanged PASS, and P2 live API-to-native export gate PASS. Exact filenames pilotodin_report_8bcb81b8d195_rev2.html/pdf. Owner used confirmed alternate absolute exports folder from earlier DevQA run; this was checked against latest run reference hashes. Diagnostic ZIP not uploaded. Historical failures remain failures; full P2 release and installed P8 remain open.
