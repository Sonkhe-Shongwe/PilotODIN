# PilotODIN 1.0 | P4-57 local Gate C CI shadow-decision evidence validator

**Status: PREPARATORY TOOLING ONLY. P4 active, P4-R01–R06 open, P5 not authorised, P8 not certified.**

## Rationale and scope

[P4-56](./P4_56_CI_GATE_C_HISTORY_FEASIBILITY_2026-11-12.md) identified a potential user-owned development decision: before pushing a change, decide whether a focused extra preflight would be worthwhile in addition to the normal CI. It found no independently timed pre-push decisions, true human repair time, root-cause audit or decision benefit. Neither historical workflow failure nor retrospective modelling establishes Gate C.

P4-57 adds only `qa/p4_shadow/validate_shadow_log.py` and `tests/test_p4_shadow_decision_log.py` to give the owner a **local/manual, non-collecting, read-only validation format**. There is **no event listener, CI trigger, API token, GitHub API request, action execution, outcome backfill, model fitting, installer/native build, original owner-data operation or automated logging**. No real decision records have been captured. Any future shadow study requires owner participation and independent evidence validation. Do not commit actual personal time/account records or sensitive details into this public repository.

## Manual intake formats: one JSON object per line (JSONL)

Create `pre.jsonl` privately before an actual future push. Each line has exactly the following keys. This is **synthetic format illustration, not an observed decision**:

```json
{"change_id":"synthetic-001","recorded_at_utc":"2026-11-12T08:00:00Z","branch":"feature/live-dev-workspace-20261023","base_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","patch_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","changed_paths":["frontend/src/App.tsx"],"extra_preflight_recommended":true,"proposed_check":"targeted frontend typecheck","rationale":"Synthetic edit has potential typecheck exposure"}
```

`patch_sha256` must identify the actual proposed patch bytes using a documented, stable digest method. It is **not** proof that the proposed patch matches the later commit: independent reconciliation of base, diff, patch digest and run `head_sha` is still required. `recorded_at_utc` must be captured **before** the push and should have independently verifiable timestamped provenance. The validator cannot prove that a local file was not retroactively edited. A recommendation remains **shadow only**, never permission to suppress existing CI or run extra checks.

After a particular workflow run exists, manually record a `post.jsonl` entry for the same `change_id` and exact workflow run. For every distinct `(change_id, workflow_run_id)`, use exactly these keys:

```json
{"change_id":"synthetic-001","push_at_utc":"2026-11-12T09:00:00Z","workflow_run_id":123456789,"workflow":"P1 Isolated Frontend Verification","run_started_at_utc":"2026-11-12T09:01:00Z","run_conclusion":"failure","failure_attribution":"unattributed","attribution_evidence_url":null,"human_debug_minutes":null,"actual_preflight_minutes":null}
```

Allowed conclusions: `success`, `failure`, `cancelled`, `skipped`, `queued`, `unknown`. Cancellation/queue/unknown are **censored or unresolved**, not defects or successes. For completed failures, allowed independent attribution categories are `new_actionable`, `pre_existing`, `expected_test`, `infrastructure`, `unattributed`; any definite classification requires a GitHub repository evidence URL. Non-failures must use `not_applicable`. Actual measured human times are non-negative numbers of minutes; **null means unmeasured, not zero**. No model scores, ROI assumptions or eventual corrective commit information may be inserted into the predecision row.

## Offline validation

```powershell
python qa/p4_shadow/validate_shadow_log.py C:\private\pre.jsonl C:\private\post.jsonl
python -m unittest discover -s tests -p test_p4_shadow_decision_log.py -v
```

The validator reads both files and prints structure-only counts. It rejects extra outcome keys in predecisions, missing/fabricated upstream decisions, duplicate decisions/runs, backwards recorded/push times, unsafe path forms, invalid conclusion/attribution combinations, and missing measured-vs-unmeasured distinctions. It **never writes to, changes or transmits the JSONL files**.

**Limits:** This is schema and relative-chronology validation, **not an independent clock, GitHub run signature/URL verifier, immutability guarantee, owner acceptance, avoidance-of-defect proof or a Gate C pass**. It cannot prove that a human would have acted on a shadow recommendation, or measure the counterfactual benefit of an extra check. Attach independent provenance and adjudication notes in a separately authorised study. Do not attempt to infer causal benefit from a small sample of 20–30 future changes. The first 20–30 distinct changes proposed in P4-56 are a feasibility check of instrumentation, not statistical power or an acceptance threshold.

## Local verification evidence and gate

- 12 November 2026: `python -m unittest discover -s tests -p test_p4_shadow_decision_log.py -v`: **12/12 synthetic tests PASS** in the isolated authoring container after a test-only assertion correction. The test failures during local authoring are not claimed as a GitHub CI run.
- `python -m py_compile` for both files: **PASS** in the isolated authoring container.
- **Not executed:** current full PilotODIN backend/frontend suite, GitHub Actions on this change, owner Windows native UI, physical 8 GB AI, training, or a genuine prospective decision record.
- **Next:** obtain a separate owner decision that this internal GitHub QA use case meets the real-business Gate C charter; only then ask the owner to manually capture a real pre-push record under independent timestamp and privacy safeguards. Continue all existing CI unchanged. Evaluate missingness and attribution consistency before any intervention or model permission.

The R06 historical full owner-app-local-data strict integrity finding remains **FAIL** (320 backed-up files versus 346 observed, 74 cache-folder candidates, writer unknown). This synthetic tool cannot resolve it. One-time P4-47 native-build and P4-55 training permissions remain consumed.
