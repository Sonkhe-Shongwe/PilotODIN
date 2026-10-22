# PilotODIN: Build B, the new Investigation Canvas

Start with [docs/BUILD_B_CANVAS_SPIKE.md](docs/BUILD_B_CANVAS_SPIKE.md).

This is the **complete Build A source plus an additive, separate Build B investigation-first experience**. It preserves existing capabilities, the secure Tauri scaffold, AI provider settings and quality workflows. It does not replace them with an HTML toy application.

To use, install existing Python and npm dependencies, start the app, select **New Canvas** in the Studio header. Projects imported in Studio appear in the new canvas. New investigation records and evidence are saved in the current PilotODIN SQLite database.

The standalone HTML review outside this zip is a static design reference using genuinely computed sample aggregates; it is not a functioning copy of the app.

**Validated:** 161 Python tests passed; TypeScript syntax parsed. **Pending:** package installation and real Vite build, browser screenshot/E2E, Windows installer.
