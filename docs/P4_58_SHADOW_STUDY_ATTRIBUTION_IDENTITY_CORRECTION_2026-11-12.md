# PilotODIN 1.0 | P4-58 Shadow study attribution identity correction

**Evidence date:** 12 November 2026. **Phase:** P4 Target Intelligence, active. **Scope:** local read-only P4-57 evidence validator only. No new prospective owner decisions, external attestation, business gate signoff, native build, installer, model fitting, original Windows app/data or CI workflow modification.

## Confirmed defect and reproduction

Source reviewed from the exact GitHub branch checkpoint `668952d9154f4186320bfb0f813d8c4944033e3c`; local copies of `qa/p4_shadow/validate_shadow_log.py` and `tests/test_p4_shadow_decision_log.py` matched existing Git object blob hashes `c16f066c57e7609132e651ea4ca01c84e04419c7` and `b9767726ce9c76382b6b2919e78ce7066f65826d`.

P4-57 keyed used CI run IDs by `(change_id, workflow_run_id)` rather than the GitHub Actions run's **globally unique ID**. A synthetic pre/post input with two different pre-push `change_id` values and the **same one GitHub Actions run ID** was accepted as `post_runs=2, completed_runs=2, failed_runs=2`. This is a confirmed validator data-integrity defect, **not evidence that an actual P4 owner study double-counted real GitHub runs**. No real prospective study records exist.

Two closely related study-attribution gaps were also verified by source inspection: identical proposed patch identity (branch, base commit SHA, patch SHA-256) could be counted as distinct changes by renaming `change_id`; multiple post-CI rows for one change could present conflicting push timestamps and incorrectly imply one frozen decision covered two pushes.

## Bounded fix

1. Require global uniqueness of `workflow_run_id` across the entire supplied post-CI file; preserve distinct run IDs for different workflows executed against one change.
2. Require distinct `(branch, base_sha, patch_sha256)` for each pre-push change identity, preventing accidental double-counting of identical proposals.
3. Require a consistent push timestamp for all post-CI runs linked to one predecision. Existing strict `predecision < push <= run_start` ordering remains.
4. Add four synthetic tests: duplicate run across change IDs, duplicate patch across change IDs, inconsistent push timestamp, and positive multi-workflow same-change control. No format/schema field added, no alteration to prior valid distinct-run records.

**These checks verify only manually entered internal consistency.** The validator still cannot independently prove that a patch digest corresponds to a real Git diff, that a GitHub run maps to a particular pushed head SHA, that the timestamps were immutable, or that a human took an action. A real evidence source, genuine pre-push commitments, ownership and benefit-cost assessment remain required.

## Local verification

- Python 3.13.5, isolated Linux authoring container, source bytes verified against GitHub history before editing.
- Previous exact GitHub source and tests: `python -m unittest discover -s tests -p test_p4_shadow_decision_log.py -v` **12/12 PASS**.
- Reproducer against previous GitHub validator source: **wrongly accepted one run ID for two change IDs** and returned `failed_runs=2`.
- After source fix: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_p4_shadow_decision_log.py -v` **16/16 PASS**, including four new regression cases.
- `python -m py_compile qa/p4_shadow/validate_shadow_log.py tests/test_p4_shadow_decision_log.py` **PASS**.
- New source blob SHA-1 `3bb5e4014d1deb5dfce4232467086b1f2ca06e2a`; test blob SHA-1 `9dbc8682372c3c9f76b74a2e07e1ad6ae106cbee`. Confirm these match the GitHub committed blobs.
- **Not executed:** full PilotODIN backend/frontend/browser suite, GitHub Actions verification at the new SHA, Windows native/physical 8 GB, Qwen, any model fit, any real future study, or owner-machine access. Do not infer a CI PASS from the local checks.

## Acceptance / next

This is a **source-local engineering correction**, not real-business Gate C evidence, a P4 acceptance signoff or activation of the study. The P4-56 proposal remains **manual shadow-only**, with no monitoring and no change to normal CI. Owner approval of the objective and independent timestamps/outcome classification are still missing. P4-R01–R06 remain OPEN, owner declined risk deferral, P5 NOT AUTHORISED, P8 NOT CERTIFIED. Historical original whole-app-local-data R06 STRICT FAIL (320 backup vs 346 observed, 74 WebView/cache candidates, historic writer unknown) remains unchanged. P4-47 native and P4-55 research fit one-use approvals remain consumed.

**Recommended next:** stop adding study tooling absent new real evidence. Seek the owner's explicit assessment of whether the self-owned CI QA decision fits the unchanged business Gate C; only then capture a genuine **future** frozen pre-push decision and subsequent independently verified, privacy-minimised result. Keep original Windows data untouched and existing CI unchanged.
