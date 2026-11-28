# PilotODIN P4 R02.5 | Source-only diagnostic for exact Sysmon and ETW lifetime failures

**21 November 2026. Source-only implementation complete at `c07d93fda2b36bbfa5e275e5ef1c327a31cbead1`.** [Exact-source CI #44891619664](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44891619664) **4/4 SUCCESS**: 933 Python tests passed, 6 skipped, 378 subtests, 104 Node tests, TypeScript/Vite build, disposable real-HTTP browser, hosted-Windows synthetic collector and R03 fixture tests. **No native Rust compilation, PilotODIN startup, new Sysmon provisioning, protected owner data, installer or live FileIO/network capture** occurred in this increment.

## Why this is the correct next evidence checkpoint

The owner-approved no-CDP hosted-Windows [Stage 1 retest #44890538700](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44890538700) compiled and exercised the unpackaged app, matched protected endpoint snapshots, captured one app, six WebView and one WebView-network process, and observed zero ETW loss. Both retained app/launcher handles agreed exactly with corresponding ETW payload birth and exit times. However, the verifier stopped on **`no-cdp-sysmon-lifetime-unverified`**, before confirming the app and launcher's whole lifecycle and browser ancestry. The old combined Boolean did not distinguish missing Sysmon exit, disputed identity, exact exit mismatch, birth mismatch, capture bounds or image mismatch. Existing redacted logs are insufficient to infer the single failing clause. The old run remains **BLOCKED** and cannot be reinterpreted.

## Exact source change

`qa/p4_native/n12_exit_corroboration.py` now exposes the existing no-CDP-only predicate as eight named fixed checks consumed **both** by the original `all(checks.values())` strict gate and by a separate redacted `no_cdp_sysmon_diagnostic`. Acceptance is not decided from the report. No tick tolerance was added or changed. The unchanged checks are:

1. `no-cdp-scope-enabled`: the separately approved no-CDP mode is active;
2. `sysmon-exit-present`: the independent Sysmon GUID-owned process has a recorded end;
3. `sysmon-exit-not-disputed`: its exit is not marked disputed;
4. `etw-sequence-present-and-equal`: ETW start and stop share a non-null sequence;
5. `etw-lifetime-payload-within-window`: provider creation/exit payloads stay in the original capture window in order;
6. `etw-birth-within-original-sysmon-bound`: creation is within the **existing** 1 ms Sysmon start join;
7. `etw-exit-exactly-matches-sysmon`: independent Sysmon end equals the ETW ExitTime payload **exactly**, with no rounding or relaxed tolerance;
8. `etw-start-exact-image`: ETW start's full canonicalized executable path exactly matches the independent Sysmon image.

Missing, duplicate or sequence-conflicted ETW pairs fail before these checks. The diagnostic uses only whitelisted fixed error labels for those cases; arbitrary exception text and raw process values are not returned.

`qa/p4_research/n12_app_lifetime.py` now emits an additional `no_cdp_sysmon_diagnostic` key **only** in `no_cdp_profile=True` reductions. It includes separate **launcher and app** status, named failed checks and **relative** ETW-vs-Sysmon and Sysmon-vs-original-handle birth/exit deltas in 100 ns ticks; all browser/network child results are aggregated by role as counts and static failed-check labels. It contains **no** PID, process GUID, full image/path, command line, private data or absolute timestamp. On coverage loss or no verified ETW source it reports `NOT_EVALUATED`, not a misleading positive result. Every receipt keeps `native_N12_acceptance=NOT_EVALUATED`.

## Generated tests and preserved refusals

The synthetic tests in `tests/test_p4_n12_app_lifetime.py` establish positive comparison without promoting missing-stage evidence; distinguish missing, disputed or exact-mismatched Sysmon exits; verify original-handle comparison deltas; reject missing ETW stops, wrong ETW sequence, changed start executable path, out-of-window ETW payload and collector loss; and assert the diagnostic is absent in ordinary default mode. Sensitive identifiers/paths/absolute timestamp strings are excluded from the diagnostic. Legacy strict N12 tests and acceptance remain intact.

**No retrospective native assertion:** The actual #44890538700 runner did not emit these new per-clause fields, and its original private underlying process records are not available from the redacted job log. The root clause therefore remains unknown until independently acquired evidence, not guessed from the app handle's exact ETW match.

## Next permission boundary and ledger

A **new explicit one-use authorization** is required to capture another exact-source hosted-Windows no-CDP app lifetime with these now-tested per-clause receipts. Prefer a carefully reviewed **single narrowly scoped diagnostic capture** rather than recurring blind retries. The N12 lifetime workflow is still `if: false`, previous one-use approval marker absent. Stage 2 full filesystem/FileIO and network acceptance, installer, firewall changes, owner's installed app and protected data are **not authorized**.

**Unchanged:** Stage 1 native **BLOCKED**; file mutation workstream **3/4 (75%)**; R02.5 **0/5**; N12 **0/2**; network **2/3**; official P4 **14/20 (70%)**. Last complete owner-approved native N12 #44838416004 remains filesystem **FAIL**, network **FAIL**, FileIO coverage **BLOCKED**.
