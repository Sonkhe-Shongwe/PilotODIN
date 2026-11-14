# P5 — Cooperative ML cancellation and explicit soft training time limits

**25 October 2026 — focused owner Windows verification PASS (uploaded ZIP inspected).**

PilotODIN ML uses Python `BackgroundTasks`, scikit-learn `cross_val_score` and blocking estimator `fit` operations. These cannot safely be force-killed mid-operation in the existing in-process architecture. This feature implements **safe cooperative stopping** at observable, finite code boundaries. It is not a hard execution deadline or general task scheduler.

## New behavior and safety contract

- **Queued experiments:** `POST /api/experiments/{id}/cancel` atomically changes `queued → cancelled` and appends an actual terminal progress event. The background worker cannot claim this job afterward; the Low-memory one-training slot is released. Repeated cancel requests return `already_finished` without duplicate history.
- **Running experiments:** the same local-authenticated API atomically sets a persisted **cancel_requested** bit but leaves status **running** until the worker **actually stops**. The Evaluate interface accurately says "Cancellation requested; the current fitting operation may still be running." A worker stops at checkpoints before and after baseline CV, each candidate CV/fit, and during post-training artifact serialization, then records `running → cancelled`.
- **Optional soft deadline:** the user may explicitly choose *No limit* (default), 10, 30 or 60 minutes in Model Lab. The API accepts `max_duration_seconds` (60 to 14,400 seconds or null) and saves it with the experiment's version-bound config. Its deadline begins when a queued worker **actually starts**, is persisted in `experiment_run_controls`, and is examined at the same checkpoints. If time has expired the worker records `timed_out`. A single long sklearn `fit` may exceed this time; it will not be force-interrupted. **No guarantee of strict wall-clock termination.**
- **Terminal race protection:** SQLite `BEGIN IMMEDIATE` synchronizes the cancellation request and the worker's final completed state. If cancellation was requested or the deadline expired before final commit, the worker cannot mark that experiment `completed`. When a stop is observed, the worker records a clear `cancelled`/`timed_out` status, failed/empty results, and a timestamped stage event. A completed model cannot subsequently be cancelled.
- **Partial artifact cleanup:** a job writes fitted pipelines under its own generated `models/<experiment-id>` directory. If cancellation, soft timeout, storage error or restart race prevents successful finalization, the worker attempts to delete **only the new job's incomplete directory**; it never deletes previously completed experiments or uploaded datasets. An abrupt process kill during serialization may leave inert incomplete files; because the experiment status is non-completed and startup recovery marks it failed, these are not selectable. **This is not a filesystem-atomic commit guarantee.**
- **Existing safeguards:** data-version approval, leakage-safe splits, model/family hard caps, Low-memory RAM admission, one training slot, progress history, result selection constraints and strict local-only API access remain. Cloud/model availability and offline Qwen are unchanged.

## Files and focused test contract

- `backend/storage.py`: additive SQLite `experiment_run_controls` schema, `TrainingInterrupted`, `request_training_cancel`, `check_training_interruption`, `finish_interrupted_experiment`; completion checks stop requests and deadlines in one transaction. Added stage labels `cancelled` and `timed_out`; old experiment schema untouched.
- `backend/engine.py::run_training`: backward-compatible optional `stop_check` callback; checks before/after expensive CV/fit boundaries and **rethrows `InterruptedError`** rather than reporting a candidate model failed.
- `backend/main.py`: new local-only POST cancel endpoint, explicit timeout validation/persistence, callback/checkpoints in worker, cleanup of only job-owned incomplete model directory, cooperative/accurate status and control response.
- `frontend/src/api.ts` and `frontend/src/App.tsx`: optional time-limit selector, Cancel queued / Request safe cancellation action, pending/confirmed cancellation vs timeout distinctions; uses existing 1.2-second experiment polling, no extra heavy computation.
- `tests/test_p5_training_cancellation.py` synthetic SQLite tests: queued cancellation and slot release; running request stays pending until an observed checkpoint; persisted deadline; old no-timeout runs unaffected; cancellation requested during model computation; cancellation while partial artifacts saved; completed models not deleted; disk failure cleanup; sklearn interruption not swallowed; invalid timeout.
- `frontend/tests/p5-training-cancellation-contracts.test.cjs` source/contracts for persisted cancellation, temporal ordering, local API, model checkpoint, honest UI. Existing `frontend/tests/p5-training-progress-contracts.test.cjs` updated to tolerate multiline `run_training(` invocation.
- `tools/Verify_P0_A4_Readiness.py` includes the new Python module once for future full suite.
- **One owner verification only:** `Run_PilotODIN_P5_Training_Cancellation.bat` calling `tools/Verify_P5_Training_Cancellation_Local.py`, which runs **only changed** cancellation, P5 progress/slot and directly affected P1 admission Python suites; 3 P5 Node source-contract suites, and frontend `npm run build` because the App/API changed. Isolated `PILOTODIN_HOME` and synthetic data, one `pilotodin-p5-cancel-*.zip` diagnostic.

**Verification truth:** Source was committed and inspected, but no new Pytest/Node/Vite build has yet been run on the owner's Windows machine. The preceding P5 progress package was owner-accepted **18/18 Python, 7/7 Node, TypeScript/Vite PASS**. Do not present these previous numbers as verification for new cancellation/timeout functionality.

## Owner verification — 25 October 2026

The owner ran `Run_PilotODIN_P5_Training_Cancellation.bat` and uploaded `pilotodin-p5-cancel-ayag0sci.zip`. We directly extracted **all four files**, not only the screenshot. `result.json` recorded **2026-10-25T18:38:46.030809Z**, overall **PASS** with all three phase exit codes 0.

- `p5-training-cancellation-backend.log`: **45/45 Python tests PASS in 5.05s** across new cancellation and affected P5/P1 suites.
- `p5-training-cancellation-node.log`: **12/12 Node contract tests PASS**, 0 fail/skip, ~143ms.
- `frontend-typescript-vite.log`: `tsc --noEmit && vite build` **PASS**; 1,618 modules transformed, built in 3.47s. Vite displayed a **non-blocking 500 kB chunk-size warning**.
- Runner used synthetic isolated data (`original_datasets_accessed=false`) and did not rerun P0/A4, native Tauri smoke, real Qwen or the installer.

**Acceptance boundary:** P5 cooperative training cancellation/soft timeout and owned artifact cleanup have passed **focused automated Windows verification**, not native live-ML interruption stress, hard preemptive kill, general durable task orchestration, or offline 8 GB AI certification. The verifier `result.json` uses the inherited field `durable_general_scheduler_or_safe_cancellation: NOT_IMPLEMENTED`; this ambiguously combines two distinct capabilities. **Cooperative safe cancellation is implemented and tested; a general durable scheduler is not.** The verifier metadata should be corrected for subsequent runs (no need to rerun already-green checks for metadata).

**Sequencing decision:** The user's original complexity-last roadmap calls for **P3 shared deterministic semantic profiles and P4 user-chosen target intelligence before investing in heavy P5/P7 generalized scheduling**. The P5 core ML slot, factual stage history and cooperative interruption are adequate for the next deterministic product-value increment. Defer a full task queue, high-risk process preemption and AI-wide orchestration until Master modes demand them.

## Next after acceptance

A future larger P5 implementation can address durable general task queues, per-job cancellation for AI operations, stricter runtime isolation/process-based termination if desired, true deadline enforcement, retry/resume semantics and cleanup of abandoned staging directories after crashes. Those requirements need separate design, operating-system tests and acceptance.

**E2 remains UNDETERMINED:** no actual offline licensed Qwen generation and concurrent 8 GB laptop memory peak test has been completed. No model download, OS process termination, hosted GitHub Action, native installer or full P0/A4 rerun is requested for this slice.
