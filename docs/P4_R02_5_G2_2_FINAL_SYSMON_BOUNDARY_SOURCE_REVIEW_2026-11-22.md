# PilotODIN P4 R02.5 | G2.2 final Sysmon boundary failure and source-only correction

**22 November 2026.** Read-only diagnosis of consumed native run [#45041259808](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45041259808), followed by a **source-only** correction and synthetic regression coverage. NO second native run, no new capture consent or acceptance credit.

## Verified results of the one-use Windows run

- Reviewed source `166dfa39efa6a1629c35cc4c2c6c3fc740078c3c`; exact activation `58f72bf3e226b2a1d87ab11a6fe3727f424268b4`; first attempt only.
- GitHub job status: **COMPLETED FAILURE**. Approval guard, Python/Node/dependency preflight and isolated **unpackaged** Windows build succeeded.
- The initial generated Sysmon calibration **PASSED on read 1** (unlike the prior missing-Event-3 failure). The `app-lifetime-worker` and `no-cdp-same-capture-write-and-restore` checkpoints were **completed**. This proves stage execution, not successful FileIO mutation containment, protected-root verification, or full report.
- The **final** Sysmon fixture was `interrupted` on read 1 by `parent-birth-before-window`. Its redacted fixed-count diagnostic reported one outside-window candidate; Sysmon birth stamp minus final start `-4710` 100 ns ticks (approximately -0.471 ms), generated parent creation minus start `+5279` ticks (approximately +0.528 ms), and Sysmon stamp minus creation `-9989` ticks (approximately -0.999 ms). This is **consistent with millisecond timestamp truncation**, not proof that the fixture or real app ran early.
- ETW stop and failure-path endpoint checks completed. There is **no complete fixed-label FileIO report** in the GitHub summary. No raw ETW evidence or private paths were uploaded. The owner's one-use consent is **consumed**.
- Immediately following activation the workflow was independently disarmed in `5a4c14d7cfa8f9af003ef22c19b55ab43488d5b0`. Do not rerun the consumed job or reactivate the old marker.

## Mechanism and smallest safe correction

- The existing initial fixture uses `run_initial_calibration()`: record the audit window first, then wait `INITIAL_FIXTURE_LEAD_IN_SECONDS = 0.05` s before creating the generated calibration parent. The final fixture in `n12_app_lifetime.capture()` previously recorded `final_start = journey.now()` and immediately spawned the parent with no lead.
- Sysmon ProcessCreate timestamps use the `UtcTime` field, which may be quantised at millisecond precision. A process created just after a submillisecond start can therefore appear just before it. Historical strict tests require `parent-birth-before-window` to BLOCK; we **must not simply accept out-of-window events**.
- A source-only `verify_final_calibration()` helper records the final window **before** a 50 ms generated-fixture lead-in, then performs exactly one existing `journey.calibrate` and one unchanged strict `journey.verify_fixture_sysmon`. Window start/end values are handed to the same original verifier without tolerance expansion. The original app lifecycle, Sysmon event parsing, reducer, file roots, native approval and workflow remain unchanged.
- The synthetic tests verify correct window/delay/fixture/check order, sub-millisecond rounding, propagated final verification failure and no verification after fixture failure. The G2 static preflight now checks both historical and newest consumed markers, and the source-only Linux workflow runs these tests.

## Remaining limitations and decision

- This is a hypothesis-driven source correction, **not confirmation on Windows**. It does not prove TCP/UDP final calibration, actual file handle/IRP/path attribution, zero ETW loss, protected snapshots, or N12 acceptance.
- Real WebView2 child **process** handles are not original WebView2 **file** handles. Even if the next independently approved baseline passes both bookends, G2 original-file-handle evidence is still missing.
- Further Windows execution requires an entirely **new source-pinned one-use owner approval**. Do not reactivate consumed workflow, widen scope or automatically rerun.
- G1 PASSED. **Delivery tracker 1/4 = 25%, G2 OPEN**. R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**, historical file mutation engineering **3/4 (75%)** unchanged.

## Source-only verification

The Linux-only CI workflow is run on exact published source; record its verified conclusion separately before claiming the patch is tested in GitHub. No desktop app or native collector is invoked by this change.
