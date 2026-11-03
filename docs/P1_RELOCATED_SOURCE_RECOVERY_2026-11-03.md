# P1 relocated original dataset: safe recovery protocol
**3 November 2026. Evidence: owner native Windows FastAPI traceback. Product phase P1 only.**

## Observed cause
A project labelled `day` appears in the current isolated project catalogue, and its metadata endpoint returns HTTP 200. Its `/api/projects/{id}/live-profile` request returned 500 because `backend.quality._ensure` attempted to SHA-256-hash an **original CSV referenced by an absolute path from an earlier checkout**, but that file no longer exists at the saved location. The owner moved the source tree to a different checkout folder. The original was not found at its *old referenced path*; whether it exists under the current workspace has **not been checked**.

The versioned Quality engine fingerprints the *original uploaded bytes*, and the persistent SQLite record stores the original `dataset_path`. A file with the same filename is NOT automatically trustworthy. Do not delete or reimport the existing project, reset `quality_state` or `quality_versions`, rewrite the SQLite database, or silently search-and-bind a same-named replacement. Never print user dataset contents to public GitHub.

## Read-only Windows candidate inspection
Open a separate PowerShell in the repository root. Leave the existing isolated backend and Tauri smoke app running. This code reads the **local test-workspace database** in SQLite read-only mode, checks recorded and current-workspace source candidates, and compares any readable candidate's SHA-256 against the pinned Quality checksum. It does **not** write to disk, modify the database, print source bytes or access the installed application data.

```powershell
$python = ".\.venv-live\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Isolated Python environment unavailable." }
@'
from pathlib import Path
import hashlib, sqlite3

home = Path.cwd() / ".pilotodin-dev-data"
db = home / "pilotodin.sqlite3"
if not db.is_file():
    raise SystemExit("Isolated project database not found. Stop without creating one.")
with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as con:
    rows = con.execute(
        "SELECT id,dataset_path FROM projects WHERE name=?",
        ("day",)
    ).fetchall()
    if len(rows) != 1:
        raise SystemExit(f"Expected one project named day; found {len(rows)}. Stop.")
    pid, original_reference = rows[0]
    pinned = con.execute(
        "SELECT original_sha256 FROM quality_state WHERE project_id=?",
        (pid,)
    ).fetchone()
    expected = pinned[0] if pinned else None

original = Path(original_reference)
candidate = home / "datasets" / original.name
print("Saved original still exists:", original.is_file())
print("Candidate exists under current isolated workspace:", candidate.is_file())
print("Pinned SHA-256 available:", expected is not None)

for label, path in (("Saved original", original), ("Current workspace candidate", candidate)):
    if not path.is_file():
        continue
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            digest.update(chunk)
    print(f"{label} matches pinned SHA-256:", expected is not None and digest.hexdigest() == expected)
'@ | & $python -
```

Record only existence booleans and whether SHA-256 equals the stored pin. If the candidate is absent, do not guess or fabricate the source. Search personal backups without copying any unknown data into the test project.

## Owner-controlled restoration gate
- If **no byte-identical original exists**, stop. Keep project metadata and history unchanged. A new **disposable synthetic** project may be used for separate native keyboard QA, but must not be portrayed as restoring `day`.
- If an original file exists **and matches the pinned SHA-256**, treat it as a *candidate* only. Before any path rebase, request explicit owner approval; back up the **entire** `.pilotodin-dev-data` (including SQLite and source files) to an owner-chosen safe local destination with the backend stopped; review metadata and all version references; develop a dry-run, fingerprint-verified, transactionally safe relink routine and test it against synthetic moved workspaces first. Do not run raw SQL from a screenshot.
- After an approved fix, verify `/api/projects/{id}`, `/api/projects/{id}/live-profile`, full Quality version/hash invariants, then check actual Tauri project load using a disposable test workflow. A successful metadata GET is not complete recovery.

## P1 source-level protective fix and test truth
[`1d9fb1e0da22`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1d9fb1e0da2207e3e06f6e01d480777504a024c0) changes `backend/quality.py` and `backend/main.py`: missing or inaccessible originals become safe HTTP 409 conflicts without raw filesystem paths, tampered originals retain existing 409, and no automatic relink occurs. The new source recovery tests use temporary databases and fixture CSVs. [GitHub-hosted run #41694011119](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41694011119) verified Python source compile and **11/11 focused tests PASS**. This is Linux CI evidence, not a Windows runtime retest or user-data repair.

The nine Windows native keyboard/display scaling/snap checks and integrated project restoration remain **OPEN**. Preserve untracked `frontend/src-tauri/Cargo.lock` and `frontend/src-tauri/gen/`. No installer, sidecar, models or AI execution is part of this recovery.
