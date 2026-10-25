# P5 First Slice — Low-memory ML coordination and restart recovery

**25 October 2026 — implementation committed; owner Windows execution PENDING.**  
Source: `backend/storage.py`, `backend/main.py`, `tests/test_p5_ml_training_slot.py`.  
**One-click acceptance:** `Run_PilotODIN_P5_ML_Coordination.bat` from GitHub Desktop clone root.

## Design decision and narrow scope

The current FastAPI implementation creates a `queued` experiment and runs training through a `BackgroundTasks` worker; before this change multiple requests could start expensive independent runs even with Low-memory mode selected. A process restart could leave experiments indefinitely `queued` or `running` while no worker existed. No durable task queue or generic scheduler currently exists.

This slice implements a **single global training slot only while Low-memory policy is selected**, and robust compare-and-set ML status transitions. This is intentionally **defer/refuse on busy**; it does **not** claim to persist an autonomous queue or resume a model job.

### Exact behavior

1. Existing data-version, target, split/leakage, selected-model and resource-cap validations run **before** admission. Low-memory's 0.75 GiB available-memory screening floor remains in place. Adaptive/Performance maintain their earlier hard ML and data-integrity limits.
2. A low-memory new experiment reservation uses `storage.new_experiment_with_capacity` with SQLite `BEGIN IMMEDIATE` and rejects if any experiment across projects is `queued` or `running`. The presence check and inserted `queued` record happen in **one write transaction**, not a race-prone Python thread lock.
3. The busy path returns **HTTP 503**, machine-readable `ml_training_slot_busy`, `retryable=true` and an understandable message. **No new experiment record or background task is created.** Existing work continues unaffected.
4. A worker atomically transitions **queued → running** only once. It may finalize **running → completed/failed** only while still running. A late completion cannot overwrite failed/interrupted work. Existing saved model selection and completed results remain immutable.
5. On an ordinary fresh FastAPI backend startup, any abandoned `queued`/`running` ML experiments are marked **failed**, with `Training interrupted by application restart` and no finalized result. Existing completed/failed experiments are unchanged, and the next attempt must be explicitly initiated again. This is **single-user single-backend-process recovery**; the application must not run two independent sidecars pointing at the same SQLite database simultaneously.
6. This feature **does not** start, download, serialize or benchmark local Qwen. General durable P5 task orchestration, progress events, user-facing cancellation, queued retry and AI-wide concurrency remain subsequent increments. The real 8 GB/offline E2 milestone remains **UNDETERMINED**.

### Tests added

`tests/test_p5_ml_training_slot.py` uses fresh SQLite in Pytest `tmp_path` and synthetic tabular data only. Covers single slot across projects, **8 simultaneous competing reservations with exactly one winner**, queued→running compare-and-set, terminal/late-writer safety, startup recovery without changing completed results, failure release of slot, no worker resurrection, Low-memory API 503 with no phantom experiment or scheduled task, Adaptive's preserved earlier multi-request behavior, terminal-status validation.

Updated `tests/test_p1_resource_admission.py` to adapt its synthetic storage mock to the new atomic allocator. New `frontend/tests/p5-ml-training-slot-contracts.test.cjs` statically enforces transaction/status/API order. A future consolidated P0/A4 backend runner includes the new suite exactly once.

### One owner verification, no redundant tests

1. **Pull active branch `feature/live-dev-workspace-20261023` once.** If GitHub Desktop shows uncommitted changes, inspect and preserve them; never discard generated files blindly.
2. Double-click **`Run_PilotODIN_P5_ML_Coordination.bat`**. It runs ONLY P5 backend regressions plus the earlier P1-admission suite whose training-storage fake needed updating, then the three focused Node source contract tests; no TypeScript/Vite build because no frontend application sources changed in this increment.
3. It reports PASS/FAIL and writes ONE `pilotodin-p5-slot-*.zip` under Temp with logs and `result.json`. Upload this ZIP **only on failure** for targeted correction.
4. Do not reimport or retrain insurance data, redo P0/A4 native export, rescan Windows memory, start an AI model or create a release installer for this milestone.

**Evidence limit:** GitHub commits and source re-fetches establish changes, not Windows execution. Keep P5 acceptance **PENDING** until owner runs the focused test. Do not describe SQLite transaction tests as a distributed durable queue; actual long-running resume/cancellation and cross-model scheduling remain future work.
