# P2 controlled full-stack reporting acceptance: mounted React + real isolated FastAPI/SQLite

**26 October 2026 — source committed. Owner Windows test PENDING.**

## Accepted predecessor, limited to synthetic mocked-browser integration
Owner screenshot from `Run_PilotODIN_P2_React_Integration.bat` after its readiness-poll repair shows `frontend-typescript-vite: PASS`, `p2-mounted-react-dom: PASS`, `P2 mounted React integration gate: PASS` and success. The newly printed local ZIP `pilotodin-p2-mounted-react-ll89w_k5.zip` was not uploaded or inspected, so its individual raw test/DOM logs, times and status JSON are not independently verified. Earlier initial uploaded ZIP was inspected: browser **4/5 PASS**, failed fifth due a corrected test-harness mount timing error. **Owner-observed corrected focused mocked-API React gate accepted.** This does not test the real FastAPI server.

## What this NEXT test-only increment adds
A genuine but disposable local API integration, NOT production feature code:
- `tools/Verify_P2_Real_API_Integration_Local.py` creates a fresh temporary `PILOTODIN_HOME`, imports and calls the **real FastAPI app via TestClient** to create exactly two tiny synthetic CSV projects, captures an explicit read-only Quality audit in project A, then saves its first report revision. Records SHA-256 and filesystem paths under the temporary dataset directory only.
- It builds the frontend with existing Node/npm; starts an isolated FastAPI/Uvicorn process on an **ephemeral 127.0.0.1 port**, with `--lifespan off` to avoid automatic cloud-provider checks. No desktop session or model worker starts. It starts an isolated loopback Vite server on the first free development CORS-compatible port 5174–5179 and runs installed Chrome/Edge in headless mode with its **own fresh temporary profile**.
- `frontend/p2_full_stack_test.html` and `frontend/src/p2ReportFullStackHarness.tsx` mount the **real ReportWorkspace**, not a stub. The test-only page redirects its expected `127.0.0.1:8000/api` requests to the isolated ephemeral local FastAPI port, failing closed on any other fetched destination. It does NOT connect to or stop the user's existing local 8000 backend.
- Three actual React+HTTP+SQLite scenarios: (1) restore a persisted revision and verified Quality evidence; (2) edit and explicitly save revision 2, check revision 1 remains frozen, compare GET/revision and actual HTML/PDF exports including PDF signature and versioned filename; (3) switch to project B, verify the A library/evidence is excluded, capture project B's own audit and confirm project A's revision is unchanged.
- After Chrome exits, stop the test-owned Vite and FastAPI child processes. Check both source CSV SHA-256 values against their pre-test values. All artifacts/logs remain inside a disposable temporary folder. Every phase must individually report PASS; compilation and fixture presence alone are not sufficient.
- One launcher `Run_PilotODIN_P2_Real_API_Integration.bat`, one `pilotodin-p2-full-stack-*.zip` result with per-phase result JSON and logs. No new npm/Python package installation and no replays of unchanged P0/P1/P3/P4/P5 or earlier P2 launchers.

## Acceptance boundary and safety
This test operates on **created synthetic projects** and genuine app endpoints in isolated SQLite, rather than the user's existing projects. It still does **not** verify the Rust/Tauri native Save As, disconnected bundled Qwen, real 8 GB coexistence, power-loss recovery, actual real-project import or completed P8 installer and E-01–E-24 release checks. Network is limited to test-owned loopback listeners; the test browser profile is disposable. Fixture creation uses TestClient but the mounted React exercises a separately running Uvicorn FastAPI instance, not mocked HTTP results.

**Evidence truth:** All new test source was committed and re-fetched. **No owner Windows test for this new full-stack gate has been observed; it is PENDING.** If an environment/setup issue occurs, inspect the diagnostic ZIP and distinguish test harness from production logic rather than weakening product safety rules.

## Exact ONE next owner action
Pull `feature/live-dev-workspace-20261023` in GitHub Desktop without discarding uncommitted local changes. Run `Run_PilotODIN_P2_Real_API_Integration.bat` once. If red, upload `pilotodin-p2-full-stack-*.zip`; if green, share PASS result. Do not launch existing full apps, Qwen, installers or hosted Actions for this check.
