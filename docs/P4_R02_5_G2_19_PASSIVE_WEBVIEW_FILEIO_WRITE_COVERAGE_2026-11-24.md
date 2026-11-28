# PilotODIN P4 R02.5 G2.19 | Passive WebView2 FileIO request/completion shape coverage

**24 November 2026 | SOURCE ONLY. No WebView2 launch, foreign HANDLE duplication, ETW collection, original owner data or installer.**

## Reason for the change

The historical original N12 product result still has unresolved WebView2 network and background FileIO paths and incomplete lifetime evidence. G2.18 revoked the unsafe plan to duplicate unclassified browser handles. The existing pure `n12_fileio_pair_contract.py` already indexes numeric Kernel File operation/IRP/FileObject information without preserving private paths, but its `_by_irp` index only retained events whose IRP was present and nonzero. A future passive coverage report based only on `_by_irp` would silently omit precisely the writes whose IRP was missing.

## Integrated code, not a separate synthetic harness

- `PrivatePairIndex` now retains a **private write-row mapping by PID** for every Kernel File Write event 16, including missing or zero IRP. This shares the same single full-stream parse and schema guards as the existing original-file pair reducer. It preserves no private path in the index or public results.
- `passive_webview_write_coverage(index, writer_epochs)` consumes that already-built index and a bounded, explicitly **untrusted** tuple of up to 96 role/lifetime claims (`webview` and `webview-network`). It gives fixed per-role *counts*, never raw PIDs, paths, FileObjects, handles or ETW payload. The elapsed-clock and role input is **not authenticated** by this helper.
- It counts **all** selected write requests and classifies each as: `pair_shape_only`, missing/ambiguous/reused IRP, unsuccessful/unknown completion, absent/conflicting writer/object identity, or outside supplied process lifetime. It examines an entire capture's IRP history to avoid crediting an otherwise convenient slice of a reused operation ID. Completion PID may be system context. Missing completion FileObject/FileKey does not contradict the request, but never supplies independent provenance.
- A well-formed, uniquely completed operation is only `SHAPES_REVIEWABLE_ONLY` and always reports original handle, kernel-to-handle join, physical destination and loss/completeness **NOT VERIFIED**. The first gap makes the summary `BLOCKED`. An empty set of target writes cannot be interpreted as full containment.
- This is an O(number of indexed write events plus process claims) summary after indexing; dense repetitive FileObject traffic is assessed by IRP, not repeatedly walked by object. A source-only 15,000-write synthetic burst exercises the intended large-stream shape.
- The **strict original N12 path/actor/containment reducer is unchanged**. No G2.13/14/15 workflow changes, native activation or consent marker. Existing G2.18 socket-safe ban remains.

## Acceptance gap

This detects *syntactic* request/completion holes on independently supplied ETW-shaped data, not whether actual WebView2 processes were fully captured or which path a write reached. Before G2, a separately authorised original app capture must bind original writer process sequence and thread, original FileObject/IRP and successful completion to a verified request-time physical destination with zero unresolved mutation coverage, independently calibrated loss, complete child lifetimes and protected-owner safety. Do not promote this synthetic summary or a clean count to R02.5 acceptance.

**Before and after official status:** P4 **14/20 (70%)**, N12 **0/2**, R02.5 **0/5**, G1–G4 **1/4 (25%)**. Engineering mutation **3/4 (75%)**. P5 and intermediate installers remain disallowed.

## Source CI completion | 24 November 2026

[Commit `d624aec63d272581dc7b4b0e660e38cb3351f0a3`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/d624aec63d272581dc7b4b0e660e38cb3351f0a3) passed the full [R02.5 FileIO source-only contract #45333948777](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/45333948777), including G2.19's new negative request/completion, missing IRP and privacy tests and a 15,000-write generated burst. The CI result verifies Python source behavior only; it **does not** verify full historical WebView2 writer coverage or an original native Windows run. No native permissions, workflow markers, installer or strict N12 verdict changed. G2 remains open.
