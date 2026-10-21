# PilotODIN Studio v0.8 | One consolidated update

**This package updates an existing PilotODIN Studio v0.7 installation. It does not create a new user project.**

1. Close the frontend window and the backend window, even if the Chrome tab is still open. Stop any old v0.6 instances too.
2. Make a backup of your existing **inner** `PilotODIN` folder, especially the `data` folder. Do not delete your existing installation.
3. Extract the ZIP to a temporary folder. It contains `backend`, `frontend`, `tests`, `docs`, plus launchers and instructions.
4. Copy **the contents of the extracted patch**, not the folder itself, into the inner `PilotODIN` directory containing `Start_PilotODIN.bat`, `backend` and `frontend`.
5. Choose **Replace files in the destination** if Windows prompts.
6. Do not remove or overwrite `data`, `.venv` or `frontend/node_modules`; none are included in this patch.
7. Double-click `Start_PilotODIN.bat` to launch. Existing `http://localhost:5173` should open. If the launcher warns port 8000 or 5173 is occupied, close the old application runtime window before retrying.
8. Once running, exercise the workflow, then run `Self_Test_PilotODIN.bat` for Windows-specific regression and production frontend build checks.

**Important:** The application is still a developer-operated local web/desktop-style workspace, not a self-contained `.exe`. The new intelligence features are evidence-based and controlled, but not unrestricted autonomous AI or a bundled local language model. No API keys are ever included in this release.
