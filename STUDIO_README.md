# PilotODIN Studio · Complete Project

A new light-first frontend with the existing working local-first Python analytics, data-quality, ML and multi-AI backends. This is a **Studio preview**, not a signed Windows installer or a production-certified application.

## What's new in v0.8 (October 2026)

- Real, read-only missingness investigations: local row positions, comparisons of affected vs other records, group-level missing counts and source-aware cautions. Cloud providers receive only numeric aggregate facts, never the row positions or category labels.
- Explicitly approved numeric median imputation as a versioned working-data transformation, with evidence preview, no automatic execution, preserved originals and Undo in Data Quality history. Categorical, free-text and datetime imputation is intentionally not automated.
- Provider output limit increased, explicit finish-reason/incomplete metadata, user-controlled **Continue answer** and safer Markdown tables/lists rendering. These improve long replies but cannot guarantee provider availability or correct reasoning.
- Chart builder prevents incompatible scatter/histogram choices, preventing avoidable 422 requests.
- Project home now shows actual completeness instead of a decorative chart that could be mistaken for data. Model comparison and prediction result interpretation also improved.
- Startup checks fail clearly if another old PilotODIN instance occupies ports 8000 or 5173. Localhost ports 5173–5179 are safely recognised for development API origins.
- Automated regression tests and a reproducible release report are included in `docs/V08_RELEASE_TEST_REPORT.md`.

## What is new

- New light-first interface: violet/iris and teal accents, modern Manrope/Inter typography (Windows Segoe UI offline fallback), responsive workspace and calm navigation.
- New project home with real dataset statistics, recent work, quality alerts, and clear starting actions.
- Contextual ODIN assistant drawer that is available across analytical workspaces. It uses existing local and opt-in multi-provider AI endpoints.
- Separate sidebar/content scrolling, responsive app shell, keyboard workspace search (`Ctrl+K`), quick transitions, load feedback and preserved Explore/Quality/Chat state.
- Existing data quality proposals/undo, EDA chart building, feature preparation, 5-model comparisons, holdout evaluation, prediction pipelines, AI Settings and provider handshake continue to use the Python backend.

## Windows startup

Extract the ZIP, then open the INNER `PilotODIN` folder and double-click `Start_PilotODIN.bat`. On first run it creates a Python virtual environment and installs Python/Node dependencies if required; subsequent starts reuse them.

Requirements: Windows, Python 3.11+, Node.js 20+, internet for first dependency installation and optional cloud AI. Python and Node installations are **developer prerequisites**; this is not yet a self-contained `.exe`.

Frontend: http://localhost:5173 · Backend: http://127.0.0.1:8000/docs

## Move projects from an older PilotODIN

Close both applications. **Before starting this new version**, double-click `Import_Existing_Projects.bat`, paste the full path to your OLD INNER PilotODIN folder (which contains `data`, `backend` and `frontend`) and follow the prompts. It copies your old `data` directory, preserves the old installation and rewrites database dataset paths for the new folder. It refuses to overwrite an existing non-empty destination `data` directory.

The old credentials are stored using Windows DPAPI, and can typically be decrypted only under the same Windows user account on the same machine. If you change machine/account, enter fresh API keys in AI Settings. Never paste keys into chats or source files.

To stay safe, keep your old folder until you have opened and verified the migrated projects, datasets, quality history and trained models in Studio. Source code and sample datasets are included, but no private data or keys are bundled.

## Development

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
# second terminal
cd frontend
npm.cmd install
npm.cmd run dev
```

Tests from project root: `.\.venv\Scripts\python.exe -m pytest -q tests` (install pytest if needed).
Frontend check: `cd frontend; npm.cmd run build`.

## Important limits

- A full React production build and live Windows browser verification could not run in the build container because Node packages were unavailable offline. The app needs `npm install`/`npm run build` on your Windows computer for final verification.
- Frontend elements use local API calls. The cloud AI models require your opt-in and individual API keys; free provider availability is not guaranteed.
- Offline intelligence is rules/statistics-based, not a local flagship LLM. No local LLM is bundled. Model training and evaluation are not reliable when data are unsuitable or too small; review baseline and test warnings.
- For large files, software limits, memory use and performance depend on hardware. Charts can sample or truncate groups; labels disclose these cases.
- Do not publicly deploy the local backend without proper authentication and production security work.
