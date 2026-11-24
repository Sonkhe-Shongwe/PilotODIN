# PilotODIN 1.0 | Current tab migration handoff

**Checkpoint: 24 November 2026, after G2.20 actual Windows baseline.** Read this first in any new conversation. GitHub is the working source of truth; do not assume the local owner tree was inspected. This is a compact operational summary, not a new acceptance decision or an authorisation to run native tooling.

## 1. Identity and navigation

- Repository: [Sonkhe-Shongwe/PilotODIN](https://github.com/Sonkhe-Shongwe/PilotODIN).
- Active branch: `feature/live-dev-workspace-20261023`.
- Audited pre-documentation HEAD: [`b0c39a75212eab9e92445e6a0cbf12e250dc33d7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/b0c39a75212eab9e92445e6a0cbf12e250dc33d7). Query current branch HEAD before editing; the migration audit itself adds a documentation-only commit.
- Last native-reviewed source: `35aa9f080a394c7578a1a0255f4414bb59b29395`.
- Last focused source implementation: G2.20 `8c2d456a1978145d10af1da86caf97053b07a1b3`, [CI #45341086645](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45341086645) SUCCESS.
- [Current status / scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard), [full continuity history](./SESSION_HANDOFF_CURRENT.md), [four-gate ledger](./P4_R02_5_25_PERCENT_EXECUTION_TRACKER_2026-11-22.md), [G2.20 exact result](./P4_R02_5_G2_20_INTEGRATED_PASSIVE_FILEIO_PATH_DIAGNOSTIC_2026-11-24.md), [documentation audit](./DOCUMENTATION_CONTINUITY_AUDIT_2026-11-24.md).
- Product: local-first Windows analytics/data investigation/predictive modelling; React/TypeScript, Tauri/Rust, local FastAPI/SQLite, pandas/scikit-learn, report export, optional bundled/cloud ODIN. Owner's original Master Reconstruction Blueprint is normative; [phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) governs scope/exit, not historical source guesses.

## 2. Progress and scope

| Measure | Status |
| --- | --- |
| P0 | Scoped core journey accepted |
| P1–P3 | Bounded development closure (not release certification) |
| P4 Target Intelligence | ACTIVE, 14/20 (70%) |
| R02.5 official score | 0/5 points |
| N12 acceptance | 0/2 |
| File-mutation preparation | 3/4 (75%), separate internal tracker |
| Four-gate R02.5 delivery | G1 only, 1/4 (25%) |
| P5 | Unauthorised |
| P6/P7 | Later phases |
| P8 | Final integrated Windows release pending |

G1 **GitHub source identity and safe contracts** passed; G2 **Complete real native FileIO evidence** open; G3 **Correct actual product writing mechanisms** pending; G4 **Strict final mutation closure** pending. Each gate awards 25 percentage points only at independently verified exit. G2.20 is a checkpoint, not a completed gate. The owner explicitly selected G2 as the immediate priority; the general CF-01–CF-10 product backlog remains important but does not replace it.

G2 requires one-use-approved, exact-source disposable actual Windows execution, real Sysmon File/TCP/UDP calibration, original writer and original **file** HANDLE / FileObject / IRP / path / operation joins, independent loss review, write/restore, private handling and cleanup. G2 can complete with product violations if evidence is complete. G3 fixes the actual mechanisms; G4 proves zero prohibited or unresolved mutations and unsupported events under complete independently approved strict capture. Do not quietly amend these criteria.

## 3. Latest genuine native result

[Run #45342345634](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45342345634) at reviewed source `35aa9f0`, activation `8437e93180c2d5243f9f16a21491f8f04cd3abcb`, job `138268731874`, attempt 1. **COMPLETED FAILURE / BLOCKED evidence** at 06:49:59 UTC, 24 November. This is not a build failure or a startup crash. Staged executable SHA-256: `2c068d9944e782afa44eec6e93b4071ee3b94fb465dbdac0460affcd5009038a`.

| Evidence from actual log receipt | Observed |
| --- | --- |
| Native build, app ready, cleanup, worker exit | Completed |
| Initial and final Sysmon calibration | Both passed on read 1 |
| ETW/Sysmon exports and reduction | Completed |
| Collector event / log-buffer / realtime-buffer losses | 0 / 0 / 0, 1,249 buffers written (not full completeness proof) |
| Same-capture mutate and restore | TWO_UNIQUE_WRITES_CORROBORATED |
| Generated calibration bookends | BOOKEND_OS_FILE_NETWORK_REVIEWABLE |
| Protected endpoint snapshot | MATCH (not no transient write proof) |
| Scoped WebView roles | 6 webview + 1 webview-network |
| Known scoped operations | 5,106 |
| Prohibited operations | 23 (21 WebView, 2 other) |
| Unresolved mutation credits | 4,921 total |
| Strict WebView-network write-path gaps | 125 |
| Bounded path candidates | 112 eligible, 102 checked, 102 candidate outside-scope, 10 eligible unchecked, 13 ineligible |
| Candidate physical path / original file HANDLE proof | NOT VERIFIED |
| Strict credits awarded from candidates | 0 |

The 102 are lexical path candidates within the 125 strict network gaps; never add them to 23 as confirmed violations, subtract them from strict gaps, or label them physical destinations. Both calibration and control receipts remain diagnostic, not official acceptance. The historical **complete** N12 journey [#44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004) remains the governing full-audit filesystem FAIL, network FAIL, mutation coverage BLOCKED. Its earlier 227,087 network / 4,112 background gaps and 42 missing lifetimes are a different capture and scope. Do not compare counts as a proven improvement in product containment.

### Actual remaining blockers

- Lifetime verdict BLOCKED with issues `app-or-launcher-handle-unverified`, `no-cdp-prior-lifetime-evidence-unverified`, `no-cdp-sysmon-lifetime-unverified`.
- Retained launcher and app handle creation and exit times exactly match ETW payload values (zero tick deltas). Sysmon exit exact-match check fails: ETW minus Sysmon 34,799 ticks (3.4799 ms) for launcher, 53,810 ticks (5.3810 ms) for app. All seven child roles fail the same check. This is evidence of a disagreement, not evidence of an accepted tolerance or proof of the cause.
- ETW start image exact paths match for launcher, app and all children. Child stop headers precede unconfirmed exit; six child start headers precede creation slightly. Do not conflate header emission time with payload/retained HANDLE times.
- Child shadow witness review retained zero accepted original child witnesses. Private child diagnostic failed `private-evidence-inventory-unverified`. Need trace of actual observer, transport, decoding and inventory comparison; cannot infer whether sampler missed processes, private evidence absent or admission failed.
- Browser command-line profile not verified; effective UDF unknown. Original FILE handle to kernel FileObject association remains unproved. Query-only original process HANDLE is distinct from original file HANDLE.

## 4. Exact next action (proposed G2.21)

1. Inspect `qa/p4_native/n12_exit_corroboration.py` (`EtwLifetimes._no_cdp_sysmon_checks`, `_no_cdp_sysmon_confirmed`, `shadow_handle_exit_review`, `_order_issues`) and `qa/p4_native/n12_trace.py` Sysmon Event 1/5 parsing. Establish documented meaning and capture precision of each clock and witness. Reproduce the observed mismatch in a source fixture. Do not simply increase tolerance or treat Sysmon as redundant.
2. Trace `qa/p4_research/n12_app_lifetime.py::reduction`, `n12_no_cdp_child_handles.py::ScopedQaChildHandleObserver` and `private_child_handle_diagnostic`, and `n12_private_child_pipe.py` (hosted_scope, encode/decode, worker send/parent receive). Investigate actual fixed-label inventory failure, differentiate missing witness versus failed admission. Reuse existing tests in `tests/test_p4_n12_app_lifetime.py`, `test_p4_n12_no_cdp_child_handles.py`, `test_p4_n12_private_child_pipe.py`, `test_p4_n12_lifetime_etw.py`. Implement only a verified minimal correction, with positive and negative regressions.
3. Run ordinary exact-source GitHub CI; update ledger with evidence. Do not create new generated-only Windows experiments by habit. Once lifetime evidence repaired, prioritize redacted destination families of confirmed prohibited operations and candidate paths using existing `n12_trace.inspect_etw_files`, `n12_etw_correlate.RequestPathHistory`, `n12_no_cdp_fileio_review.reduce` and existing storage/path diagnostic helpers. No raw path export or allowlist changes.
4. Resolve the independent original-file-HANDLE / FileObject relation by a safe evidence mechanism, or report the precise remaining feasibility blocker and seek a deliberate gate-review decision. Never substitute synthetic shape or passive lexical path for original physical destination. Only propose a separately scoped source-pinned live capture when it can answer a concrete unresolved question.
5. G3 only after trustworthy product mechanism evidence: minimal product code fix, test and native verification. G4 is separate complete acceptance. Avoid indefinite diagnostic-only loops; prioritize product root causes with the existing code-first discipline.

## 5. Decisions and source history not to lose

- G1 source contracts passed. G2.8 real generated-only Sysmon bookends passed; G2.14 generated PSS type-name not available; G2.15 self-owned generated file duplication validated FILE_TYPE_DISK only for its known disposable file.
- G2.16/G2.17 proposed foreign PSS handle bridge was **revoked** by G2.18 before any real browser use. Microsoft warns socket DuplicateHandle can interfere with Winsock bookkeeping, and File type can include IFS sockets. No arbitrary foreign file/socket handle duplication or undocumented kernel pointer scans. Both candidate entrypoints fail closed; existing child process handles remain query-only 0x1000.
- G2.19 source `d624aec63d272581dc7b4b0e660e38cb3351f0a3`, [CI #45333948777](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45333948777) SUCCESS: all observed event-16 writes indexed including missing/zero IRP; per-role shape-only diagnostic, 15,000 generated-write regression. **Not a native attribution proof.**
- G2.20 integrates bounded existing request-time name-epoch diagnostic in actual no-CDP reducer without path-credit callback; source CI green and actual receipt above. The strict governing reducer remains unchanged.
- Worker TEMP/TMP/TMPDIR/CWD source correction exists; actual WebView2 effective UDF and product storage cause still unresolved. Do not pretend the QA UDF profile equals actual physical storage. [Worker record](./P4_R02_5_PRODUCT_WORKER_TEMP_CONTAINMENT_2026-11-21.md), [G2.18 safety](./P4_R02_5_G2_18_SOCKET_SAFE_ORIGINAL_HANDLE_BOUNDARY_2026-11-24.md).
- General CF-02 identifier handling fixed for new CSV imports, exact [CI #45057052836](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45057052836); CF-01 preparse safety and other risk items preserved in [code-first directive](./PILOTODIN_CODE_FIRST_REMEDIATION_DIRECTIVE_AND_DOCUMENTATION_AUDIT_2026-11-22.md). No completion claim for CF-01. Other P4 open work includes network isolation, physical 8 GB bundled offline inference/coexistence, historical owner-data preservation and signoff.

## 6. Authority and execution safety

Owner says no more intermediate installers; P8 final installer only. Routine GitHub source edits, documentation and source/synthetic CI are permitted. No assumption of native authorisation from "next" or the migration request. Latest owner approval covered **one** exact-source actual-app baseline, consumed at activation `8437e93`, disarmed `6736752619f1704b8222521a0dbdf874c4b75f4c`. Consumed marker `qa/p4_research/N12_NO_CDP_FILEIO_OWNER_APPROVAL_20261124_G220_ONE_USE.txt` remains for audit; do not reuse. Native workflow `.github/workflows/p4-n12-no-cdp-fileio.yml` is disabled; G2.13–15 generated native workflows also disabled. No auto retry, foreign handle duplication, expanded roots, personal/owner data, raw ETW/path upload, additional network/firewall native actions or installers. A fresh explicit one-use scope and reviewed SHA are required for a future live native experiment. Previous broad owner permission does not erase one-use boundaries.

When the owner says "next", act directly on the repo for a meaningful safe engineering step. Check branch HEAD first, use existing source/tests and non-force compare-and-swap update, verify exact-source CI, and record the resulting evidence in the status and ledger. Do not mistake source CI PASS for native acceptance, or report success while a job is pending. Report before and after four-gate score, official P4/R02.5/N12 score, exact commit and CI/run ID, blockers and smallest concrete next action. No em dashes in user-facing replies. Do not ask the owner to repeat this context.

## 7. New-tab instruction

Open this file from the active branch, verify current HEAD and latest evidence, then execute the G2.21 source audit described in section 4. No installer and no new native run based on the consumed permission. Preserve earlier history; do not restart PSS feasibility from scratch.
