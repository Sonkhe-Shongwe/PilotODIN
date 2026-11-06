# PilotODIN P1 | Read-only deletion impact and future safe-deletion design
**Recorded:** 4 November 2026
**Status:** Impact review implemented and hosted verified. **Permanent deletion NOT implemented or approved.** P1 OPEN and native acceptance pending.
**Authoritative source/test SHA:** [ebd10e2db992](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/ebd10e2db992ee6bc4ec8dc53a436d156d226458)

## Current implemented boundary
- UI: Manage projects → **Review impact** on an active or archived project, read-only. The card shows counts for nonempty linked tables, original-file presence/location classification, managed model-directory candidates, unknown schema, outstanding model/ODIN activity, external-export exclusions, and plain-language limitations. It is **not a delete confirmation dialog**.
- API: GET \`/api/projects/{project_id}/deletion-impact?expected_revision={revision}\`. The result includes \`preview_only: true\` and \`deletion_available: false\`. A project ID is exact; a stale revision receives 409; missing ID receives 404. There is **no DELETE handler and no direct filesystem write** in the impact code.
- Storage: Inventory connection uses SQLite \`PRAGMA query_only=ON\`. Fixed SQL statements count known project-linked records; no user supplied SQL or filesystem path is executed. Original dataset bytes, Quality approvals, reports, model files and other project history are never read or changed by inventory.
- UI never exposes raw local source paths. A symlink, unclassified table, external source, active model run or ODIN run is flagged rather than treated as safe for deletion. File assessment currently identifies original and linked experiment model-directory locations only. It **does not claim a complete manifest**.
- The preview may become outdated if other actors append experiment/evidence rows without bumping the project lifecycle revision. **Expected revision protects metadata identity, not the entire dependency graph.** A future delete must revalidate all content and concurrent writers under durable exclusive controls.

## Known persisted project-linked families inventoried
| Direct/parent link | Indirect dependent records |
| --- | --- |
| Project record, lifecycle metadata, target business context | None |
| Quality state, versions, actions, decisions, approval receipts | None |
| Model experiments | Progress events and run controls via experiment ID |
| Investigations | Evidence via investigation ID |
| ODIN runs | ODIN run steps via run ID |
| Saved Explore snapshots | None |
| Reports, report quality audits | Report revisions via report ID |

Physical file candidates are original CSV/XLSX under the app-managed \`datasets\` directory and model artifacts under \`models/{experiment_id}\`. The inventory does not enumerate all contents within model directories and does not assume that an unknown or symlinked path is safe. Temporary exports, user-selected Save As destinations, copies, external backups, shared settings, downloaded models and the installed desktop are **outside the declared deletion scope**.

## P1-M4 request-entry archive write guard (4 November 2026, hosted verified)
At [tested `1ac2587920cd`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/1ac2587920cd0e482102ce96a24c0b739ad220fe), state-changing HTTP requests to archived projects are denied HTTP 409 by a server-side lookup through direct project IDs or indirect experiment/investigation/report IDs. This complements frontend preservation of archived mounted workspaces. [14/14 backend tests](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41840614063), [145/145 frontend + 5/5 Chromium](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41840976435), and [4/4 real Uvicorn/Chromium scenarios](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41840976488) PASS, with only synthetic datasets.

**Do not confuse with an atomic freeze.** The guard examines project state at HTTP entry, and direct Python work or a request already running when an archive commits may escape the preflight. For irreversible Delete, a full scope-aware, transaction-bound write fence and recoverable crash journal are still mandatory. No Delete endpoint has been implemented.

## P1-M5 scoped Quality transaction fence, 4 November 2026
Covered direct Quality mutation paths and receipt-based Quality prepare/commit now execute authoritative archive checks within the **same `BEGIN IMMEDIATE` SQLite transaction** that writes Quality history. Source [`8a4c66a262fd`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8a4c66a262fd7525c45180b007989473aecaa110), [16/16 backend pytest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41852781940) (backend source unchanged afterward) and [4/4 actual Uvicorn/Chromium](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41853026518) PASS using disposable synthetic projects. This protects against stale project objects and serializes the reviewed Quality modifications with lifecycle archive. No original files removed or changed.

This is **not** a project-wide cross-module write fence. Reports, saved Explore, ML worker state, investigations, model artifacts and auxiliary state still need independently audited commit-time exclusion and durable cross-process cancellation before irreversible deletion. `quality._ensure` may lazily initialize metadata on read paths and is outside this scoped proof. In no case does this work authorise permanent DELETE.

## P1-M6 report, saved Explore and investigation transaction fence, 4 November 2026
Source [`0920202f5089`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0920202f5089a9002427f2e6bd23a41d52d0fae9) extends the previous Quality write/archive transaction fence: `reports.capture_quality`, `reports.save`, `saved_analyses.save`, `investigations.create` and `investigations.run` invoke a reusable archive-state check while holding the **same SQLite `BEGIN IMMEDIATE` writer lock** used for their insert/update. Explore additionally verifies its approved Quality version under that lock. [18/18 disposable backend pytest](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41854793319) and [4/4 actual loopback Uvicorn/Chromium](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41855153909) PASS, with no original dataset changes.

**Still outside this guarantee:** ODIN autonomous background threads and status/step events, model experiments and model files, target-business context, other direct storage writes, in-flight post-commit data reads, filesystem artifacts and crash-recoverable deletion. An entire-project pause, manifest, journal, quarantine and explicit owner authorization are still prerequisites to irreversible deletion. Windows native acceptance is separate and remains OPEN.

## Requirements before adding a real permanent-delete operation
1. **Owner authorisation and written scope.** Identify the exact project and revision; review displayed impact plus any unclassified relations. Require typed confirmation of its visible name and stable ID, and a second explicit irreversible decision. Cancel at any point before commit must leave both SQLite and files unchanged.
2. **Authoritative manifest and freeze.** Re-enumerate project-linked tables, active runs, all file paths and integrity hashes under a durable project-exclusive lock. Protect indirect routes and concurrent Studio windows, Quality approval, background training, autonomous tasks, report writes and saved analysis writes. Do not rely on the UI's current-selection flag or preview revision alone.
3. **No blind unlink.** Refuse paths outside the configured PilotODIN home, symlinks/path traversal, unknown tables, unowned artifacts, unresolved owners and active processes. Never delete user exports, backups or a shared model. A separate manifest and audit trail must be outside the purged project's tables.
4. **Cross-storage crash design.** SQLite and filesystem operations cannot share a single atomic transaction. Design a durable deletion journal/tombstone and a recoverable quarantine on the same managed filesystem. Define exact transitions: prepared, blocked, staged, metadata committed, cleanup pending, purged or restored. Before irreversible purge, each interrupted state must retain a reconstructible project and its original, or a fully recoverable tombstone with a verified manifest. Never claim atomic file plus SQL deletion from SQLite alone.
5. **Failure injection.** Simulate cancellation, old revision/ID, two tabs, active ML/ODIN, read-only files, EXDEV/move refusal, symlinks, blocked directory permissions, crash before/after each durable state transition, locked SQLite, partial model cleanup and interrupted restart, all on disposable projects only. Verify the untouched control project, immutable original and Quality versions at every recoverable boundary.
6. **Native usability and consent.** Validate WebView2 keyboard focus return, screen reader, multi-window selection and error recovery, display scaling and all remaining P1 native gates separately. Hosted Linux Chromium is not a Windows acceptance substitute.
7. **Audit and retention.** Obtain a separate owner decision on quarantine retention, backup scope and whether a true permanent purge is allowed at all. Exact cleanup receipts must be idempotent and redacted of sensitive full paths in the browser UI.

## Test ledger
- [Lifecycle backend #41832930061](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41832930061) **12/12 pytest PASS** at backend source ancestor \`02d6da06\`; syntax, existing import and failed-switch regression included. Its production backend logic is unchanged in final tested SHA.
- [P1 isolated frontend #41833432539](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41833432539), **144/144 Node PASS**, TypeScript/Vite build PASS, **5/5** synthetic Chromium PASS.
- [P1 real HTTP #41833432977](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/41833432977), **3/3** distinct Uvicorn/Chromium scenarios PASS on final SHA. New D/E project-library scenario includes read-only impact before rename and while archived, exact scoped browser GET, then rename, archive and restore with preserved Quality v0 and backend restart.
- No personal project, existing database, file, backup, installer, AI worker, native DEV window or physical Windows environment was used. Earlier tested reversible manager at \`5c261a03765f\` remains historical evidence, not a native acceptance.

**Decision:** Impact inventory HOSTED PASS, Windows native still OPEN. **Permanent Delete remains unimplemented. P1 remains OPEN.** The next primary assignment remains real P1 native acceptance and owner closure/deferral decision under the one-phase policy.
