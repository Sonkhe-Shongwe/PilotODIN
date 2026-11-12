# PilotODIN 1.0 | P4-49 mixed-case identifier screening

**Date:** 12 November 2026. **Phase:** P4 Target Intelligence. **Implementation commit:** [`bb79ae2b5d2499840d6f81dd403bb458cc9a0785`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/bb79ae2b5d2499840d6f81dd403bb458cc9a0785). **Exact-source CI:** [#43174956377](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43174956377), **completed success, 3/3 jobs**.

## Source-confirmed gap

The P4-48 safeguard excluded identifier-like predictors only when the existing `_is_identifier` function recognised their header. Its `_normalized()` calls `casefold()`; `accountId` became `accountid` and `CustomerID` became `customerid`, neither matching `_id`. A synthetic 80-row `churn` Y/N target with only such a unique per-row identifier could therefore be marked structurally reviewable. This is **source/synthetic false-readiness risk**, not proof of a real user dataset incident, model training or predictive business value.

## Bounded implementation

`backend/target_opportunities.py` adds `_CAMEL_IDENTIFIER_SUFFIX`, a case-sensitive check for `ID`, `Id`, `UUID`, `Uuid`, `GUID` and `Guid` at a mixed-case header's end, preserving existing exact and underscore-separated identifier cases. It requires a preceding alphanumeric character to identify a suffix boundary. This check applies to both reviewed targets and minimum predictor evidence, and supports the existing repeated-identifier aggregate hints.

`tests/test_p4_target_opportunities.py` adds eight synthetic cases: four identifier-only blocked headers (`accountId`, `CustomerID`, `claimUUID`, `paymentGuid`), three non-identifier controls (`valid`, `paid`, `grid`) and one mixed-case identifier plus genuine varied `event_type` predictor. Tests assert ranked/manual consistency, no data mutation, no automatic training and no silent false blocking of legitimate non-identifier controls.

## Exact verification

| Evidence | Actual result |
| --- | --- |
| [P4 Actions #43174956377](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43174956377), exact source `bb79ae2` | **COMPLETED SUCCESS**, 3/3 jobs |
| Python focused backend tests | **163 passed** |
| Node P4/source contracts | **45 passed, 0 failed** |
| TypeScript and Vite production build | **Passed** |
| Disposable real-HTTP Chromium | **9 passed** |
| Windows synthetic read-only preservation and WebView fixtures | **Passed** on PowerShell 7.6.9 and 5.1.20348.5773 |

This is compiled frontend/source, real-HTTP disposable browser and synthetic Windows-script evidence only. There was **no new native Tauri compilation**, installer, actual latest-source user Windows functional acceptance, bundled inference, physical offline 8 GB Qwen measurement, original data access, baseline update or modelling.

## Unchanged acceptance/no-go

P4-R01–R06 are **OPEN**. Independent real-life Gate C decision utility/label provenance not supplied; latest-source native negative/version UX and Prepare gates not complete; offline physical 8 GB analytics/Qwen coexistence not measured. Historical original entire app-data tree **strict FAIL** persists (320 independent backup files vs 346 observed; 74 changed browser/cache *candidates*, writer UNKNOWN), despite prior project `data/` scoped 0-difference result. The owner previously declined closure by risk deferral and the P4-47 one-use unpackaged native build authorisation was consumed. P5 remains unauthorised; P8 remains uncertified.

**Next engineering judgement:** Obtain genuine independent business and owner-native acceptance evidence rather than using further source tests as substitutes. Any later implementation should require a new, reproducible P4 defect and appropriate regression proof.
