# P5 — Durable, factual ML training progress

**25 October 2026: source and focused tests committed; owner Windows acceptance pending.**
**Prior accepted P5 scope:** SQLite Low-memory single training slot and restart recovery, **25/25 backend + 3/3 frontend source-contract tests PASS** from uploaded owner ZIP `pilotodin-p5-slot-izx59pft.zip`. Do not rerun those unchanged acceptances reflexively.

## What the next slice adds

**One experiment ID; actual persisted work stages, not estimated percentages.** This is an additive, backwards-compatible progress ledger for ML training only. No generic operations platform, model cancellation/resume, AI model loading or final-release claim.

`backend/storage.py::init` creates `experiment_progress_events` in SQLite with an index. The existing `experiments` schema is **not rewritten**, so legacy persisted models/data and selection columns remain intact. A new experiment records `queued` atomically with the initial experiment insert, under both ordinary and Low-memory capacity paths. The worker's existing compare-and-set queued→running records `loading_data` once; it records `training_models` after loading the saved dataset version but **before** invoking the existing cross-validation/model fit; after the engine returns, it records `saving_artifacts` before writing model files; terminal completed/failed and backend-startup interruptions record their actual outcomes. SQLite transactions couple lifecycle changes with each event.

A new `advance_running_experiment(eid,stage,detail)` rejects invalid, repeated, reversed or terminal-stage updates. If the backend already declared a job interrupted, a stale worker cannot write new stages or legitimately complete it. **No estimate of percent, ETA, individual model fold position or resource peak** is invented.

`storage.get_experiment` returns an additive `progress` with `stage`, human-readable `label`/`detail`, `updated_at`, `history` and `history_available`. An older experiment **without** events returns an explicit historical fallback; it is *not* assigned invented development/training milestones. `GET /api/experiments/{id}` includes that object, retaining every previous metric/results/selection field.

In `frontend/src/App.tsx`, existing per-experiment `GET` polling (about every 1.2 s) already checks active project, generation and experiment IDs. The Evaluate panel now shows **latest observed stage**, actual stage history when recorded, and a clear note that stages are not percentage-complete guesses. Failed operations show their reason and recorded last event. No separate polling loop/worker is introduced, and the successful evaluation/prediction/report layouts remain unchanged.

## Tests and scope

- `tests/test_p5_training_progress.py` covers SQLite persistence, atomic events for both admission paths, monotonically increasing stage order, terminal-write protection, old experiments without synthetic history, idempotent schema setup, genuine restart-interruption history without touching completed results, experiment API visibility, work-stage timing using stubbed training/saving (no actual model training), error stage propagation and stale-worker refusal.
- `frontend/tests/p5-training-progress-contracts.test.cjs` guards stage persistence, worker operation ordering, frontend contract/polling and no fabricated percent.
- `tools/Verify_P0_A4_Readiness.py` includes the new backend suite **once** for an eventual comprehensive regression.
- **Single focused owner runner:** `Run_PilotODIN_P5_Training_Progress.bat`, calling `tools/Verify_P5_Training_Progress_Local.py`. Runs only `tests/test_p5_training_progress.py`, changed-storage dependent `tests/test_p5_ml_training_slot.py`, both focused P5 Node source contract suites, and the TypeScript/Vite build because the frontend changed. Uses an isolated `PILOTODIN_HOME` and per-test SQLite fixtures; writes one `pilotodin-p5-progress-*.zip` diagnostic under Windows Temp.

**No owner Windows execution of this new milestone has happened yet.** Source review is not a test PASS. Do not request the already-green 25/3 standalone P5 suite independently, the P1 27/5 suites, previous A2/A3/A4 checks, Qwen downloads, native Save As or a new 8 GB inventory. One focused test should be sufficient unless a real regression appears.

## Future P5 and E2 boundaries

The extension does **not** implement user cancellation, retry/resume, a durable multi-operation queue, automatic progress percentages, cross-Qwen concurrency, general scheduler or verified native running ML stress. An interrupted job is failed honestly; restarting training remains an explicit user action. The existing single-backend-per-workspace requirement and hard ML validation/capacity guards remain.

**Actual licensed local Qwen inference disconnected from the network with a concurrent PilotODIN workload on real 8 GB hardware: E2 UNDETERMINED.** No model was loaded or tested here. P8 installer/release verification remains pending.

**Next after green owner gate:** consider a bounded cancellation/timeout contract and a broader durable operation ledger only after reviewing the existing approved dataset/version and worker cleanup invariants.
