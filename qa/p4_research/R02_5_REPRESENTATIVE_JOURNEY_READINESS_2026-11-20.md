# R02.5 | Representative Windows journey: bounded readiness decision

Status: **preparation only; no live capture or native build authorised**. Prepared 20 November 2026 on `feature/live-dev-workspace-20261023`. The [current status](../../docs/PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard) governs scoring, not this plan.

## Decision and prior evidence

Question: Can the **actual PilotODIN desktop journey** retain immutable originals and account for in-window file mutations with validated process, path and capture coverage? R02.5 requires a complete **calibrated hosted Windows N12 audit** with a filesystem PASS. Endpoint hashes alone are insufficient: a protected file can be written and restored between scans.

Reuse rather than repeat: the [protected write-and-restore control](../p4_native/n12_protected_restore.py) already produced a scoped hosted PASS on 19 November, with two independently identified writers and endpoint equality. It separately reported strict coverage **BLOCKED**. Do not convert its scoped success into app-wide credit. The first Procmon/ETW timing control found a 10.0724 ms stamp discrepancy and the second stopped before comparison. **Do not restart that clock chain** without an app-specific decision it can resolve.

## Minimal approved-scope candidate (not an approval)

1. Use generated CSV and a disposable project, isolated backend state, user-data folder, temp directories and native process tree. Pin the reviewed SHA, executable hash, dependency lock, WebView2 version, collector configuration, attempt and runner image before launch. Confirm no owner data is mounted or accessed.
2. Run preflight on the exact capture path before spending a native build: identity and path mapping, initial calibration, ETW export digest and loss counters, final-calibration feasibility, close/exit evidence and failure reporting. Existing tests and the known writer control are preferred to new tools.
3. Start one ETW session **before** the app journey and stop it **after** the final protected fingerprint and a verified calibration. Record immutable source digest and protected-root inventories at both endpoints.
4. Within the same trace window execute: import the generated CSV; inspect profile; preview and approve one exact Quality edit; verify new working version; undo; close native app; reopen same disposable project; verify version/history and original source digest. Use no model training and no cloud provider.
5. Inside that window change **one generated protected sentinel file and restore its exact original bytes**, using the existing independent-writer fixture where compatible with the app runner. Record separate writer identities and stage bounds. Sentinel must not be a real project source, nor a reason to weaken the protected-path allowlist.
6. Reduce the **ordinary governing N12 filesystem audit** and any comparison/diagnostics against the **same capture**. Report app outcome, protected endpoint comparison, sentinel detection, attributable writes by writer/destination, unresolved writes by reason, collector loss and closure, and network evidence separately.

## Offline readiness cases before requesting approval

| Case | Expected decision |
| --- | --- |
| Two completed sentinel writes from known writers, matching protected path, intermediate content changed, final bytes restored | Scoped positive control PASS; **not** a standalone R02.5 PASS |
| Same endpoint hashes but sentinel writes absent or misattributed | BLOCKED / calibration not demonstrated |
| Unresolved successful file write, conflicting key/object/path lifetime, incomplete rundown, or missing writer lifetime | BLOCKED, with reason and count retained |
| Known write under protected original or unexpected out-of-scope path | FAIL; a later restore does not erase the violation |
| ETW reported loss, missing capture bound, wrong source or executable digest, disjoint control/journey sessions | BLOCKED; do not report zero writes |
| Import/edit/undo/reopen fails or original checksum differs | Product journey FAIL; report stage and recovery state |
| All file checks pass while non-loopback traffic persists | Filesystem may pass at its own scope; **network R02.6 remains FAIL** |

## Offline replay result

The in-journey control reuses the two generated writers on a disposable sentinel outside the protected originals. The reducer reads their evidence from the journey's existing ETW export and requires their windows to fall after the Quality marker and before the first close. The draft accepted an extra completed write on the restore handle because the expected write still matched by size. The corrected check blocks that trace. Generated cases also rejected missing write evidence, wrong writer or destination, conflicting names, failed completion, out-of-window execution, ambiguous lifetime, changed endpoint and trace loss. A scoped pass preserves unrelated unresolved mutations and audit findings. [Replay cases](../../tests/test_p4_n12_same_capture_restore.py) · [Prior plan](https://github.com/Sonkhe-Shongwe/PilotODIN/blob/186b6e7e1524b5da8885acc42260a432e9b20b76/qa/p4_research/R02_5_REPRESENTATIVE_JOURNEY_READINESS_2026-11-20.md)

The optional control is staged in the capture code. Reviewed Undo, version-2 reopen and capture bracketing of both fingerprint scans still need representative driver verification. The hosted app workflow is disarmed.

## Stop rules and evidence retention

- Preflight must establish the reducer can produce a genuine PASS for clean generated evidence and a FAIL/BLOCKED for each relevant mutation and capture fault. Passing unit tests is not evidence that Windows production traces are complete.
- Record the **last completed stage** even on a failing run. Keep small redacted per-category counts, hashes, lifetimes and fixed error labels in durable CI logs. Raw traces, private file paths and row data remain runner-local; do not publish sensitive artifacts.
- No revision to the acceptance policy just to accommodate WebView2 writes. A real successful write outside permitted scope remains a violation until a reviewed product fix or owner-authorised policy revision.
- Retain source-revision and CI-run identity. Distinguish (a) test harness job status, (b) capture calibration, (c) file audit verdict, (d) network verdict, (e) native app journey and (f) P4 point award.
- A rerun needs a **changed, named blocker and a predicted observable outcome**. Do not run the same live setup merely hoping it passes.

## Approval boundary and follow-up

No approval is granted by this document. A later request must identify exact source SHA, Windows runner image, collector versions and provenance, dependency acquisition/build operation, generated fixture, capture window, raw evidence retention and redacted outputs, the one-use workflow/marker and expected decision. Keep the installer freeze and protected owner-data restrictions.

When ready, request only **one approved generated-data, GitHub-hosted Windows Server 2022, unpackaged app journey**. A successful R02.5 result is the calibrated full filesystem audit PASS, not simply matching protected hashes or detecting the sentinel.

Progress remains: file-mutation coverage **3/4 (75%)**, N12 **0/2**, official P4 **14/20 (70%)**.
