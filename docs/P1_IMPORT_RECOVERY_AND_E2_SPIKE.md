# PilotODIN P1 entry and early E2 bounded feasibility

**Scope:** The owner confirmed the one-session P0 A2/A3 interface flow "everything works fine" after an owner-uploaded **117/117 frontend + 174/174 backend** consolidated PASS. P0 is accepted for the observed **development** analysis journeys; the working-tree had uncommitted files and this is not clean-install/offline/release certification. Existing native DEV ONLY PDF Save As/HTML/Cancel is separately accepted.

## P1-1 import recovery — implemented in source, awaiting one local regression run

**Problem:** Project import saves an immutable original dataset and a project record, then calls Quality registration. If the registration fails before Quality tables exist, the old cleanup directly queried those absent tables. The resulting second SQLite error masked the original failure and could strand project metadata and/or staged source data.

**Change:** backend/main.py now has _rollback_failed_project_import. Metadata cleanup occurs within one SQLite connection and checks which Quality tables actually exist before deleting the new project's Quality state and then its project record. Staged source bytes are deleted **only after the database cleanup has succeeded**. If the database rollback itself fails, the staged bytes remain recoverable and the API returns a clear cleanup-incomplete error; the server writes diagnostic logs. Successful imports, valid data profiles, source checksum versioning, approved Quality transformations and existing user projects are not altered.

**Regression tests:** tests/test_p1_import_recovery.py uses an independent Pytest tmp_path database and generated CSV samples for each case: no Quality tables; registration interrupted after Quality entries were written; structurally invalid CSV; simulated cleanup-database unavailability retaining source bytes. It is included exactly once in tools/Verify_P0_A4_Readiness.py. A Node source gate enforces these properties. None of these newly added tests has been executed by the owner yet. Do not treat the earlier 117/174 PASS as validation of this P1 increment.

**Non-goals:** No new multi-sheet XLSX selection, automatic locale conversion, background import task system, undo flow rewrite or UI redesign. Other P1 usability/import issues remain for later increments.

## Single-click owner checkpoint (no repeated P0 or native Save As)

Pull this feature branch once, then double-click **Run_PilotODIN_P1_E2_Preflight.bat** in the repository root.

- It uses .venv-live Python to run ONLY tests/test_p1_import_recovery.py against a temporary PILOTODIN_HOME.
- It runs the Windows system-memory inventory separately, without model inference or network access.
- It prints ONE pilotodin-p1-e2-*.zip containing an exact test log, read-only inventory JSON and a results summary, with no uploaded datasets.
- PASS means only that the new P1 tests passed AND the read-only E2 inventory was collected; actual offline inference and real 8 GB load remain NOT TESTED.

The previous 117/117 frontend, 174/174 backend and native Save As tests do not need replaying for this bounded checkpoint. Do not commit Rust target artifacts or delete project data.

## Early E2 — bounded inventory first, actual 8 GB/offline feasibility still unproved

**New read-only command:** in a Windows PowerShell terminal opened at the repository root, run:

    .\tools\Probe_E2_8GB_Offline_Inventory.ps1

Optional *explicitly selected* local files (never auto-discovered/downloaded):

    .\tools\Probe_E2_8GB_Offline_Inventory.ps1 -ModelPath "C:\path\to\existing-model.gguf" -RuntimePath "C:\path\to\existing-inference.exe"

This creates one JSON file under the user's TEMP directory and prints its path. It records OS architecture, total/free physical RAM at one moment, an 8 GB-class hardware flag, bounded aggregate working-set totals of relevant app/runtime process families, and optional file **size/presence only**. It deliberately omits usernames, folder paths, file names, project records, inference prompts, model weights and network endpoints. It does not launch models, fetch packages, install software, kill processes, run a benchmark or disconnect the network.

**Critical evidence limit:** A snapshot of available RAM is **not** evidence that local Qwen can run offline, generate truthful output, coexist with FastAPI/Tauri/ML on 8 GB, or pass licensing/distribution review. The JSON explicitly records NOT_TESTED and UNDETERMINED for these gates.

### E2 follow-up feasibility experiment (not yet executed)

Only after choosing a real redistributable, licensed, memory-appropriate local Qwen model and inference runtime should we perform one *bounded* owner-approved experiment:

1. **Inventory and licensing:** Determine model version, quantization, GGUF size, inference binary, exact distribution license and runtime ABI. Document whether rights permit shipping together in the target Windows release. Unknown licensing blocks a "ready" decision.
2. **Real small offline generation:** On Windows, launch the exact local runtime using a small approved prompt with networking disconnected; record success/failure, response latency, tokens/s, total process memory and output caveats. Do not claim offline by making a request to an already-online server.
3. **Combined load on a real 8 GB laptop:** Measure OS available memory and peak end-to-end PilotODIN + Tauri + backend + local AI inference, followed by a bounded dataset analysis/ML task. Watch memory pressure, disk paging, crashes, UI responsiveness and graceful degradation when AI is unavailable. A test on a machine with substantially more RAM is **not** an 8 GB certification.
4. **Decision:** Label feasibility **PASS** only with recorded offline token generation, actual 8 GB combined-load measurements, licensing and reproducible invocation. Otherwise **BLOCKED**, **UNDETERMINED** or **FAIL** with a reason and design options (smaller quantization, AI disabled, loading only on demand, or revisiting hardware target).

### Release boundary

P1 and E2 are not a production installer, autonomous Master Analyst/Scientist or final E-01..E-24 acceptance. P0 development evidence and native Save As are preserved. Avoid Hosted GitHub Actions while minutes are exhausted; do not run the final bundled installer prematurely. Next acceptance checkpoint: one isolated P1 import regression + E2 inventory, then decide whether hardware feasibility needs a separate short offline model spike before designing P3/P4 semantics.
