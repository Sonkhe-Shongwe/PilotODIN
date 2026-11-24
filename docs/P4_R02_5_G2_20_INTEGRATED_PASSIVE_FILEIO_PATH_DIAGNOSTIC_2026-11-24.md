# R02.5 G2.20 | Integrate bounded passive name-epoch evidence in actual no-CDP FileIO reducer

24 November 2026. Source-only change. No native execution or new permission.

## Why this is different from another standalone feasibility checkpoint

The actual no-CDP app lifetime runner already invokes `n12_no_cdp_fileio_review.reduce` with its source-pinned, digest-verified ETW export. Previously this call did not enable the existing `webview_write_candidates` / dominant pair request-time name-epoch diagnostic. Its missing-path totals alone could not identify how many could be classified as a candidate path under the same capture.

G2.20 enables that existing diagnostic at the actual reducer call. No `webview_write_credit` or `credit_webview_path` callback is supplied. **No mutation/path credit is earned**. No new collector, native process API, raw trace export, installer, or protected-root change.

The new fixed-schema receipt reconciles strict network missing write-path count, eligible candidates, checked candidates, candidate lexical scopes (permitted/outside/protected), checked without a candidate, eligible but unchecked, and strict gaps ineligible for this diagnostic. Existing bounded top-two dominant pairs and retention limits are explicit. Missing results, invalid accounting, and ETW loss do not yield candidate counts. Raw outcome keys are not emitted. Zero path gaps in the strict reducer is not a physical-destination guarantee. The existing strict reducer's violations and gaps are not reduced or overwritten.

## Gate closure decision

G2 is **not complete**. The original file-handle-to-FileObject/IRP relation remains unproved. G2.18's socket-unsafe foreign duplication route remains blocked. The current passive lexical path mechanism is useful for prioritizing G3 investigations, not sufficient for the existing G2 original-file-handle or full-coverage requirements.

Next decisive step is a single, separately approved, source-pinned disposable hosted Windows baseline with the integrated reducer, existing calibration and write/restore arms, no arbitrary handle duplication, no owner data, no installers, no raw evidence upload. This can establish which original blockers actually remain. It cannot be promised to close G2 if the original file-handle witness is absent. Consumed native permissions are not reusable. Do not change G2 exit criteria without an explicit review.

Scores unchanged: four-gate 1/4 (25%), official R02.5 0/5, N12 0/2, P4 14/20 (70%).

## Exact source verification

[Source `8c2d456a1978145d10af1da86caf97053b07a1b3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8c2d456a1978145d10af1da86caf97053b07a1b3) passed [R02.5 source-only CI #45341086645](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45341086645), including regressions for unchanged strict gap/violation counts, candidate count reconciliation, privacy-safe fixed labels, loss blocking and pair-limit exhaustion. No actual native Windows capture was executed. G2 remains OPEN. The source is ready for a separately scoped baseline approval; this is NOT an assurance of G2 exit.

## Owner-approved native execution

**24 NOVEMBER 2026 | G2.20 ACTUAL-APP BASELINE AUTHORISED AND ACTIVATED:** Owner explicitly authorised the single previously scoped disposable hosted Windows diagnostic. Reviewed source [`35aa9f0`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/35aa9f080a394c7578a1a0255f4414bb59b29395); activation [`8437e93`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/8437e93180c2d5243f9f16a21491f8f04cd3abcb) changed only the guarded workflow and added fresh marker `qa/p4_research/N12_NO_CDP_FILEIO_OWNER_APPROVAL_20261124_G220_ONE_USE.txt`. Immediately disarmed [`6736752`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/6736752619f1704b8222521a0dbdf874c4b75f4c); marker retained as consumed. [Native run #45342345634](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45342345634) confirmed attempt 1, in progress at initial check. One unpackaged staged binary, calibration, one no-CDP startup/exit, retained query-only child lifetimes, ETW/Sysmon, write/restore and bounded passive request-time path diagnostic. No arbitrary original browser handle duplication, personal data, installer, raw trace upload, allowance change or retries. Normal build dependency/network traffic and possible WebView2 egress remain within the expressly approved hosted baseline. No result or acceptance assumed. G2 remains OPEN, four-gate **1/4 (25%)**, official R02.5 **0/5**, N12 **0/2**, P4 **14/20 (70%)**. Next: inspect actual terminal run result and fixed-label receipt before deciding further work. Original file-handle criterion still required.

