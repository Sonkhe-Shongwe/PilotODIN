# PilotODIN Build D.1: Branding, Project Context and Diagnostic Fixes

This is a targeted correction for the Build D Unified Studio source. It does **not** change your dataset files, project database, model files or AI provider configuration.

## What was corrected

1. **Brand identity:** Navigator Route 2 direction, using a navy circular directional symbol with connected accents, lowercase `pilot` in teal (`#148F9B`) and `ODIN` in deep violet (`#31218D`). The updated SVG is used by both Studio and Canvas, and the Tauri icon assets were regenerated. This is the approved identity **direction**, not a separately signed-off final vector master.
2. **Unclear `missingness` project label:** The name comes from the filename stem used when the CSV/XLSX was imported. The bottom-left card now clearly says `ACTIVE PROJECT`, displays a human-readable project title and shows the original filename. It also shows row count and dataset version once loaded. The original project name and dataset are not modified.
3. **Generic `Failed to fetch`:** Network errors now identify the local backend origin and failing API route. The Canvas loads profile, overview, investigation history and recommendations independently, so an optional endpoint failing cannot blank all four sections. Connection failures show a Retry action. `Diagnose_PilotODIN.bat` checks the four routes and Ollama locally, without uploading data.
4. **Additional discovered defect:** The evidence-run handler used an undefined investigation variable after a successful tool call; the redundant block was removed, preserving the computed artifact instead of triggering a misleading snapshot warning.

## Install correction patch over an existing Build D folder

1. Close both PilotODIN Backend and Frontend terminal windows; close the browser tab.
2. Make a backup copy of your current Build D folder, especially `data/`.
3. Extract the patch ZIP into the **root of your Build D project folder** (the folder containing `Start_PilotODIN.bat`), and permit replacement of the listed frontend files and icons. You should end up with `frontend/src/InvestigationCanvas.tsx` in that folder, not `PilotODIN/frontend/...` nested underneath.
4. Double-click `Start_PilotODIN.bat`. Go to the new Canvas and do a hard browser refresh (`Ctrl+Shift+R`).
5. If the warning returns, double-click `Diagnose_PilotODIN.bat`. Note which `/api/...` route fails and any backend traceback shown in the PilotODIN Backend window. Do not post your private dataset rows.

## Expected acceptance checks

- The Studio and Canvas use the Navigator brand family (matching symbol and pilot/ODIN wordmark).
- Imported file `missingness.csv`, for example, appears as `Missingness`, labelled `ACTIVE PROJECT`, with the original filename shown below.
- A failed local request names the route; unrelated successful cards remain visible.
- The Retry action can refresh connectivity.
- An investigation's comparison artifact remains available after a successful run and is recoverable after restarting the app.

## Verification performed here

- All 179 Python backend tests passed.
- Changed TypeScript/TSX modules passed syntax parsing.
- Full Vite/Tauri compilation and the exact route failure on your Windows computer are not yet verified here. This patch includes a local diagnostic script to obtain that evidence.

## Privacy

The patch deliberately does not include or overwrite `data/`, `.env`, `.venv`, `node_modules`, API secrets or installed Ollama models.
