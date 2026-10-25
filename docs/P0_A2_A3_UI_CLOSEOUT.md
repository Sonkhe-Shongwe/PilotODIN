# P0 A2/A3 — one-session interface closeout (Windows development)

Status: acceptance procedure prepared. Latest UI request-guard source and its regression checks have NOT been executed on the owner's Windows machine. This is not an installer, offline-inference, physical 8 GB, or browser end-to-end certification.

## Preconditions
- Pull the latest active feature branch once, without discarding local changes.
- Use the existing local PilotODIN Live Dev backend and frontend at 127.0.0.1:5173, or the already-confirmed native development window if it is running.
- Use the existing insurance_claims_CLEANED project and previously saved experiments, Explore analyses and reports. Do NOT reimport, retrain, or modify the original insurance data to complete these checks.
- Source-level backend ML lifecycle, version, prediction-domain, project isolation and report revision invariants have separate automated regressions.

## Minimal owner UI journey

| Gate | Action | Evidence of correct behavior |
| --- | --- | --- |
| P0-UI-1: Project isolation | Select insurance_claims_CLEANED using the global project menu. Open a different existing project if available, then return. | Histories, current model selection and predictions never leak into the other project's workspace; original history is available on return. Skip alternate project switch if none exists. |
| P0-UI-2: A3 Evaluate-first reopen | From Home recent work or Evaluate, open a saved completed and selected experiment. | Opens at Evaluate, not directly at Predict; selected model and frozen held-out metrics return. The existing insurance example retains 82% held-out accuracy and published limitations. |
| P0-UI-3: A3 prediction validity | Open Predict for an existing selected model. If the real insurance incident hour field is available, enter 25. | Invalid hour is rejected without a new valid prediction result. Negative/fractional vehicle counts and missing/unseen warnings already have separate automated coverage. |
| P0-UI-4: Saved Explore restore | Explore → Saved analyses and evidence → Open an item labelled Current verified version. | Frozen snapshot, original checksum and verified chart settings display. Live chart aggregation, axes and filters restore and are independently recomputed. |
| P0-UI-5: Historical read-only | Only if an existing historical verified saved Explore item is present, Open it. | Frozen older evidence is readable, but its settings are not applied to the current working data. Skip if no such item exists—do not approve quality changes merely to manufacture a manual case. |

## What not to repeat
- The owner already confirmed native Tauri PDF Save As, HTML Save As and Cancel-with-no-write. Do not retest that unchanged milestone.
- Do not run the whole A2/A3/A4 suite after every minor code commit. Run one consolidated gate at the next coherent checkpoint.
- No installer, model GGUF staging, hosted Actions, or fresh application-data writes are prerequisites for this UI session.

## Acceptance decision
Record which required gates were actually observed and any skipped gates with a reason. Static source contracts are NOT proof of Windows interaction. Keep P0 open for confirmed failures and until one consolidated post-change automated run is green.

## Source references
- frontend/src/App.tsx: Evaluate-first saved experiment reopening; project request epoch guards
- frontend/src/UnifiedShell.tsx: per-project tabs and workspace keys
- frontend/src/SavedExploreAnalyses.tsx: project and version request-epoch guards on listing, Save and Open; historical snapshots remain read-only
- frontend/tests/saved-explore-analyses.test.cjs, frontend/tests/project-operation-guard.test.cjs, frontend/tests/ml-a3-heldout-ood.test.cjs
- tests/test_p0_ml_persistence_version_journey.py, tests/test_saved_explore_analyses.py, tests/test_build_e_persistent_reports.py

This document defines the acceptance checks; it does not claim the newest frontend change has been executed on owner Windows.
