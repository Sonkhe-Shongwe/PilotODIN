# PilotODIN 1.0 — one-primary-phase development and closure policy

> **CURRENT POLICY, 4 November audit annotation:** P1 remains the one primary phase. The **“Current active assignment and handoff” paragraph at this document's end is its 28 October checkpoint**, not today's exact next step. Consult [current P1 closure matrix](./P1_CLOSURE_REGISTER_2026-10-28.md) and [current handoff](./SESSION_HANDOFF_CURRENT.md). The normative closure rules below are unchanged.

**Adopted by owner:** 28 October 2026. **Current primary phase: P1.**
**Authoritative branch:** `feature/live-dev-workspace-20261023`.
**Authority:** Owner's revised execution preference. This decision supersedes earlier *active priority* sequencing notes in historical roadmap and status reflections, **but does not invalidate their technical evidence or phase dependencies**.

## Operating rule

One primary implementation and acceptance phase at a time. Complete P1 to an explicitly documented, defensible closure state before scheduling discretionary P2–P8 feature work. Phase selection is not permission to conceal unresolved risks. Avoid scattering incremental polish across phases, and avoid endless new test scenarios in place of finishing complete product journeys.

An indicative **90–95%** phase-completeness target may guide planning but **is never an acceptance criterion**. The earlier P1 `~75%` and overall `~45%` figures were qualitative estimates, not audited earned-value measurements. Do not turn them into tracked KPI progress without an explicit, weighted requirement inventory. Prefer **accepted / blocked / open / deferred by approved dependency** per requirement.

## Exit criteria for the active phase

A phase can be recorded **CLOSED (development scope)** only when:

1. A frozen scope/requirement matrix names what the phase must do and maps every critical scenario to evidence.
2. No open **critical/high** in-scope safety, data-loss, correctness or security defect remains. Medium/low residuals require documented impact, owner approval for deferral and a follow-up owner.
3. Essential user journeys pass **real frontend/browser and Windows/native checks where the requirement depends on them**; source-only/Node tests, mock-only Playwright and previous-revision builds are never silently substituted.
4. The changed code passes the narrow affected contract tests and the build; a release/integration gate is only claimed with its own observed execution.
5. Durable data, project separation, cancel-before-mutation, consent and failure rollback are preserved. No owner dataset is used for destructive discovery; use disposable synthetic fixtures.
6. QA Issue #2 and both authoritative handoffs record the outcome, exact branch SHA, tests actually run, unresolved risks and next planned phase.

A phase is **BLOCKED** if essential validation depends on missing hardware, licence, source, native runtime, accessibility proof or authorization. A blocked phase is **not** automatically '95% complete'; name the dependency and choose the smallest safe unblocking activity. Freezing development does not freeze emergency security/data-loss fixes.

## Explicitly permitted exceptions

- **Critical feasibility only:** Bounded, read-only or owner-approved investigation of the true offline 8 GB local AI + ML coexistence risk and release licensing, early enough to prevent architecture rework. No new P6/P7 feature implementation under this exception.
- **Critical cross-phase dependency:** An essential P1 test or safety fix requires a contained change outside P1. Explain the dependency first, limit the diff, and return to P1.
- **Safety/regression:** An observed critical/high data-loss, privacy, security or application integrity problem in an otherwise accepted phase. Fix it using the same narrow QA/rollback rules.

Do not use a convenience improvement, attractive UI polish, unrelated exploratory research, routine refactor or speculative benchmark to invoke an exception.

## Work cycle

**Select one requirement → inspect existing source and evidence → implement one bounded change → add focused tests → validate without assuming a pass → commit → update handoffs/Issue #2 → obtain needed owner Windows evidence → record acceptance or real failure → continue the same P1 requirement family until closed.**

Do not rerun previously accepted suites on unchanged code. Do not infer clean offline release readiness from synthetic React tests. Do not overwrite owner-generated npm/Cargo lockfiles, local working changes, datasets or Tauri generated schemas. Do not launch installers, model downloads, paid services or GitHub Actions without explicit necessity and applicable approval.

## Current active assignment and handoff

- **Primary:** P1 — safe project/workspace and Quality life cycle, responsive/native workflows, unsaved forms and cross-tab/reload resilience. Its accepted subsets are recorded in [P1 Closure Register](./P1_CLOSURE_REGISTER_2026-10-28.md).
- **Immediate next slice:** Primary Studio-owned **unsaved Prepare/Model form** changes during an attempted project switch; demonstrate safe Cancel and preserve the current project/form before extending to reload/cross-tab.
- **Next after P1 closure:** P2 Deliver, PDF Unicode rendering and independent OFL/font packaging approval. Then resume remaining phases in prerequisite-aware, complexity-ascending order rather than opportunistically switching.
- **Late gates not waived:** Real 8 GB AI/ML, P6/P7 deterministic/autonomous workflows and P8 self-contained offline clean Windows installer and E-01–E-24 acceptance.

References: [Consolidated Roadmap](./PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md) · [Phase Reflection](./PILOTODIN_STATUS_REFLECTION_2026-10-26.md) · [Current Handoff](./SESSION_HANDOFF_CURRENT.md) · [Issue #2](https://github.com/Sonkhe-Shongwe/PilotODIN/issues/2).
