# PilotODIN 1.0 Build B: Investigation Canvas Spike

Date: 21 October 2026  
Status: implemented source-level proof, awaiting frontend installation/build, graphical review and Windows acceptance.

## Purpose

This is **not** a reskin of the existing Studio's ten pages. Build B introduces a distinct, opt-in, canvas-first experience alongside Build A. The key unit of work is an *Investigation* bound to a project and exact dataset version. An evidence card is created **only after a verified, allowlisted local computation succeeds**.

The prior React Studio, experiments, quality versioning, AI providers, Tauri sidecar and secure desktop API are preserved rather than rewritten. Build B deliberately does **not** activate cloud LLM calls, auto-cleaning, unreviewed data changes or autonomous multi-step agents.

## New frontend

- `frontend/src/InvestigationCanvas.tsx`: new investigation-first React experience.
- `frontend/src/investigation-canvas.css`: independent shell, living evidence canvas, contextual ODIN tool panel, responsive layouts and reduced-motion support.
- `frontend/src/main.tsx`: adds in-place hash-based experience switching; existing desktop sidecar authentication and startup sequence are unchanged.
- `frontend/src/App.tsx`: adds **New Canvas** entry; the original Studio remains available.

**How to enter:** run PilotODIN as before, select **New Canvas** in the old Studio header or set `#/canvas` in the running app's URL. Choose an imported project, create an objective and run an allowlisted operation. **Open legacy Studio** returns to the previous experience without reinitialising the app.

## Backend contracts (new)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/projects/{project_id}/investigations` | List saved investigations and current-version status |
| POST | `/api/projects/{project_id}/investigations` | Create version-bound investigation with objective |
| GET | `/api/investigations/{investigation_id}` | Resume question and ordered evidence artifacts |
| POST | `/api/investigations/{investigation_id}/runs` | Run one allowlisted local tool and persist its output |

Request for run: `{ "operation": "compare", "params": {"x": "Province", "y": "PropertyPrice"}, "expected_version": 0 }`.

**Allowlisted operations:** `overview`, `compare` (median categorical groups), `missingness` (verified column diagnostics), `distribution` (numeric quantiles and IQR fences). Unsupported operations and nonexistent columns are rejected. The comparison deliberately does not assert causation. Raw data does not go to cloud services.

New SQLite tables `investigations_v1` and `evidence_v1` are additive; they do not modify existing projects, models, or quality-version records. The stored result records `tool_version`, parameters, version, timestamps and status. If the working version advances, older evidence is retained but marked stale and no new runs can be attached to that old investigation.

## Suggested inspection route

1. Open an existing project, preferably `examples/demo_property_prices.csv` imported in Studio.
2. Open **New Canvas**, create an objective such as `How does PropertyPrice vary by Province?`.
3. Run **Dataset snapshot**, **Compare groups** (`Province` and `PropertyPrice`), and **Inspect missingness** (`Bedrooms`).
4. Expand **Inspect evidence**, then switch investigations and restart the app. Recorded evidence IDs should remain unchanged.
5. In the original Studio, approve a genuine data-quality change. Return to this investigation and refresh. Old evidence should display a stale warning; a new investigation is required for current data.

## Testing performed in this environment

- Python test suite: **161 passed**, including five newly added persistence / computation / versioning tests.
- New React component: TypeScript transpilation passed with no syntax diagnostics.
- New React canvas semantic check: passed using temporary type stubs due missing npm packages. This is **not** a replacement for a real TypeScript/Vite build.
- Full `npm install`: **blocked** by `EAI_AGAIN` DNS resolution for `registry.npmjs.org`.
- Chromium automated screenshot: **not obtained** due headless browser process stalling in this container.
- The self-contained `PilotODIN_New_Canvas_Review.html` contains a **static** graphical review with numbers computed using the bundled sample CSV. It is **not** the running React app and does not verify the Vite/Tauri presentation.

## Local startup (with developer tools installed)

```powershell
# Terminal 1, from PilotODIN root
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm install
npm run build
npm run dev
```

Open `http://127.0.0.1:5173/#/canvas`. Do not expose the backend on a public interface. Desktop packaging still follows the existing `desktop/README.md` and requires Windows build validation.

## Out of scope in this spike

- Unrestricted infinite node editor, drag-to-anywhere links, independent chart editing, custom dashboard layouts.
- Asynchronous multi-step ODIN with pause/cancel/retry, external providers and LLM-driven plans.
- Full permanent canvas block layout/pinning, report production, shared project collaboration, cloud accounts.
- Functional `Model`, `Evaluate`, `Predict` and `Quality` operations inside the new canvas (still available in legacy Studio).
- Clean Windows installer, real-device performance benchmarks, comprehensive accessibility tests, browser end-to-end tests.

## Decision gate

Review the **new canvas composition**, not the old Studio mockups: compact desktop rail, project/investigation thread, question-driven evidence document, optional ODIN tool panel. After visual review and a real frontend build, decide whether this should become the primary Windows surface. Only then progressively incorporate other Studio capabilities.
