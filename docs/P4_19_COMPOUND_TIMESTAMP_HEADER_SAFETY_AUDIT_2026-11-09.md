# PilotODIN 1.0 | P4-19 Compound Timestamp-Header Fail-Closed Audit

**Evidence date:** 9 November 2026  
**Scope authority:** Owner said `next` after P4-18 risk audit. Continue **P4 safety correction only**, not development closure, P5, training, real-data access or Windows installer work. The owner's prior refusal to waive acceptance risks remains controlling.  
**Repo and branch:** `Sonkhe-Shongwe/PilotODIN`, `feature/live-dev-workspace-20261023`  
**Exact tested application source:** [`749dd3f7890c316020341accdb4d0e0b4afd51c3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/749dd3f7890c316020341accdb4d0e0b4afd51c3)  
**CI:** [P4 #42691710713](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42691710713) **COMPLETED SUCCESS**: **104/104 Python, 28/28 Node, TypeScript/Vite production build PASS, 8/8 disposable real-HTTP Chromium PASS**.  
**Owner Windows installed QA:** **OLDER** `bca3c57b94a425cd9ef489726e721328d12c2ead`, source fix NOT tested natively.

## Source-confirmed risk and bounded fix

P4's `backend/target_opportunities.py::_is_date()` evaluated `set(_normalized(header).split("_")) & TIME_TOKENS`, where `TIME_TOKENS` contained compound terms `created_at` and `updated_at`. Splitting into `created`, `at` or `updated`, `at` meant those compound terms **could never match** the token set. A string-typed column `outcome_created_at` or `churn_updated_at` containing two distinct ISO date strings, with a varying predictor and 80 labels, could thus pass `engine.infer_task`'s two-distinct-class shortcut and be reported as **structurally reviewable classification**, despite being a timestamp-like target. Existing datetime64 values and exact single-token `_date` suffixes had independent blockers, but date strings in compound-header `*_at` columns escaped them.

**Change:** Treat a normalized header ending in conventional **`_at` timestamp suffix** as date/time, even when the data was loaded as strings, while preserving existing single-token checks and pandas datetime dtype check. This blocks `outcome_created_at`, `churn_updated_at`, `fraud_reported_at` as unsupported P4 supervised targets. Exact `created_at`/`updated_at` names are blocked for the same reason. It is a **conservative header-based structural gate**, not proof of field semantics or universal protection against every oddly named timestamp. These candidates are not deleted or auto-transformed; the owner can continue descriptive analysis without an auto-training approval.

**Five new parametric/single synthetic tests** appended to `tests/test_p4_target_opportunities.py`:
- 3 named timestamp variants with two ISO date strings and varying feature; suggestions abstain, source frame unchanged, date/time blocker visible, no task hypothesis or implicit training approval.
- Explicit `inspect_manual_target` of timestamp-like `outcome_created_at` remains blocked, read-only, no approval.
- Legitimate finite numeric `future_cost` retains regression hypothesis as **structurally reviewable only** and `safe_to_train_automatically=false`.

No frontend logic, datasets, source Quality revisions, training API, installed binaries, model weights, release artifacts or real user projects were changed by the correction.

## Verification scope and limitations

| Requirement | Evidence / status |
| --- | --- |
| Compound timestamp-like outcome titles cannot silently become binary labels | **SOURCE-FIXED + AUTOMATED PASS** at `749dd3f7890c316020341accdb4d0e0b4afd51c3` |
| Read-only manual selected-target screening applies same blocker | **AUTOMATED PASS** |
| Valid numeric regression remains reviewable with no training approval | **AUTOMATED PASS** |
| Existing P4 safety matrix, version/project isolation and bounded negative tests | **P4 CI 104 Python + 28 Node + 8 browser PASS**; not comprehensive guarantee |
| Owner Windows QA app at this new exact SHA | **NOT TESTED**; installed version remains earlier source `bca3c57...` |
| Native 8 GB/offline stability, Quality revision and no original data mutation | **OPEN / NOT TESTED** |
| Original real-world Gate C (independent label, time, true entity/group split, measurable decision benefit, lawful/fair use) | **UNVERIFIED; NOT WAIVED** |

**Defect disposition:** Medium P4 screening correctness; source-fixed/green CI; **native verification pending at later owner-authorised consolidated candidate**. The previous P4-18 non-finite numeric guard and historical CI outcomes remain unchanged.

**Phase status:** P4 **ACTIVE**; owner explicitly declined closure while risks are deferred; P4-17 closure **NOT APPROVED**, P5 **NOT AUTHORISED**, P8 **NOT CERTIFIED**. QA Issue #2 and P4 evidence Issue #9 **OPEN**. The next justified risk-first task is a more general screening correctness/isolation audit or a properly scoped original Gate C evidence intake, not another installer or repetitive owner CSV import.
