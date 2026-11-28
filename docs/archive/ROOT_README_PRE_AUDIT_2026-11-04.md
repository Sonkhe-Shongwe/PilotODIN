# Current development handoff — October 2026

**Latest verified P0–P8 position (26 October):** [Dated development reflection and acceptance register](docs/PILOTODIN_STATUS_REFLECTION_2026-10-26.md). Active P2 reporting completion includes owner-accepted **8/8 future font-resource path tests**, but no actual frozen Python font bundle or production Unicode PDF acceptance. For the current branch HEAD, exact next action and stop conditions, use [SESSION_HANDOFF_CURRENT.md](docs/SESSION_HANDOFF_CURRENT.md). The original 24 October roadmap and older handoff paragraphs are historical snapshots, not proof of release readiness.


**Resume PilotODIN in a new ChatGPT tab:** Start with the **[canonical current checkpoint + copyable handoff prompt](docs/SESSION_HANDOFF_CURRENT.md)**, then use [docs/CONTINUE_HERE.md](docs/CONTINUE_HERE.md) for historical work and review [Master Analyst / Master Scientist and target-discovery research](docs/MASTER_MODES_TARGET_DISCOVERY_RESEARCH.md), the [semantic-inference and low-cost target-ranking deep dive](docs/TARGET_INTELLIGENCE_SEMANTICS_AND_RANKING_RESEARCH.md), and [Master QA Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2). These are current development notes; earlier release readmes below remain historical.

**Product implementation order:** [Consolidated feature inventory and complexity-last roadmap](docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md). This is the current sequencing recommendation, not evidence of delivered code.

# PilotODIN Build D — Unified Studio (October 2026)

**Start here:** [BUILD_D_START_HERE.md](BUILD_D_START_HERE.md). This release contains the unified Canvas interface; the previous Studio and Build C Hybrid AI backend are retained. The Windows installer is not yet validated.

> **Build B is available:** See [BUILD_B_START_HERE.md](BUILD_B_START_HERE.md) for the new investigation-first canvas. The older Studio remains intact.

# PilotODIN 1.0 Desktop Foundation (Build A, engineering preview)

**New:** `desktop/README.md` explains native Windows packaging, source migration and honest test status. This source tree combines the v0.7 full project with v0.8 analytical improvements and adds a Tauri 2 desktop shell, packaged Python sidecar configuration and GitHub Actions Windows installer workflow. This is **not a prebuilt Windows installer**. See `docs/BUILD_A_VALIDATION.md` before using.

The existing `Start_PilotODIN.bat` remains available as an **older development/browser workflow**. For Windows desktop packaging, use `desktop/Build_Windows_Installer.ps1` or run the Windows Desktop Preview GitHub Action.

---

# PilotODIN Studio v0.8 · Intelligent Analytics Workspace

**Start here:** [STUDIO_README.md](STUDIO_README.md)

A redesigned light-first data-science workspace with local-first data quality, interactive exploration, supervised machine-learning experiments, evaluation, predictions and optional Gemini/Groq/OpenRouter intelligence. Existing analytical backend has been carried forward from v0.6 with additional migration and source checks.

To run on Windows, open the inner `PilotODIN` folder and double-click `Start_PilotODIN.bat`. On the first launch, dependencies are installed automatically if Python and Node.js are available. Use `Import_Existing_Projects.bat` before first launch if migrating previous saved projects.

The approved interface concept is included at `docs/Approved_Studio_Design_Concept.png`. It is a visual goal, not an assertion that every element of that reference image is implemented.

This is a source-based preview, not a standalone EXE. Cloud AI is optional, and any live provider limits still apply.

## Latest release v0.8

Read `STUDIO_README.md` and `docs/V08_RELEASE_TEST_REPORT.md`. This source upgrade adds missingness investigations, reviewable median corrections, cloud answer continuation, improved Markdown display and compatibility-aware charts. Install the official v0.8 patch into your EXISTING Studio v0.7 inner `PilotODIN` folder after backup, leaving `data`, `.venv`, and `node_modules` untouched.

## Build E integration status (source checkpoint, not a release)

The Build E source now includes a persistent autonomous investigation loop,
a separate bundled-local-AI runtime boundary, and a protected quality-change
workflow. Data modifications require a preview from
`POST /api/projects/{id}/quality/proposals` followed by explicit confirmation
through `POST /api/projects/{id}/quality/commit`. Direct legacy mutation routes
return HTTP 428; rejection remains available as a non-transforming decision.

`POST /api/projects/{id}/quality/export` downloads the chosen approved
dataset version as a bounded CSV or streaming XLSX, with optional columns and
filters. Exports never modify the original or active working dataset and
escape spreadsheet formulas (including dangerous column headings).

`python -m pytest -q` validates the current Python integration; desktop
frontend compilation, native Windows installation, live bundled AI and combined
8 GB hardware validation are still outstanding.

## Build E integrated desktop shell + saved reports (current source checkpoint)

- `frontend/src/UnifiedShell.tsx`: one persistent app-level navigation with project selection and project-scoped tabs. Legacy analytical panels are mounted on demand; this is an integration stage, not the final dock manager.
- `frontend/src/ReportWorkspace.tsx`: saved report composer, evidence selection, immutable revision history, and authenticated downloads.
- `backend/reports.py`: project-validated immutable evidence snapshots, cross-version lineage, HTML and offline PDF generation from one revision.
- `tests/test_build_e_persistent_reports.py`: API, security, historical, format and source-preservation regression checks.
- `reportlab>=4.2,<5` is now required for PDF export. The Windows build scripts must include it in the Python sidecar.

**Validation boundary:** Python tests passed in a Linux test environment. TypeScript files were syntax-transpiled. npm package installation was unavailable, so a complete `tsc && vite build`, Windows Tauri bundle, AI loading with the packaged model and 8 GB memory validation are **not yet verified**. The Navigator SVG still requires production asset finalisation. Non-active views are unmounted to reduce memory, so some transient form drafts are not yet restored. The ODIN dock is currently a resizable right-side panel; full docking and two-pane split views remain unfinished.

## Build E dockable workspace increment (source checkpoint)

The unified desktop shell can now open one independently mounted secondary analytical view (Understand, Quality, Explore, Prepare, Model, Evaluate, Predict, Deliver, Ask ODIN, or Settings) alongside the primary view. Use the small **Dock beside** icon on an open tab, drag a permitted tab onto the docking strip, or select a view from the dock toolbar. The split can be resized using its grip or keyboard arrows, moved left/right, closed, or reset. Tab selection and split preferences are stored per project; only bounded interface preferences, never dataset rows, are stored here. The core data and evidence remain in the authenticated Python backend.

Safety: the secondary Studio instance receives a fixed project ID and explicit view selection; it does not write the global route or change the selected project. Cross-pane dataset updates trigger version refresh and invalidate prediction state. Expensive panels unmount when closed; changing a docked Studio stage does not discard its transient modelling state. The ODIN investigation dock overlays its own pane rather than compressing the two analytical panes into three narrow columns.

Verify: `cd frontend && npm run test:workspace` (requires `npm install` on a machine with access to the package registry). Backend regression: `python -m pytest -q`. Full `npm run build`, native Tauri compilation, Windows interaction, and 8 GB performance have **not** been verified in the current Linux environment because registry dependencies are unavailable. Do not describe this checkpoint as a Windows installer or release candidate.
