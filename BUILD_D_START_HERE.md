# PilotODIN Build D: Unified Studio

This is a **source-code release**, not a signed Windows installer. Build D updates Build C without replacing your saved local projects or the existing analytical engine.

## What changed

- The optional `#/canvas` experience has been visually rebuilt with the approved light-first PilotODIN Studio identity: ivory/porcelain surfaces, iris-violet accents, teal evidence states, a clearer hierarchy, compact navigation and contextual ODIN.
- Dataset import can now be started directly inside the Canvas (`CSV`, `XLSX`; maximum 40 MB) instead of navigating to the legacy Studio.
- Creating an investigation saves it and triggers a first **verified local snapshot**. Results are stored in the existing SQLite investigation/evidence tables.
- The Canvas displays real project profile metrics and, after a tool run, a grouped comparison chart with a **descriptive-only** finding and evidence reference.
- The Canvas now includes read-only Data Quality and a local HTML report-composer tab. User-selected computed evidence is exported with its result, method/tool version, dataset version and ID. Reports are **not** cloud uploads.
- Artifacts can be pinned for presentation order, inspected, or downloaded as JSON. Pin IDs are stored locally in browser storage; actual evidence stays in SQLite.
- A shortcut to the existing data preparation and Model Lab remains available. The previous Studio is not removed.
- The ODIN panel reads the local-model status and retains Hybrid AI's cloud consent boundaries and safe computation controls.

## Your Windows run procedure

1. **Keep the working Build C folder and its local projects as a backup.** Do not overwrite a running backend while it is serving requests.
2. Extract `PilotODIN_Build_D_Unified_Studio_Source.zip` into a **new** folder.
3. Close Build C's browser tab and stop its development servers. Do not run Build C and Build D simultaneously on the same local ports.
4. Double-click `Start_PilotODIN.bat` from Build D. If dependencies have already been installed in a different extracted folder, the new folder may need its own installation. The start script and `STUDIO_README.md` describe the developer setup.
5. Open `http://localhost:5173/#/canvas`, or use **New Canvas** from the existing Studio. The new interface is the Build D unified experience.
6. Choose an existing project or use **Import a dataset**. You can also import the bundled `examples/demo_property_prices.csv` for a controlled test.
7. Create an investigation, then run a **Compare groups** calculation using `Province` and `PropertyPrice`. The chart must show the computed group medians, and a verified evidence artifact should appear.
8. Switch to **Data Quality** and inspect the missing `Bedrooms` values. Switch to **Report**, select at least one evidence artifact, enter a narrative and download the local HTML report.
9. Click **Ask ODIN**. Ollama readiness must be distinguished from actually receiving an AI answer. With Qwen already installed and Hybrid selected, request a short interpretation and check the displayed model/source attribution.
10. Refresh the page or restart PilotODIN and confirm the investigation and evidence are restored.

## What is still in the previous Studio

Data cleaning that *changes* records, feature preparation, ML training, model evaluation, prediction and the existing richer exploration remain available from the original Studio. Build D links to them while preserving their validated behavior. It does **not** claim those complex workflows have been fully merged into the new Canvas.

## Windows and release validation still required

- This build was **not** successfully compiled via `npm run build` in the authoring environment because the npm registry was unavailable. Run `cd frontend`, `npm install`, and `npm run build` on your Windows machine, or use a previously restored matching `node_modules` directory.
- The TSX files passed TypeScript transpilation/syntax checks; this is **not** equivalent to a full typechecked production bundle.
- The backend suite was run under Python using `PYTHONPATH=.`. The results are recorded in `docs/BUILD_D_VALIDATION.md`.
- Actual Ollama response latency, Windows Tauri packaging, clean-install behavior, memory usage on an 8 GB laptop, accessibility checks and E2E browser interaction tests remain unverified.
- The `design_review/build_d_review.html` file is a **static** visual review with genuine summary values calculated from the bundled *synthetic* sample CSV. It is not the running React application and cannot verify interactions.

## Privacy and correctness rules

This Build D does not write source data during investigation. Any future data-cleaning integration must preserve versioning, approval and undo. AI responses are advisory; only successfully completed allowlisted Python tools produce verified evidence artifacts. Cloud sharing remains opt-in.
