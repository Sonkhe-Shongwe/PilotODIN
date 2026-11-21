# PilotODIN 1.0 | P4-26 WebView2 profile-flag boundary guard

11 November 2026. P4 safety-only engineering, not production release or owner Windows acceptance.

## Verified finding and exact scope

In the existing optional read-only `qa/p4_native/P4_WebView_Process_Evidence.psm1`, a regular expression recognized a syntactically similar `--user-data-dir` string even when the string was embedded in a different quoted argument such as `--log-file="note --user-data-dir=C:\\P4synthetic\\Local\\com.pilotodin.studio\\EBWebView trailing"`. It also permitted partial matches immediately before malformed trailing quote characters. That could lead to an unjustified current original/QA profile count. This is a synthetic source-confirmed **diagnostic accuracy** defect, not an observed physical WebView2 security breach, historic writer proof or dataset mutation.

## Bounded correction and regressions

- Source [`80202db106b83e433d8d9979d7cf4afccab507f8`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/80202db106b83e433d8d9979d7cf4afccab507f8): require the complete flag to terminate at whitespace or end of command, and reject apparent flags located inside the quote state of another command-line argument; an odd run of backslashes escaping a double quote does not toggle the quote state. The existing expected roots, directory-prefix guards and no-certification output flags are unchanged.
- Final regression-only [`50351860537ff2c55be83d01c82f152fc21d09f2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/50351860537ff2c55be83d01c82f152fc21d09f2): explicitly exercise a fake `--user-data-dir` inside quoted `--log-file` text with trailing words, two malformed flag suffixes, and a genuinely valid flag after unrelated quoted text. All inputs are disposable fake process metadata, never actual user process enumeration.
- The observer remains read-only, collects current `msedgewebview2.exe` launch flags only, prints aggregate counts only, and reports `historical_writer_process_identified=false`, `qa_cross_app_write_excluded=false`, `original_full_data_preservation_passed=false`, `original_project_data_certified=false` and `offline_8gb_certified=false`.

## Actual CI verification

| Evidence | Result | Boundary |
| --- | --- | --- |
| [P4 run #43052022558](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43052022558), source `80202db` | **COMPLETED SUCCESS**, all 3 jobs | First code and test patch; synthetic Windows only |
| [P4 run #43052326497](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43052326497), source `5035186` | **COMPLETED SUCCESS**, all 3 jobs | Final quoted-argument regression plus Linux backend/Node/build and disposable real-HTTP Chromium |
| Actual owner Windows process read/write attribution | **NOT TESTED / UNKNOWN** | Only existing on-owner P4-24 source-scoped storage comparator evidence |
| This later documentation-only commit | **No fresh CI claimed** | Results are tied to the exact earlier source SHAs |

The initial P4-25 implementation run [#43048430220](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43048430220) was cancelled with a failed Windows job, then corrected by [`c02b491`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/c02b49187422b95d1b2c3e9a165d02b58155bd61) and successful [#43048615880](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43048615880). That failure history remains intact.

## Gate and next action

Owner's P4-24 comparator found original EXE and verified backup matching baseline, `critical_project_store_changes=0` within original `data/`, but original full-tree equality remains **FALSE/FAIL**: 320 backup files, 346 current, 74 browser/cache **candidates**, zero unclassified according to the named-path classifier. Neither the classifier nor this guard establishes the process responsible for those historical changes. No owner authorisation for a strict-fingerprint waiver, cleanup, replacing the baseline, new installer or P4 closure has been given.

Next only: preserve failed evidence and backup. If separately owner-authorised, optionally observe current WebView2 launch profiles without treating the result as historic file-write attribution. Later native dock/source-parity testing, real offline local Qwen, continuous 8 GB testing and real business Gate C remain independently unresolved. P4 ACTIVE; P4-R01–R06 OPEN; P5 NOT AUTHORISED; P8 NOT CERTIFIED.
