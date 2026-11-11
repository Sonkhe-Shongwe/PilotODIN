# PilotODIN 1.0 | P4-42 Fail closed on mid-review Quality version revision

**Date:** 11 November 2026. **Phase:** P4 ACTIVE. **Risk:** P4-R02 (negative/version parity). **Implementation SHA:** [`fad9843b9447b9d5e9a42ea1091143cbadd3b7c1`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/fad9843b9447b9d5e9a42ea1091143cbadd3b7c1). **CI at report creation:** QUEUED; NO CI PASS CLAIM.

## Exact source finding

The P4 queue and explicit manual target inspection GET handlers compared `expected_version` with `quality.current_data(project_id)` before invoking the bounded Target Intelligence candidate scan. The approved Quality state is mutable in another window. A committed Quality revision during this scan could leave the result carrying an obsolete `quality_version`, even though initial version equality was true. Old evidence could therefore be displayed as if fresh. The final recheck is **source-defence-in-depth**, not a guarantee that no revision can happen after the check, not a native report and not an owner-data incident.

## Bounded implementation

Exactly four files changed:
- `backend/main.py`: helper `_require_p4_review_version_fresh(project_id,expected_version)` reads committed `quality_state.current_version` **after** candidate computation via existing local SQLite connection. Absent/changed row returns HTTP 409 with refresh guidance. No lock, new database state, training or dataset edits. Queue and manual GET use the same check.
- `tests/test_p4_phase_exit_matrix.py`: synthetic competing committed Quality revision induced during ranked queue and manual inspection; both return HTTP 409 rather than exposing obsolete target evidence; other project's version remains 2, revised project can later be reviewed at version 3, no experiments. Additional uninitialised-state negative returns 409 without inserting a Quality row.
- `tests/test_p4_target_opportunities.py` and `tests/test_p4_manual_target_inspection.py`: adapt existing synthetic API fixture to seed explicit local `quality_state` versions and update them for version-change cases so assertions use a coherent committed version, rather than in-memory mock alone.

No migrations, original projects, database files, QA installation, P5 work or installer build. Uses existing local SQLite row lookup to avoid rereading the entire dataset just to confirm the version.

## CI, limits and governance

[GitHub P4 Actions #43096226638](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43096226638), exact implementation SHA `fad9843b`: **QUEUED; NO CI PASS CLAIM** at this report checkpoint. The change to shared `backend/main.py` also triggered adjacent P1/P2/P3 source-only workflows; their results must be tracked separately. No test or acceptance claim is made before completed outcomes.

The final query narrows stale-review exposure but cannot make HTTP response delivery/GUI state atomic with future Quality approvals. Existing stale-selection and version-bound writes remain the authoritative guards. Source CI does not establish owner-native WebView2 parity.

Strict original whole app-data preservation remains **FAIL** (320 backup vs 346 current; 74 WebView/cache *candidates*, historic writer unknown); original project `data/` prior evidence had zero changes and original EXE/backup matched independently. Independent real business Gate C, physical 8 GB offline Qwen, owner-current native verification and P4-R01–R06 remain open. Owner refused deferring risks and explicitly forbids intermediate P4–P7 installers. **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED**.

**Next:** Inspect exact-source P4 + adjacent CI outcomes; fix any failing scope regression, update authoritative evidence. Do not close P4, treat a synthetic test as native acceptance, rebaseline owner files or enter P5 without owner decision.
