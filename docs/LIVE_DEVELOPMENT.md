# PilotODIN Live Development Workspace

**Purpose:** iteratively polish PilotODIN's fonts, colours, navigation, charts, ODIN interactions, and Python analytics without waiting for a new Windows NSIS installer after every change.

## Start (one-time setup, then one click)

1. In GitHub Desktop, clone PilotODIN and check out \`feature/live-dev-workspace-20261023\` (this work sits on the Build E offline-fix branch). Keep a separate clone from any existing installed release or older production Studio directory.
2. Install **Python 3.11+** and **Node.js 20+** on the development computer. Internet is needed for the first dependency install. You do **not** need Rust or Visual Studio Build Tools to develop the browser UI/backend.
3. In the root of this clone, double-click **\`Start_PilotODIN_Live_Dev.bat\`**.
4. The launcher prepares \`.venv-live\`, installs missing frontend dependencies, then starts two visible PowerShell consoles. It opens **http://127.0.0.1:5173** after the backend and frontend both respond.
5. Keep the two consoles running while you edit. Save a React/CSS file for Vite hot reload; save a Python file for backend reload. **Neither operation produces an installer.**

The launcher shows elapsed startup time at five-second intervals; this is actual elapsed time, **not** an invented percentage. It reports failures instead of silently proceeding. The backend health endpoint is http://127.0.0.1:8000/api/health.

### Files to edit

| Goal | Source |
|---|---|
| Brand colours and application font | \`frontend/src/design-tokens.css\` |
| Shell layout, tab bar, navigation | \`frontend/src/unified-shell.css\`, \`frontend/src/UnifiedShell.tsx\` |
| Other workspace styles | \`frontend/src/studio.css\`, \`frontend/src/styles.css\` |
| Explore charts | \`frontend/src/ExploreWorkspace.tsx\` |
| Investigation and Ask ODIN | \`frontend/src/InvestigationCanvas.tsx\`, \`frontend/src/AssistantWorkspace.tsx\`, \`frontend/src/AIWorkspace.tsx\` |
| Backend analytics and APIs | \`backend/analytics.py\`, \`backend/main.py\`, other \`backend/*.py\` |

**Important:** the central design tokens are a starting point. Some older workspaces still have hard-coded colours and typography; consolidating those rules is part of the next UX refinement phase.

## Strict separation from production

- This launcher uses only \`<clone>/.pilotodin-dev-data\` for SQLite, datasets, trained models, settings and AI keys. This is intentionally a **fresh** development workspace, not a copied production database.
- The installed Tauri app's app-local-data store is **not** opened or migrated by this workflow.
- Development env \`.venv-live\`, cache \`.pilotodin-dev-cache\` and the dev data folder are gitignored.
- Never put production credentials or confidential datasets in test projects. Do not copy a production \`data\` directory into this folder.
- Backend binds to \`127.0.0.1:8000\`; frontend binds to \`127.0.0.1:5173\`. Browser development is intentionally **not** the authenticated Tauri production shell. Keep this developer server on your own trusted computer; do not expose it to your network.
- The full **bundled Qwen3 desktop path** (Rust resource verification, model launch and session authentication) is **not** reproduced by browser Vite. Browser-only ODIN uses local rules or development Ollama/cloud settings as configured. Test packaged offline AI on a real Windows installer at milestone checkpoints.
- Developer dependency installation and runtime model loading are separate operations. Live reload does not update an already-installed EXE.

## Quick quality checks (no NSIS build)

Run from the project root in PowerShell after starting the environment:

\`\`\`powershell
.\.venv-live\Scripts\python.exe -m pip install -r backend\requirements-test.txt
.\.venv-live\Scripts\python.exe -m pytest -q tests
cd frontend
npm.cmd run build
npm.cmd run test:workspace
\`\`\`

When a feature changes, verify the live preview first, then run regression tests before opening a pull request. Only run Tauri/NSIS bundling at an intentional release milestone.

## Troubleshooting

- **Port already in use:** close both previous development PowerShell windows. The launcher will not kill or replace an existing server.
- **Launcher failed before opening browser:** inspect its explicit error and the two PowerShell consoles. Python/Node missing or incomplete initial dependencies are common causes.
- **A view says backend unavailable:** check http://127.0.0.1:8000/api/health and backend console for traceback.
- **Edits don't appear:** confirm you edited the checked-out branch and the source folder used by the launcher, not the already-installed PilotODIN EXE. Hard refresh the browser if needed.
- **Need the native Tauri shell during development:** \`npm run desktop:dev\` requires a configured Rust/MSVC environment and its desktop sidecars/resources; it is a separate integration check, not a replacement for the browser fast loop.
- **Stopping:** close the backend and frontend PowerShell windows. Do not delete \`.pilotodin-dev-data\` unless you intentionally want to reset only your isolated development projects.

## Development rhythm

**Edit -> live preview -> test -> commit -> review.** Consolidate reviewed changes before the next Windows installer. Do not rebuild the 1.5 GiB offline model package merely to try a colour, font or component layout.
