# PilotODIN v0.2B: Smart Autopilot Increment 1

**Status:** Implemented and locally tested backend foundation. This increment deliberately does **not** add the approved split-workspace React interface, enable automatic execution on upload, or feed cleaned versions into existing Model Lab/analytics. Those belong to the separately approved later increments.

## Core guarantees

1. Uploaded CSV/XLSX source files remain byte-for-byte unchanged. A SHA-256 digest is pinned on upload for new projects, or at first quality scan for projects created by earlier releases. Unexpected changes block quality replay.
2. Every quality transformation is a validated, recorded operation. Dataset versions reference a sequence of operations applied to the immutable original; no destructive source rewrite.
3. **Smart Autopilot is intentionally narrow:** it may trim surrounding whitespace only when a string categorical column passes conservative safety checks. It does not automatically fix spelling, change case, impute, remove duplicates, remove outliers or convert ambiguous data types.
4. Proposed spelling/case harmonisations require explicit approval. Other findings can remain investigation-only.
5. Read-only scans and data previews never change a dataset version. Mutations use a supplied `expected_version` and an exclusive SQLite transaction to reject stale requests.
6. Undo any currently active transformation, provided remaining dependent operations still replay with the same affected-record counts. Restore any prior version to a **new** version. An undo suppresses automatic reapplication until the user explicitly approves again.
7. Audit log includes actions, timestamp, parameters, source (autopilot vs approved), row counts, versions and decisions.
8. The quality engine does not send dataset content to external AI services and does not execute generated code.

## Current detectors

- Conservative automatic whitespace cleanup in unambiguous ordinary categories
- Possible spelling and case differences (proposed merge, manual approval)
- Nulls and whitespace-only strings (investigation, no auto-imputation)
- Exact duplicate rows (investigation, no auto-removal)
- Numerical IQR-fence outliers (investigation, no auto-removal)
- Possible identifiers/high-cardinality fields (information)
- Ambiguous slash-style dates in date-named columns (investigation)
- Numbers represented as currency/thousands-separator text (investigation)

A detected issue is **not** proof of erroneous data. Suggestions should be reviewed with domain context.

## REST API (available in /docs)

| Route | Behaviour |
|---|---|
| `GET /api/projects/{project_id}/quality` | Summary, pending/rejected/applied findings, version, first rows of working data |
| `GET /api/projects/{project_id}/quality/preview?issue_id=...&offset=0&limit=20` | Paginated original vs working vs proposed rows (up to 200 per request) |
| `GET /api/projects/{project_id}/quality/history` | All versions, audit actions and decisions |
| `POST /api/projects/{project_id}/quality/autopilot` | Narrow safe corrections; JSON `{ "expected_version": 0 }` |
| `POST /api/projects/{project_id}/quality/decisions` | JSON `{ "expected_version": 1, "issue_id": "...", "decision": "approve" }` or `reject` |
| `POST /api/projects/{project_id}/quality/undo` | JSON `{ "expected_version": 2, "action_id": "..." }` |
| `POST /api/projects/{project_id}/quality/restore` | JSON `{ "expected_version": 3, "target_version": 0 }` |

Each successful mutation returns the new version. A stale version or incompatible history operation returns HTTP 409 rather than silently changing data.

### Guided manual exercise

1. Start the original v0.2A FastAPI/React commands from README.md.
2. Upload `examples/demo_quality_issues.csv` in the current UI (this only uploads; it does **not** trigger new cleaning automatically).
3. Open `http://127.0.0.1:8000/docs` and identify the new project ID using `GET /api/projects`.
4. Open `GET /api/projects/{project_id}/quality`. Inspect the issue list, note `version: 0`.
5. Send `{ "expected_version": 0 }` to `POST /quality/autopilot`. Only eligible whitespace corrections should be applied; note the returned new version.
6. Scan again, find the proposed `Mpimilanga` category correction, and inspect its issue-specific preview.
7. Approve using the issue ID and **current** expected version. Verify the label changes on the working preview but not in the original preview.
8. Open `quality/history` and use the `action_id` to undo; try restoring any earlier version. Confirm the source file remains unchanged.

## Testing

From the project root, with the backend requirements plus pytest/httpx installed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

22 API tests passed in the build environment, including six pre-existing regression tests. Tests cover narrow automation, typo proposals, missing values, outliers, ambiguous dates, duplicates, leading-zero identifiers in the quality CSV loader, approval/rejection, version concurrency, undo, restore, dependency conflicts, original-file integrity and persistence across API clients.

## What is **not** implemented yet

- The split-workspace data-quality screen, interactive on-page approval buttons and concise UI notifications
- Automatic run triggered by UI upload; currently explicit API-triggered
- Advanced learned imputation, safe duplicate deletion or data-type conversion actions
- Rule-driven domain validators, complex cross-column consistency or LLM semantic inference
- Cleaning-version integration into training, model invalidation and Explore charts
- Scaling beyond the v0.2A limits: 15 MB, 30,000 rows, 100 columns
- Full fidelity of Excel *display formatting*. For CSV quality previews, common explicitly named identifiers such as `CustomerID` are loaded as text to protect leading zeros; ambiguous columns still require review. The existing v0.2A ML importer has not yet adopted these protections.

Keep v0.2A installed separately while testing this incremental full-project copy. Existing SQLite project records contain file paths; copying just the database into a different directory does not safely migrate the complete project.
