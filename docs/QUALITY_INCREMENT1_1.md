# PilotODIN v0.2B Increment 1.1 — detection-quality patch

This is a **targeted update** for an existing PilotODIN v0.2B Increment 1 installation. It does not replace the frontend, change the API or database schema, change saved projects, or enable ML training on cleaned working datasets. No new Python or npm dependencies are required.

## Fixes

1. **Structured/date values are never passed to the ordinary fuzzy-spelling recommender.** Temporal columns identified by their names, date-like strings in otherwise unnamed columns, numeric tokens, URLs, email-like values and machine-readable mixed alphanumeric codes are protected. Date-specific ambiguity findings are still reported, without a suggested replacement date.
2. **Do not double-report whitespace as spelling.** Labels already flagged for surrounding whitespace are not also offered as spelling or case corrections for those same values. After trimming, fresh findings can be generated for any remaining genuine case/spelling inconsistencies.

These are conservative **detection** safeguards. They do not introduce automatic category merges, imputation, date conversion or row deletion.

## Installation — existing folder, no new venv or npm install

1. Stop the backend in its VS Code PowerShell terminal with `Ctrl+C` before copying files.
2. Open the **existing** `PilotODIN` project root in VS Code (it contains `backend`, `frontend` and `.venv`).
3. Download `PilotODIN_v0.2B_Increment1_1_Patch.zip` to your Downloads folder.
4. In a terminal at the project root, run:

   ```powershell
   Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\PilotODIN_v0.2B_Increment1_1_Patch.zip" -DestinationPath . -Force
   ```

   This replaces only `backend/quality.py`, `tests/test_quality_increment1.py` and adds this document. Your virtual environment, SQLite database, uploaded datasets and models are not included in the patch.

5. Restart the existing backend:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```

   The frontend stays as it was. Start it normally if it is not already running.

6. Optional test suite, **if pytest and httpx are already installed**:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```

## Manual verification on your existing example project

- `GET /api/projects/{project_id}/quality` should now omit the `InvoiceDate` *spelling* suggestion (`03/04/2025` -> `14/04/2025`), but still show the separate *ambiguous dates* investigation.
- A value ` Mpumalanga ` should have one whitespace issue, not an additional spelling issue for the same whitespace.
- The real typo `Mpimilanga` -> `Mpumalanga` remains a review-only spelling suggestion until approved.
- Existing corrections and versions remain. The current data version will **not** change when merely updating the Python file or reading the quality results.
- For the specific example state at **version 3** after approving `Mpimilanga`, the total issue count should change from **8 to 6** without changing data versions or historical actions.

## Verification

- **32 backend tests passed** in the build environment: 22 original tests plus 10 new regression tests, including the user's example dataset, date-like values, machine-readable codes, genuine typos, whitespace deduplication and version/undo stability.
- Existing date recommendations that users might have previously approved are **not undone automatically** by this update; review those historical transformations manually.

Future Increment 2 UI and Increment 3 cleaned-data ML integration are not part of this patch.
