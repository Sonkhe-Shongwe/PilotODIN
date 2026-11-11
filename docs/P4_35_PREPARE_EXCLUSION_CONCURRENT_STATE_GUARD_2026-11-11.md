# PilotODIN 1.0 | P4-35 Prepare high-risk exclusion state preservation

**Date:** 11 November 2026. **Scope:** Source-only P4 Prepare safety regression and exact-source CI. **No new installer, owner filesystem access, source model training or new phase.**

## Audited finding: historical issue text partly stale

Master QA Issue #2 / BE-024 originally described the Apply suggestions button as replacing manually selected feature exclusions and raised other usability and preprocessing concerns. Inspection of current source at `97ecaa98549f307e965fa3e2a4b6b80294602860` established the replacement behaviour had **already been corrected**: the button used `[...new Set([...excluded,...proposed])]` and included an `INCLUDED PREDICTORS` metric and high-risk review warnings. Do not report that old replacement bug as newly discovered or unfixed.

However, the button still called `setExcluded(next)` using an **array captured by the handler's React render**. If a more recent manual checkbox edit is pending in the current state before the handler's captured value is refreshed, a value-only setter can discard that new manual choice. This is a **source-confirmed stale-state vulnerability**, validated in an isolated handler harness, not an observed owner-native field failure. The existing A3 contract also expected a functional updater, but wasn't exercised by the focused P4 workflow.

## Bounded source fix

[Source commit `5cda74311a25cc78b4324c50e7ccd1d61553b6b9`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5cda74311a25cc78b4324c50e7ccd1d61553b6b9) changes:

- `frontend/src/App.tsx`: preserve no-op detection and primary edit marker; apply only genuinely new high-risk proposals with `setExcluded(current => [...new Set([...current, ...additions])])` against **current** React exclusion state. A pending manual checkbox choice is retained, never silently overwritten by the action.
- `frontend/tests/p1-primary-button-edit-markers.test.cjs`: adjust live-handler simulation to correctly execute functional React state updaters; test late manual checkbox addition absent from handler's closure alongside existing no-op, primary/docked and model-toggle tests.
- `.github/workflows/p4-target-ranking.yml`: run both the existing A3 Prepare source contract and live P1 handler test in the focused P4 Node step, and trigger P4 CI when their tests or `App.tsx` change. **The workflow performs only Python/Node/Vite, isolated browser and synthetic Windows checks**, with no native packaging or downloads of models.

No production backend training endpoint, preprocessing policy, project database, model runtime, original application or owner data touched. The other BE-024 items, including configurable per-feature transformations and visual previews, are **not implemented/accepted** by this fix.

## Verification

At exact application source `5cda743`:

| GitHub Actions result | Verified scope |
| --- | --- |
| [P4 #43077912100](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43077912100): **COMPLETED SUCCESS 3/3 jobs** | Focused Python and Node, live-handler stale-state regression and A3 contract, TS/Vite, disposable real-HTTP Chromium, Windows-2022 synthetic integrity and PowerShell 5.1 |
| [P1 #43077911841](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43077911841): **COMPLETED SUCCESS** | Source contract, production frontend build and isolated browser regression |
| [P2 #43077911822](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43077911822): **COMPLETED SUCCESS** | Adjacent report async safety contract and frontend build |
| Owner physical Windows current-source Prepare UI | **NOT RETESTED**, installer freeze applies | Synthetic tests do not prove installed native UI parity |

No new installer was built, downloaded or run. Existing source-branch installer workflows remain guarded `if: ${{ false }}` and should not be re-enabled until an explicitly owner-authorised **final** P8 stage.

## Unchanged acceptance boundaries

Original independent backup and installed production EXE matched baseline; source-defined original critical project `data/` subtree 0 detected changes. But **complete original application data-directory strict integrity remains FAIL** (320 baseline vs 346 current files, 74 WebView/cache candidates, historical writer UNKNOWN). This source fix cannot identify cache writers, waive failed preservation or certify user Windows 8 GB/offline operation. Real operational business Gate C is UNVERIFIED, and P4-R01–R06 remain open.

**Disposition:** P4-35 SOURCE FIXED, exact-source CI PASS, owner-native UI **NOT RETESTED**. P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED. No more intermediate installers.
