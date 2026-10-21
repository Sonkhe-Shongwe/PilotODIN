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
