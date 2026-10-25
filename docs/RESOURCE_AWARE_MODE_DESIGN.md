# Resource-Aware Mode — approved design direction, not yet implemented

**Decision recorded 25 October 2026.** The owner agreed to pursue PilotODIN-managed resource constraints instead of treating an 8 GB Windows machine as requiring unsafe removal of system limits. This document is the scoped implementation proposal; **no runtime Resource-Aware Mode is currently shipped**.

## P1 first slice — SOURCE IMPLEMENTED, NOT YET OWNER-TESTED (25 October 2026)

The first *read-only* UI/API implementation is now committed, but **not accepted** until its focused Windows tests pass:

- `backend/resource_policy.py`: three allowed modes, Adaptive default, atomic JSON save under the current `PILOTODIN_HOME`, invalid/corrupt disk preference reporting without rewriting, physical RAM reading through Windows `GlobalMemoryStatusEx` (and Linux development fallback), unavailable readings reported as `null`. Neither OS processes nor model runtimes are enumerated or launched.
- `backend/main.py`: `GET /api/resource/status` and `PUT /api/resource/policy` with the existing local-only/desktop-session trust boundary; strict Pydantic mode validation and forbidden extraneous preference fields. Read-only status shows `policy_effect=display_only_p1_not_enforced` and `offline_8gb_ai_feasibility=NOT_TESTED`.
- `frontend/src/ResourceSettings.tsx`, placed inside existing `AISettings`: mode dropdown, explicit Save, instant available/total RAM, manual refresh, honest persistence warnings and not-yet-enforced messaging. The first slice does not modify any ML, bundled AI or quality approval workflow.
- `tests/test_p1_resource_policy.py`: isolated JSON persistence, recovery from invalid settings, fault-injected atomic write preservation, deterministic fake-memory readings, API roundtrip/local origin restrictions and input validation.
- `frontend/tests/p1-resource-settings.test.cjs`: front-end/API wiring source gates. New backend suite also added once to the consolidated runner for later regression.
- One owner check only: `Run_PilotODIN_P1_Resource_Settings.bat` calls `tools/Verify_P1_Resource_Local.py` for **only** the focused backend tests, frontend Node source gates and TypeScript/Vite build, with a single ZIP diagnostic in Temp. No P0/A4 suite, E2 scan, AI download, installer or native Save As repeat.

**Acceptance remains pending a real owner Windows run** of the new single BAT and a short glance at Settings for correct values/persistence. Do not claim RAM budgets or task scheduling work simply because a preference exists. The later P5/P7 heavy-task orchestration and actual offline E2 feasibility remain unchanged.

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
