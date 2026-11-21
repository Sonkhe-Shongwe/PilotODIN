# PilotODIN P4 | R02.5 file-mutation decision from actual N12 logs

**21 November 2026. Direct historical native-log audit plus source-only future reporting.** This is not a new native capture or an N12 acceptance result. Latest approved native capture is still [N12 #44838416004](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44838416004), completed 20 November UTC on reviewed code `e21bcdc579456bb02016fb0b2cb86744a287edb5`, with filesystem **FAIL**, network **FAIL**, file-mutation coverage **BLOCKED**.

## Why the 227,087 gap count was misleading as a next task

I reopened the **original completed GitHub Actions journey job log #136640497137**, not just the saved summary, and compared its original `N12 ordinary audit`, same-ETW `webview_credit_comparison`, and `N12 background FileIO comparison` payloads. The ordinary and the credited reductions both used ETW SHA-256 `cfa0aa13e8ea6312d27ae548f871d5b950201bceb9ecae41ea27aa525c02957d`. The independent background rundown reported its own digest `3230a7307eed1a750ed152c3ae55831d43e8e95f91f58eedd7260782436c7fd9`.

| Actual metric in the approved run | Count |
| --- | ---: |
| Original unresolved `webview-network:write:path-missing` | 227,087 |
| Same-capture request-time path credits in permitted roots | **226,959** |
| Same-capture path credits **outside** permitted roots | **113** |
| Residual WebView-network write path gaps in credit comparison | **15** |
| Original unresolved background (`other:write:path-missing`) | 4,190 |
| Background writes given path evidence by stop-time rundown | 78 |
| Background write paths **still** unresolved | **4,112** |
| Background write records with missing process lifetime | **42** |

**Verified arithmetic:** `226959 + 113 + 15 = 227087`, and `78 + 4112 = 4190`. These are independently computed reductions on the *same previously collected evidence*, not a new success for the PilotODIN application. The primary strict audit remains unchanged. The `webview_credit_comparison` was diagnostic and retained **filesystem FAIL, coverage BLOCKED, network FAIL**; its 113 newly attributed outside-scope writes increase the recorded known violation footprint rather than proving containment. **Do not simply relabel all previously unresolved WebView writes as permitted.**

## Exactly what still blocks R02.5

1. **Prohibited actual file operations:** The ordinary native audit lists 8 outside-scope WebView creates, 4 overwrites, 4 writes, 23 unsupported WebView operations, and 1 backend source-checkout write. The credited comparison adds **113 outside-scope WebView-network writes**. The backend CWD source mitigation is not verified in a new native capture; no policy exception has been approved. The 23 unsupported operations must be resolved or proven non-mutating with evidence, not silently excluded.
2. **Still-unattributed file operations:** 15 WebView-network writes remain unresolved after credit, plus 4,112 background writes and 42 background process-lifetime gaps. The rest of the ordinary categories, including 930 unresolved WebView writes, 298 backend writes and 1,327 background resizes, also remain in the credited report. Correctly identifying one dominant pair does **not** close whole-capture coverage.
3. **Completeness and prevention:** Protected endpoint hashes match, but do not show absence of write-and-restore. The existing proof architecture requires independently observed FileIO/loss/capture calibration plus credible protected-root prevention. The ProcMon A/B comparator still requires loss-reviewed evidence unavailable from its native wrapper. Do not hard-code `procmon_loss_reviewed=true` or reduce the monitored scope to make a pass.

## Implemented action, not more native captures

[Code `5ddb24b`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/5ddb24bfb065382307d8705116a82175af1334c8) adds a redacted `qa/p4_research/n12_mutation_triage.py` and source fixture tests, wired into the existing N12 journey output **after** the ordinary and the two comparisons. It checks exact event-credit arithmetic, unchanged other unresolved counts, no hidden previous violations, newly attributed outside-scope writes and matching ETW digest in the background comparison. It emits a fixed, redacted `mutation-triage.json` and one `N12 mutation triage` line on any **future separately authorised** native run. Invalid or incomplete comparison becomes `BLOCKED`. It does **not** change the strict native filesystem/coverage/network verdicts, close any issue, allow a path, launch an app or authorize a new run. Even fabricated perfect input cannot award acceptance.

[Exact-source routine P4 CI #44879307717](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44879307717), at `5ddb24b`, completed **4/4 jobs SUCCESS**: **890 Python passed, 6 skipped, 350 subtests, one warning**, **104 Node/frontend passed**, TypeScript/Vite build passed, **8 synthetic mutation triage tests**, Windows FileIO and ETW fixtures passed, **13 disposable real-HTTP browser tests passed**, and **4 R03 Windows tests passed**. No native PilotODIN WebView2 file write was measured.

## What will actually earn the final file-mutation point

**R02.5 is one official five-point P4 check** (not four equally scored subtests). File-mutation **3/4 (75%)** is an engineering substream tracker; overall P4 remains **14/20 (70%)**. The remaining R02.5 check requires **a fresh source-pinned, approved real native Windows journey**, with a complete positive calibrated FileIO trace, all protected roots unchanged, *zero* unapproved file mutations and *zero* unresolved mutation/identity/path evidence. Native firewall/network R02.6 is a separate remaining check.

**Next work should be a specific corrective change, not another general observer:** investigate the traced WebView2 user-local/user-temp outside-scope writes and the 113 known outside-profile request-time candidates, review whether the startup options or runtime itself can redirect or prevent them **without weakening the protected-path policy**, and verify the earlier backend source-checkout CWD correction. Prior raw user-local filenames were deliberately not retained; current saved logs do **not** permit inventing exact target names or claiming a specific root cause. Prepare the smallest source-backed product containment or diagnostic correction first, then request **fresh explicit one-use approval** for native verification. Existing one-use native workflows remain disarmed. No installer or owner data was touched.

**Official counts unchanged:** file-mutation **3/4**, desktop network **2/3**, N12 **0/2**, physical offline inference **1/3**, original-data preservation **0/2**, P4 **14/20 (70%)**.
