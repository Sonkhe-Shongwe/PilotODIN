# P1 relocated original dataset: safe recovery protocol
**3 November 2026. Evidence: owner native Windows FastAPI traceback. Product phase P1 only.**

## 3 November: Owner-executed recovery command succeeded, endpoint retest outstanding

The owner supplied screenshots proving that their local tracked branch fast-forwarded to `f6f9f0d`, and the new guarded utility ran successfully on Windows against the **isolated development workspace**. Its read-only stage verified the original fingerprint and Quality version. The owner then used the explicit confirmation ID and fresh backup destination, and the `--apply` stage printed:

```text
BACKUP VERIFIED AND SINGLE SOURCE-PATH RELINK COMMITTED.
```

This is evidence of a **completed local backup and original-reference database relink as reported by the script**; it is not an independent audit of the backup or an end-to-end confirmation that `/live-profile` now works. No source file replacement, Quality history reset, approved transformation or installed-user-app migration was requested. **Do not run `--apply` again.**

**Next verification, backend and native only:**
1. Keep the private backup outside the repository. Start exactly one isolated DEV backend with `tools/run_live_backend.ps1` from the current repository root.
2. In a separate terminal, GET `/api/health`, `/api/projects/{id}` and `/api/projects/{id}/live-profile`, printing status codes only. Expect 200 for each; keep any new 500 and Uvicorn traceback for targeted diagnosis.
3. Confirm the DEV ONLY Tauri app loads the project without "Could not open project", inspect the unchanged Quality history and begin WIN-K1..WIN-A1 with disposable data. No inference or cloud AI action required.
4. Record separate PASS/FAIL/BLOCKED for post-repair API, user-interface project load, and all native acceptance checks. Neither source-relocation repair nor hosted 30/30 synthetic tests certifies native release.

## Observed cause
A project labelled `day` appears in the current isolated project catalogue, and its metadata endpoint returns HTTP 200. Its `/api/projects/{id}/live-profile` request returned 500 because `backend.quality._ensure` attempted to SHA-256-hash an **original CSV referenced by an absolute path from an earlier checkout**, but that file no longer exists at the saved location. The owner moved the source tree to a different checkout folder. The original is missing at its *old referenced path*, but the owner has since confirmed a candidate exists in the current isolated workspace and its SHA-256 **matches the original Quality pin exactly**. **Owner has now executed the guarded backup-first relink successfully on Windows**, with the utility reporting the backup verified and one-row path update committed. Actual endpoint/native project retest remains pending.

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


## Owner's 3 November source identity check: verified, not repaired

The owner ran the read-only original-file check against the isolated `.pilotodin-dev-data` database and current datasets directory:

- The **old recorded source path does not exist**.
- The same-named CSV candidate is present inside the current isolated workspace's `datasets/` folder.
- The candidate's actual SHA-256 **exactly matches `quality_state.original_sha256`**.

This closes the *candidate identity* question for the existing `day` project, **not** the persisted-reference recovery or native Windows project load. Do not publish the full local path, file name or hash in public QA records.

## Guarded, backup-first path repair tool: ready for owner execution

The repository now includes [`tools/p1_relink_original_source.py`](../tools/p1_relink_original_source.py). It is **read-only by default** and targets only the isolated development workspace from the repository root. It validates exactly one named project, available Quality version, old path missing, a real candidate in current `datasets/`, and its complete original SHA-256. It never creates a database during inspection. The explicit `--apply` path additionally requires confirmation of the exact project ID, a fresh backup directory **outside** the repository, no listener on 127.0.0.1:8000, full-workspace byte-for-byte backup comparison, and a guarded SQLite update affecting exactly one `projects.dataset_path` row. It does **not** overwrite original CSV bytes, change `quality_state`, `quality_versions`, approvals, transformations or the installed application's workspace. It refuses mismatches and unexpected state changes.

**Step A, safe to run while the DEV backend is running, after fast-forwarding the correct clean feature branch:**

```powershell
$branch = "feature/live-dev-workspace-20261023"
if ((git branch --show-current) -ne $branch) { throw "Wrong branch" }
if (git status --porcelain --untracked-files=no) { throw "Tracked changes require review" }
git fetch origin $branch
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git merge --ff-only "origin/$branch"
if ($LASTEXITCODE -ne 0) { throw "Fast-forward failed" }
& .\.venv-live\Scripts\python.exe tools\p1_relink_original_source.py --project-name day
if ($LASTEXITCODE -ne 0) { throw "Read-only inspection blocked" }
```

The last command prints the exact project ID and **`READ ONLY`**. It does not write.

**Step B, optional explicit owner-approved repair only after reviewing Step A and choosing to proceed:**

1. Close the DEV ONLY Tauri window and stop its Tauri terminal normally. Stop the isolated Uvicorn backend using Ctrl+C in the server terminal. Never stop an unrelated user's service. Verify no listener remains on local port 8000, no unsaved form needs preservation, and no second PilotODIN process holds the dev workspace.
2. Use a **new** backup directory outside the repository. Keep this private local backup; never commit it or publish its contents.
3. Invoke `--apply` with the exact project ID printed by Step A, deliberately approving the one-row relink:

```powershell
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Port 8000 still occupied: stop safely before repair" }
$backup = Join-Path $env:USERPROFILE ("PilotODIN-dev-backup-{0:yyyyMMdd-HHmmss}" -f (Get-Date))
& .\.venv-live\Scripts\python.exe tools\p1_relink_original_source.py --project-name day --apply --backup-to "$backup" --confirm-id "PASTE_EXACT_ID_FROM_STEP_A"
if ($LASTEXITCODE -ne 0) { throw "Repair blocked; do not retry with another ID or overwrite backup" }
```

The expected success line is `BACKUP VERIFIED AND SINGLE SOURCE-PATH RELINK COMMITTED.`. The backup contains private dataset bytes and an unchanged pre-repair SQLite snapshot. If any safety check fails, stop and inspect; never force an update.

4. Start the isolated backend again via `tools/run_live_backend.ps1`; verify `GET /api/projects/{id}` and `GET /api/projects/{id}/live-profile` each return 200 using the original single ID, without printing or posting dataset rows. Reopen the DEV ONLY Tauri window, verify project restoration and original Quality version/history, then resume WIN-K1..WIN-A1 native acceptance. A success in synthetic Linux CI **does not** prove local Windows repair until observed.

**Automated source-level evidence:** The repair utility and eight synthetic refusal/snapshot tests were committed at [`3ea246bc64ad`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/3ea246bc64ad17e795d760aa180e5bf3aaaaa45d) with first GitHub run [#41698128851](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41698128851): **19/19 PASS**. Two additional regression cases at [`144d2ed289f0`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/144d2ed289f02b2924baf1e373be2ed320f5a66b) specifically verify a legacy Windows absolute path and refusal if candidate bytes change after inspection. The latest [CI run #41698423812](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41698423812) **completed successfully, 21/21 Python tests PASS**; no actual user's data or Windows install was tested or modified by GitHub.


## Windows closed-port timeout: additional source fix (3 November)

The owner confirmed `Get-NetTCPConnection -LocalPort 8000 -State Listen` produced **NO LISTENER**, but a Python loopback `socket.create_connection` raised `TimeoutError` after the DEV backend was stopped. The original recovery implementation only allowed `ConnectionRefusedError`, therefore correctly blocked before changing SQLite or creating a backup.

[Source commit `9a7929c0233a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9a7929c0233a4dfbdfbe146bd1a5b11275d3aa4c) adds a **fail-closed Windows-only fallback**: on a TCP timeout, run native `Get-NetTCPConnection -State Listen` under bounded PowerShell execution, and accept only a successful, exactly `P1_NO_LISTENER` response. A listener, failed query, unexpected output, unavailable PowerShell and non-Windows timeout still **block**. No weakening of the source SHA-256 pin, one-row update, backup verification or explicit consent. Actual [hosted CI run #41703658280](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41703658280) **30/30 Python tests PASS**, including mocked Windows fallback and failure cases; this is not yet an executed Windows-specific regression.

**After a safe fast-forward to the new HEAD:** Re-run the default read-only inspect first. If still matching and the backend/Tauri instances are stopped, execute the same explicit `--apply` command from the existing section with a **fresh** private backup path and the exact project ID. Do not reuse a partially-created backup folder. Do not stop unrelated processes or disable firewall protection. If it still blocks, share the exact new error without trying to bypass it.

