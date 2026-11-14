# P1 upload staging and recoverable disk-write failures

**25 October 2026: owner-observed focused Windows gate PASS (screenshot); diagnostic ZIP not independently inspected.**

## Why
The previous `backend/main.py::create_project` wrote upload source bytes via `path.write_bytes(b)` before its error-handling `try`. A recoverable partial disk-write/flush failure therefore could leave an orphaned partial source under `data/datasets`, even when no project was saved. This is a concrete P1 failure-path gap, not a defect claim about a past successful import.

## Narrow change
- Stage bytes under a newly generated `<id>.<ext>.uploading` file using exclusive creation (`xb`), flush and `os.fsync`. Publish to the final generated `<id>.<ext>` via same-directory `os.replace` only after the full write succeeded.
- Catch failed write, sync, rename, parse, profile, metadata save or Quality registration. Remove the temporary staging file, invoke the existing transactional metadata rollback and final-file cleanup; preserve the existing refusal to delete a published source if metadata rollback might have failed. A failed staging cleanup is explicitly logged and reported as a 500 rather than misrepresented as clean recovery.
- Existing CSV/XLSX extensions, 40 MB application-level read limit, generated path, imported original immutability, checksum/Quality pinning and existing positive import semantics are unchanged.
- This does **not** promise safety after abrupt OS power loss, arbitrary filesystem corruption or adversarial network/filesystem behavior. The full content is still read into memory before staging as before; does not address multipart parser spooling or memory usage.

## Focused gate
`Run_PilotODIN_P1_Upload_Staging.bat` invokes `tools/Verify_P1_Upload_Staging_Local.py` with isolated `PILOTODIN_HOME`; only new `tests/test_p1_upload_atomic_staging.py` (four synthetic tests: write/sync failure, rename failure, successful checksum pin, bad data rollback) and directly affected existing `tests/test_p1_import_recovery.py` (four tests). One `pilotodin-p1-import-stage-*.zip` with result JSON and phase log. No Vite/Node/old P4/P3/P5/P0/A4 replay because frontend and those paths are unchanged.

**Owner Windows gate PENDING.** GitHub source inspection alone cannot establish the result. If FAIL, upload ZIP for a targeted fix; if PASS, report the pass. No real user dataset import, installer, Qwen download, Actions or high-RAM work.

## After green
Continue the complexity-last reliability/reporting work by reviewing the next evidenced P1/P2 gap. Do not create speculative P4 sub-increments or prematurely implement P6 Master workflows.

## Owner focused acceptance

Owner screenshot shows `P1 isolated import staging: PASS`, `P1 import staging checks passed`, one local diagnostic ZIP `pilotodin-p1-import-stage-li2_fvh_.zip`. The ZIP was not uploaded; source-only and screenshot evidence support scoped developer acceptance, not verified exact Pytest counts or real OS power-loss resilience. Latest next P2 report navigation work is documented in `docs/P2_REPORT_OPEN_ACCEPTANCE.md`.
