# PilotODIN 1.0 | P4-08 Human Target Suitability Review and Abstention

**Date:** 9 November 2026  
**Active branch:** `feature/live-dev-workspace-20261023`  
**Source SHA:** [`75ed74918a9216584bcedfaa4d6e41e947000a6a`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/75ed74918a9216584bcedfaa4d6e41e947000a6a)  
**Phase status:** P4 ACTIVE; P1/P2/P3 CLOSED for bounded development; P8 NOT CERTIFIED.

## Problem, authorised scope, and what is preserved

P4-01 through P4-07 previously implemented read-only technical screening, bounded rank for a *human review queue*, user-described version-specific business context, source/timing questions, alternative review parity and repeated identifier-like evidence. That work is preserved.

Previously the candidate cards offered only **Review this target**, even if the user intended to defer or reject that particular prediction objective. Once a target was selected, there was no direct candidate-specific decision to clear stale preparation. Manual target choices outside the bounded recommendation queue also lacked a concise statement that they had not been screened. P4-08 adds **an explicit local review workflow**, not a new persisted approval process or independent business verification.

## Implemented behaviour

1. **Temporary candidate-level disposition:** each reviewable shortlist and alternative candidate has separate `Defer target in this review` and `Decline target in this review` actions, marked clearly as *not saved*. These are local view dispositions only. They neither change the backend's deterministic ranking nor permanently exclude a target; the owner may reselect it using the accepted explicit controls.
2. **Safe deselection:** If the candidate being deferred/declined is currently chosen, `onClearTarget` calls the existing Prepare state invalidation pattern in `App.tsx`: clear `target`, `prep`, current `experiment` view, confirmation of random split, and stale error. The clear action reports an edited Prepare draft to the existing primary unsaved-draft mechanism. Clearing an already-empty target is a no-op. Saved experiments/history in SQLite are not deleted.
3. **No predictive objective:** explicit `No prediction objective right now` deselects any current target and provides a visible, reversible informational state. It never commits a permanent rejection, and the user may still choose another target manually.
4. **Selected-target suitability checkpoint:** the Prepare recommendation component shows an immediately visible read-only checkpoint when a target has been chosen. A currently recommended target includes bounded label support, missing counts and unverified decision/timing/grouping caveats; a manually chosen target outside the top 3+12 candidacy queue explicitly shows that no P4 suitability evidence is established. This is **not** an ML training approval, legal/ethical clearance, or new automatic safety score.
5. **Project/version isolation:** temporary dispositions live in the keyed `TargetOpportunities` component instance (`project.id+'-'+qualityVersion`). No localStorage/sessionStorage write, SQL mutation, extra backend endpoint, AI call, model fitting, new dependency, native code or installer. Existing normal Prepare/Model Lab guards remain responsible for experiments; local UI deferral is not a security permission gate.

## Verified automated evidence at exact application commit

- [P4 targeted CI #42591576526](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42591576526): **COMPLETED SUCCESS** at `75ed74918a9216584bcedfaa4d6e41e947000a6a`. Job logs show **42/42 Python**, **20/20 Node source contracts**, TypeScript/Vite production build **PASS**, **2/2 actual isolated Chromium + Uvicorn/SQLite real-HTTP browser tests PASS**.
- The existing P4 browser review test now checks selection of a lower-ranked alternative, the selected-target checkpoint, deferral clearing the actual manual dropdown, explicit re-selection, decline clearing selection, manual selection outside the bounded queue with conservative warning, manual clear, global abstention, zero unexpected API mutations and zero experiments created. The second browser scenario still tests explicit local context save, refresh and unverified owner-text status, not automatic training.
- [P1 frontend #42591576550](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42591576550): **COMPLETED SUCCESS**, same exact SHA, **160/160 Node source contracts**, production frontend build, **5/5 isolated browser scenarios**.
- [P2 report-export-draft-safety #42591576545](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42591576545): **COMPLETED SUCCESS**, same exact SHA. No P2 product feature or report data changed.
- All backend dataset operations in the browser tests used synthetic 80-row CSV fixtures and CI-isolated `PILOTODIN_HOME`; no actual owner project or installed Windows app was opened.

## Limits and acceptance decision

**P4-08 SCOPED DEVELOPMENT ACCEPTED** based on completed code/build and disposable real-HTTP browser evidence only. Deferral/decline is *temporary*; it cannot be interpreted as a persisted audit decision, a policy constraint or a new server-side training restriction. A manual choice remains possible and still passes through existing Model Lab scientific checks. No independently verified business meaning, label provenance, prediction timing or group identity was created. This is not physical Windows/Tauri native acceptance, full P4 owner closure, E2 offline 8 GB/Qwen proof or P8 release certification.

**Next:** reconcile the remaining P4-specific phase-exit criteria and risk/negative-case matrix, particularly no credible target, rare event outcomes, regression, repeated entities and Quality version changes, then assess whether targeted native owner evidence is indispensable before requesting separate P4 closure approval. Do not automatically start P5.
