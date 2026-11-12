# PilotODIN P4-74 | Real-HTTP Prepare feature-audit and revision provenance regression

**Date:** 12 November 2026. **Scope:** a single existing read-only/scoped synthetic real-HTTP Chromium test expansion, no PilotODIN product source changes, no model fitting, no installer, no new native executable, no original data access.

## Source-verified gap and test change

Existing [P4-62](../frontend/e2e/p4-real-http-review-queue.spec.ts) disposable-browser acceptance checked additive high-risk exclusions but **did not assert the per-field Prepare audit table and both version-pinned read-only response contracts** during the same manual-exclusion journey. The current BE-024 public acceptance gap includes understandable per-column treatments and included predictor counts, and P4-64's cross-revision semantics must remain 409 for stale requests.

P4-74 extends **the same 80-row synthetic project** within that existing test. Before mutating any temporary checkbox, it asserts that both `/preparation?target=churn&expected_version=0` and `/features?target=churn&expected_version=0` respond with matching version/target and mark `TransactionID` high-risk; `expected_version=1` returns **409** from both read-only endpoints. It checks the actual browser audit's field-specific risk and mode/median treatments, that a manual `event_type` exclusion changes only its audit row to `Excluded by user / No training transform`, and that the subsequent explicit reviewed suggestion additionally excludes `TransactionID` while leaving `amount` included. Afterward, it verifies **3 candidate predictors / 1 currently included / 0 unresolved high-risk** in the actual page. The existing no-experiment-record assertion remains mandatory.

**Not a preprocessing alternative control:** This tests the *existing* read-only strategy and choices, not per-field alternative configuration, training outcome, external Gate C or native UI parity. No existing gate is certified simply by making an assertion.

## Governance and execution boundaries

The test is run only under the existing GitHub-hosted disposable `CI/GITHUB_ACTIONS/P1_REAL_HTTP_E2E/PILOTODIN_HOME` guard, with the existing synthetic 80-row CSV and isolated disposable project database. There is no call to `/experiments`, no model fit or experiment history, no native build, owner PC access, original data/write, app or backend change, workflow dispatch or risk waiver.

**Acceptance after this checkpoint:** P4 ACTIVE, R01–R06 OPEN, real business Gate C UNVERIFIED, R02/R04/R05 native NOT TESTED, R03 physical offline 8 GB/Qwen NOT TESTED, original whole app-local-data STRICT FAIL (320 baseline / 346 observed; historical writer UNKNOWN), P5 NOT AUTHORISED, P8 NOT CERTIFIED. The one-use P4-71 native approval is consumed. Full BE-024 configurable preprocessing remains OPEN and must not be presented as implemented.

