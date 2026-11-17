# Resource-Aware Mode — approved design and staged implementation

**Current checkpoint, 17 November 2026.** Settings displays available physical RAM and saves the resource policy. Low-memory mode screens new training at 0.75 GiB and new local inference at 2.00 GiB under the current normal policy. The isolated 1.50 GiB QA candidate deferred local inference on the physical laptop and returned local rules. The everyday Local analytics workflow has a first [physical RAM baseline](#first-physical-baseline-result). Physical offline generation and coexistence remain unverified. [Current handoff](./SESSION_HANDOFF_CURRENT.md)

## Proposed 1 GiB everyday RAM target

**Measure the installed Windows desktop app's full process tree during a defined everyday session.** The proposed target is **1,024 MiB peak app-attributable resident physical RAM** across the desktop shell, its WebView2 profile processes, the analytics backend and any worker that starts during the measured session. Record warm idle and the increase from each action as well. The app's resident usage, memory Windows has available for new work and the local AI admission floor answer different questions.

| Order | Work | Evidence needed |
| --- | --- | --- |
| 1. Establish the baseline | Reuse a verified Windows desktop build on the owner's 8 GB class laptop with a separate QA profile and generated data. Start capture before cold launch. Measure ready idle, import, project/tab switching, Quality, Explore, Ask ODIN Local analytics, ordinary export and cooldown. Include a small fixture and a representative wider, string-heavy fixture with recorded dimensions. | Build SHA, profile, fixtures, timings, per-process and whole-app peak RAM, idle and cooldown RAM, lowest system-available RAM, commit, paging and responsiveness. Keep the raw readings and sequence for comparison. |
| 2. Find and address the largest repeatable spike | Repeat the same sequence three times to identify the process and operation driving the peak. Check bounded previews and payloads, unnecessary retained copies, cache ownership or inactive views only where the measurements point. Change one hot path per comparison. | Same build configuration and workflow before and after, exact outcomes for the affected operation and repeatable improvement. Preserve project switch, draft, dataset version, export accuracy and privacy behaviour. |
| 3. Verify the target under pressure | Repeat the baseline and run a representative longer session to catch gradual growth. Agree numeric responsiveness and paging limits before treating the 1 GiB target as accepted. Keep training and bundled inference measurable as separate heavy workloads and check graceful deferral while the ordinary workspace remains usable. | Physical Windows evidence of the proposed budget under the named everyday workload and recorded handling of heavy work. Physical bundled generation and coexistence use their own R03 criteria. |

Use [the current Windows sampler](../tools/Measure_Local_Analytics_Windows_Native.ps1) to start evaluating process attribution. Match each PilotODIN-owned PID to its creation time and relevant app/profile or launched-child identity. Report private resident memory where available, summed working-set upper bound with its shared-page duplication, and private bytes as commit. If shared pages make the target ambiguous, collect a more precise trace before awarding a pass. Capture system available RAM and paging against idle for context. Compare time to a visible result and UI responsiveness alongside the measurements so paging and stalls are visible even if resident RAM decreases.

The 1.50 GiB experiment still tests the headroom needed to attempt Qwen startup. Preserve its JSONL and CSV before any rerun. The existing model and inference configuration stay fixed for a like-for-like comparison when that exercise resumes. [Physical R03 procedure and evidence](./P4_LOCAL_ANALYTICS_IMPLEMENTATION_PLAN_2026-11-15.md#r03-candidate-at-150-gib-available)

### First physical everyday RAM session

Use the extracted [PilotODIN-P4-R03-Headroom-QA kit](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44106241769/artifacts/14339122820) already used for the headroom comparison. From the updated PilotODIN checkout, open an interactive Windows PowerShell window and run:

```powershell
& .\tools\Start_P4_Everyday_RAM_Baseline.ps1 -KitDirectory "$env:USERPROFILE\Downloads\PilotODIN-P4-R03-Headroom-QA" -ArchiveExistingQaBaseline
```

Use the actual extracted folder containing both executables if it differs. Close the installed app and any running QA or PilotODIN Live Dev session beforehand. The launcher pins both executable hashes to the verified build, starts a fresh WebView2 profile and generates a four-row CSV and a 4,000-row, 28-column CSV. It stages only the two executables. With the archive switch, an existing disposable QA baseline profile is renamed to a sibling folder and its location is printed. The prior files are retained and the new baseline starts empty. The candidate profile, existing memory CSVs and the installed app's data stay in place.

Follow the prompts in the console. Press **P** after seeing the expected result, **F** to record a failure or **Q** to stop. Keep other applications in their usual state and note any visible lag or error. The timed idle and cooldown steps advance on their own. After the run, the console prints the path of `PilotODIN-Everyday-RAM-Evidence.zip`. The archive contains the build receipt, step markers, per-process rows and system/aggregate samples. It excludes app data, CSV contents and the exported report.

The first run is a diagnostic baseline. Treat missing roles or counters as gaps. Compare private resident memory as a lower bound and summed working sets as an upper bound for the observed process tree. A one-second wait between polls plus collection time can miss short peaks, and the console markers reflect owner-observed outcomes rather than precise click-to-render timing. Repeat the controlled workload before using it to assess an optimisation or the 1 GiB target.

### First physical baseline result

The owner ran the isolated build from source `8966edc` on the 8 GB laptop. The highest sampled combined working set was **706.35 MiB** during Deliver, including **487.93 MiB** in the app's WebView2 processes. Private resident memory peaked at **340 MiB** during Quality. The desktop reported responsive at all **257 app samples**, about two seconds apart. The HTML export contained the expected Quality finding. The earlier export filename check prevented the cooldown stage. This run used Local analytics with the model unloaded. [Filename verification](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44140150015/job/134240418592)

Two engine processes from an earlier QA installation were still present before the run. The desktop now opts into monitoring the pipe it owns, and the backend asks Uvicorn to shut down when that pipe closes. The frozen engine passed the standalone owner-disconnect smoke test. A rebuilt, unpackaged Windows Server 2022 QA desktop from source `acfc402` also passed both shutdown cases with its actual PyInstaller one-file engine and a separate profile. The original launcher and worker handles both signaled exit after a normal close (**211 ms**) and after killing just the desktop (**1,451 ms**). Both engine processes returned exit code 0 in the desktop-only termination case. These are single hosted observations. The run used analytics only. The initial setup failed before any compilation because of a mistyped Node action pin. The corrected run completed and the trigger was disarmed. [Windows job](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44144350648/job/134255285703) · [Engine smoke test](../desktop/verify_packaged_engine.py)

The first run's median combined WebView2 working set was **471 MiB** at ready idle, **475 MiB** while switching projects and **470 MiB** during Deliver. Median private resident WebView2 memory was **212, 199 and 171 MiB** in those same stages. The median desktop process working set rose from **29 MiB** at ready idle to **71 MiB** in Deliver. The stage combined report composition, Save As and the benchmark's filename wait. One switch sequence and a missing cooldown cannot establish long-session retention or identify the operation that caused the desktop increase.

The shell mounts the active workspace and any docked workspace. It can retain an edited docked form during a narrow-window pause and retains the prior project while the next project's data is verified. [Workspace lifetime](../frontend/src/UnifiedShell.tsx)

### Deliver binary Save As

Native Save As now sends an `ArrayBuffer` and separate filename and format headers. Rust validates the raw buffer or Tauri's byte-array fallback before opening the native dialog. The selected file is still checked for length and SHA-256 after writing. [Frontend transport](../frontend/src/api.ts) · [Native command](../frontend/src-tauri/src/lib.rs)

The hosted Windows test used a 1 MiB synthetic payload filled with byte value 255. Its deliberately invalid PDF signature ended the request before Save As opened. The binary body was **1,048,576 bytes**, compared with **4,194,354 bytes** for the same fixture in the former JSON representation, a **75% reduction in transfer size** for this fixture. The three warm binary round trips, including Rust validation, took **43.8 to 71.3 ms** in the final run. The timing excludes the dialog and disk writes. [Hosted Windows measurements](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44150811473/job/134278302684)

Source `da1caea` passed four Rust report tests on Windows. The production writer saved the raw PDF and fallback HTML byte for byte and rejected a wrong extension before writing. WebView2 opened the genuine Windows dialog with a valid PDF, and closing it returned cancellation without writing an export. WebView2 also passed the forced Tauri fallback validation check. Two earlier runs could not automate the filename field, so selecting a destination and clicking **Save** remain unverified in the optimized Windows build. The physical laptop's whole-app peak has yet to be measured with this change. [Final Windows verification](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44150811473/job/134278302684) · [Earlier dialog locator result](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44149152932/job/134272354089)

The full set of 697 frontend tests was compared with pre-change source `4070e19`. The same 47 tests fail on both sources and two report checks passed on the updated source after failing on the baseline. All 35 focused report and export checks pass.

## P1 first slice — SOURCE IMPLEMENTED, NOT YET OWNER-TESTED (25 October 2026)

The first *read-only* UI/API implementation is now committed, but **not accepted** until its focused Windows tests pass:

- `backend/resource_policy.py`: three allowed modes, Adaptive default, atomic JSON save under the current `PILOTODIN_HOME`, invalid/corrupt disk preference reporting without rewriting, physical RAM reading through Windows `GlobalMemoryStatusEx` (and Linux development fallback), unavailable readings reported as `null`. Neither OS processes nor model runtimes are enumerated or launched.
- `backend/main.py`: `GET /api/resource/status` and `PUT /api/resource/policy` with the existing local-only/desktop-session trust boundary; strict Pydantic mode validation and forbidden extraneous preference fields. Read-only status shows `policy_effect=display_only_p1_not_enforced` and `offline_8gb_ai_feasibility=NOT_TESTED`.
- `frontend/src/ResourceSettings.tsx`, placed inside existing `AISettings`: mode dropdown, explicit Save, instant available/total RAM, manual refresh, honest persistence warnings and not-yet-enforced messaging. The first slice does not modify any ML, bundled AI or quality approval workflow.
- `tests/test_p1_resource_policy.py`: isolated JSON persistence, recovery from invalid settings, fault-injected atomic write preservation, deterministic fake-memory readings, API roundtrip/local origin restrictions and input validation.
- `frontend/tests/p1-resource-settings.test.cjs`: front-end/API wiring source gates. New backend suite also added once to the consolidated runner for later regression.
- One owner check only: `Run_PilotODIN_P1_Resource_Settings.bat` calls `tools/Verify_P1_Resource_Local.py` for **only** the focused backend tests, frontend Node source gates and TypeScript/Vite build, with a single ZIP diagnostic in Temp. No P0/A4 suite, E2 scan, AI download, installer or native Save As repeat.

**Acceptance remains pending a real owner Windows run** of the new single BAT and a short glance at Settings for correct values/persistence. Do not claim RAM budgets or task scheduling work simply because a preference exists. The later P5/P7 heavy-task orchestration and actual offline E2 feasibility remain unchanged.

## P1 incremental low-memory admission — committed, Windows verification pending (25 October 2026)

Owner screenshot now confirms Settings shows **Low-memory** with a saved-success banner and RAM reading **1.09 GiB available / 7.80 GiB physical**. This is evidence of the in-app Save response, not yet proof of persistence after a full backend restart or a successful Node retest. Owner instructed us to proceed.

**New source:** `backend/resource_policy.py::admit_new_work` screens two bounded new-operation classes **only when Low-memory mode is selected**: new ML training starts require at least **0.75 GiB** available; local inference starts require **2.0 GiB** available. These values are **heuristic admission floors, not calibrated peak RAM estimates or a guarantee of safe execution**. A missing memory reading **defers new work in Low-memory**. Adaptive and Performance retain the existing engine and privacy hard limits and do not claim this new enforcement. No running job is interrupted or killed, no Windows processes stopped, no source data changed. Durable task queue, parallelism control, cancellation and task scheduling remain P5.

**Training integration:** `backend/main.py::new_experiment` calls the new admission policy **after** existing split/leakage/candidate resource validations but **before** `storage.new_experiment` or `background_tasks.add_task`. When refused, it returns HTTP **503** with a machine-readable `retryable=true` and current/required RAM, rather than silently creating an experiment that never trains. Existing models and report/evaluation retrieval paths are not affected.

**Local AI integration:** `backend/ai_provider.py::local_try` screens available RAM before any Ollama or bundled inference request and can use deterministic rules as fallback with `local_status=resource_limited`. Importantly, the native desktop frontend's `frontend/src/api.ts::requestLocalAI` can invoke the Rust model launcher *before* Python sees the request, so it now obtains a local-session-authenticated, read-only `GET /api/resource/preflight?operation=local_inference` and skips `invoke('launch_bundled_ai')` if deferred or preflight is unavailable. Existing cloud consent handling is unchanged. No AI model is downloaded, loaded or benchmarked by this code change itself.

**Settings UI wording updated** to display actual low-memory start screening and the two numerical screening floors. It explicitly says this is *not* peak memory certification or a durable scheduler. `status().policy_effect` now correctly reports `low_memory_new_work_preflight_only_no_scheduler` rather than `display_only_p1_not_enforced`. The original 10 deterministic resource settings tests are updated; new `tests/test_p1_resource_admission.py` covers mock RAM floors, unknown RAM, no ghost ML experiment/background job, allowed start after existing ML validations, unchanged Adaptive/Performance safeguards, and deterministic AI fallback without actually calling a model. Node source tests additionally assert FastAPI and Tauri preflight order. Both backend test modules run in the existing focused `Run_PilotODIN_P1_Resource_Settings.bat` runner and are included once in future comprehensive regressions.

**Acceptance NOT YET DONE:** Updated source was committed and GitHub-fetched/reviewed, but no Windows Pytest, Node source gates, TypeScript/Vite build or native low-memory runtime smoke has run against this increment. The actual physical **8 GB combined PilotODIN+Qwen/ML** feasibility remains `UNDETERMINED`; refusing model startup under low free memory is a safety measure, **not a successful offline Qwen test**.

**Owner's only upcoming action:** pull active branch, run `Run_PilotODIN_P1_Resource_Settings.bat` once, upload generated ZIP only if red. If green, check the existing Low-memory Settings state and one low-memory planning message in the normal app, without importing/retraining the insurance dataset or launching Qwen on this constrained laptop.

## Problem and measured baseline

The owner's Windows machine has 7.804 GiB visible physical RAM. E2 read-only measurements observed **0.572 GiB free** with RAID/Steam/Chrome/ChatGPT etc active, then **1.019 GiB free** after closing RAID. This does **not** measure simultaneous local-Qwen generation + analytics or prove model viability. Memory pressure varies with other applications. Do not attribute all used RAM to PilotODIN or assume a GGUF file's disk size equals peak RAM use.

## Resource policy — proposed user-facing behavior

- **Adaptive (default):** Recheck Windows available physical memory, concurrent PilotODIN workloads and explicit per-operation estimates immediately before heavy work. Permit or defer bounded operations based on actual headroom. Don't claim a fixed threshold is a guaranteed memory fit.
- **Low-memory:** Prioritize deterministic Explore, Quality and reports; minimize caches, keep local LLM unloaded except an explicitly requested brief inference run when preflight is safe, and serialize expensive ML/inference tasks. Always preserve ongoing unsaved work and immutable originals.
- **Performance:** Allow greater throughput only within validated hard resource budgets and operation-specific constraints. **Never bypass integrity/security/prediction/leakage or memory ceilings** because the user chose Performance.

Any automatic low-memory recommendation must be **explainable and overridable only within hard safeguards**. Consider detected physical RAM and *currently available* headroom, not total RAM alone. Report “not measured” rather than invented peak usage or precision.

## Phased implementation aligned with P0–P8

1. **P1 — read-only status and policy persistence:** Implement narrowly scoped platform metrics (physical/available RAM, PilotODIN-owned processes and bounded task queue metadata) and a persistent per-device setting for the three modes. Distinguish observed vs estimated. Do **not** enumerate/terminate unrelated applications or collect unrelated process command lines.
2. **P1/P5 — truthful heavy-operation preflight and serialization:** Centralize resource estimates and deny/defer new local ML/inference work when memory is insufficient; run one expensive task at a time in Low-memory mode. Provide clear reason, suggested safe action and retry. Do not discard running work, change source data, auto-approve Quality fixes or silently modify a selected prediction target. Add version-sensitive and cancellation regression tests.
3. **Early E2 feasibility checkpoint — *separate acceptance*:** Choose a specifically licensed, quantized local model and supported Windows inference runtime, measure real model loading/inference, peak joint RAM/paging/responsiveness while concurrently operating PilotODIN, including a disconnected-network run on real 8 GB hardware. **Undetermined** until measured. The owner's current E2 scans are hardware inventory, not a PASS.
4. **P5/P7 — actual AI lifecycle integration only after E2:** Lazy-load the local LLM, use a small bounded context and one active generation by default, unload after use through the selected runtime's supported controls, and enforce timeout/resource budgets. Deterministic analytics continue without AI. A model refusal/error must not corrupt tasks or freeze reports.
5. **P8 — integrated release certification:** Standalone installation/offline launch and real 8 GB joint load plus original Build E E-01–E-24. Prove graceful degradation and usable fallbacks when inference is unavailable.

## Hard invariants

- Never disable Windows pagefile, memory compression, antivirus or services; never kill unrelated apps.
- Never circumvent import size restrictions, SQL/data access boundaries, data-source immutability, human Quality approvals, ML leakage/split guards, cross-project isolation or legitimate operation caps.
- Do not automatically download models or transmit datasets to external AI services. An AI model's optional availability is not an unconditional PilotODIN startup dependency.
- Never present a lower CPU/RAM footprint as verified without before/after measurements on the target Windows hardware.

## Acceptance criteria for first P1 slice

- Three modes can be selected and restored after a normal application restart, with Adaptive as the default; no mode can suppress hard integrity/resource limits.
- Read-only physical/available RAM is correctly measured or explicitly “unavailable”; monitor does not leak unrelated process names, command lines or private data.
- A deliberately simulated low-headroom heavy task is **blocked/deferred before task execution**, without creating an experiment artifact, mutating data or dropping the existing UI session; show a clear explanation.
- Mode and preflight decisions are unit/integration tested with fake resource observations, so tests do not depend on fluctuating Windows memory.
- One owner Windows smoke test after a coherent code batch; do not require multiple round trips, new Qwen installations or repeated native A4 export.
- E2 offline/8 GB remains “not certified” until actual offline inference and concurrent peak-load evidence is present.

## Non-goals of this decision

This approval is for **a staged resource management feature**, not approval to build an autonomous model scheduler, install Qwen, make unsafe memory tweaks, modify user project files or claim the 8 GB compatibility requirement has been met.
