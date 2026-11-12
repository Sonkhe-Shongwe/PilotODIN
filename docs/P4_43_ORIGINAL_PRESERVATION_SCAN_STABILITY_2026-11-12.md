# PilotODIN 1.0 | P4-43 Original-storage sequential scan stability guard

**Date:** 12 November 2026. **Phase:** P4 ACTIVE. **Risk addressed in source:** P4-R06. **Owner production-data integrity acceptance:** unchanged FAIL. **No owner-side command or installer required.**

## Finding

The original-data comparison script checked the independently preserved backup against the historical P4-22 baseline, scanned the current original data tree, hashed the original desktop EXE and finally classified file and directory changes. Those steps were sequential. An application-data mutation **after the first tree scan** could invalidate the reported state before completion without being detected. The script could consequently return a misleading `FULL_FINGERPRINT_MATCH` from an earlier observation. This is a theoretical/reproduced **synthetic comparison flaw**, not a finding that the owner's real application made a new write.

## Engineering change

[Commit `0ff0244093b5be05f7bcb0eb746d37811303c650`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0ff0244093b5be05f7bcb0eb746d37811303c650) updates `qa/p4_native/Compare_P4_Original_Storage.ps1` to compute the complete **backup, current data and original desktop EXE** fingerprints twice. `SameTree` compares total file count/bytes, file path-and-content hash, and **all directory path-set membership**, including empty directories. If any result differs, throw a fail-closed error without emitting a stable preservation verdict. Any established mismatch to the original baseline remains a FAIL even if scans happen to be stable. The output explicitly says `snapshot_is_atomic=false` and adds `sequential_rescan_consistent=true` for steady observations.

This is still **not a filesystem snapshot**: changing and reverting a file between reads, a write after the last read or historical writes cannot be ruled out. It is no basis for writer attribution, original app-data certification, 8 GB/offline Qwen or actual business safety. The original P4-22 baseline v1 schema/hash and independent backup are never rewritten.

## Disposable negative tests, CI and prior failures

`qa/p4_native/Test_P4_Original_Storage_Compare.ps1` now injects a deterministic synthetic mutation **after** the first backup/current scans by intercepting the first EXE hash inside a disposable PowerShell child scope. Two cases mutate a current project-data fixture or the independent backup fixture. Both must be rejected without a verdict; clean restore must reproduce the expected `FULL_FINGERPRINT_MATCH` with `snapshot_is_atomic=false`. The previously existing empty-folder, browser-cache, project SQLite/dataset drift, standalone EXE tamper and independent backup tamper tests still run.

Initial CI attempts failed in the **test harness**, not in the read-only comparator's business logic: [#43148792745](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43148792745) and [#43148981103](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43148981103) exposed a leaked/uninitialised global fake hash function; [#43149155782](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43149155782) passed PowerShell 7 but a PowerShell 5.1-specific cleanup assertion rejected the module command. Corresponding test corrections are [`78bc25c7`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/78bc25c7e73f37b39f9b7cf3fe043cf532f075fb), [`9304f217`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9304f2170f770247a3551485ee6fec63c59dd63c) and final [`e6803505`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/e680350500e1634b0599dc3926068439e37bb48b), which confines the interceptor to a child scope. Do not relabel earlier failures as passing.

**Final checked implementation:** [P4 Actions #43149480761](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43149480761) for `e680350500e1634b0599dc3926068439e37bb48b`, **COMPLETED SUCCESS 3/3**:

| Test | Direct log result |
| --- | --- |
| P4 Python suite | **150 passed** |
| Node contracts | **40 passed, 0 failed** |
| TS/Vite | **built successfully** |
| Chromium disposable real HTTP backend | **9 passed** |
| Windows read-only integrity and WebView | **PASS PowerShell 7.6.9 and 5.1.20348.5773**, includes current/backup post-scan race negatives |

This source-only CI does **not** use owner Windows files, launch a native Tauri desktop build, read actual business outcomes, fit/train models or download/build an EXE/MSI/NSIS installer.

## Remaining binding restrictions

Strict full original app-data preservation on the owner's previous evidence **FAIL**: 320 files in independent original backup compared to 346 observed in original application-data root; 74 changed items are *WebView/cache candidates* but the historical writer remains UNKNOWN. Prior exact original EXE/backup hash agreement and protected project data/ no-difference evidence do not prove complete preservation. The new second scan is **not yet run on owner hardware** and cannot retrospectively identify the writer or establish the historical directory state.

Real-world Gate C, latest native Windows UI parity, 8 GB offline Qwen and P4-R01–R06 remain OPEN. Owner explicitly declined closure by deferring risks and forbids intermediate installers until final stage. **P4 ACTIVE, P5 NOT AUTHORISED, P8 NOT CERTIFIED.**

**Next:** Only independently established owner Windows/data/business acceptance evidence can close remaining owner-dependent risk gates; avoid speculative source refactors or a risk waiver. Separate final-stage installer authorisation would be needed even after engineering passes.
