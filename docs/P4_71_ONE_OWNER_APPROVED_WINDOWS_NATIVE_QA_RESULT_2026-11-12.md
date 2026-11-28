# PilotODIN 1.0 | P4-71 One owner-approved isolated Windows native QA outcome

**12 November 2026.** Owner approved one isolated **unpackaged** Tauri developer build plus bounded acceptance on disposable Windows, **no installer, original owner files, owner PC, sidecar, Qwen, or model fitting**. Authorisation is **CONSUMED** by the successful single native compilation. It did not approve P4 closure, P5, P8 or release.

## Honest complete run chronology

| GitHub Actions run | Observed result | Native compilation? |
| --- | --- | --- |
| [#43276025772](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276025772) | FAILED on shallow checkout depth 1 before parent/source validation | **NO** |
| [#43276316744](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276316744) | PASSED two preflights, failed BEFORE compilation because PowerShell reserved variable HOME is case-insensitive | **NO** |
| [#43276839784](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276839784) | **COMPLETED SUCCESS**, 2/2 jobs; actual Windows native debug build + isolated process/profile smoke | **ONE** |

Final successful native compile is **exact source commit 8060d17b679d959d7b404a06a382d52ce20a8cf7**. The approval-controlled base source was fc20659e5fced50f046fee56a3b35334caa96fa3; intervening files were one-use QA-only workflow, runner script, trigger and Node WebView probe. Source/synthetic P4 workflow [#43276839718](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276839718) PASSED at the exact build source. Adjacent earlier P1 source [#43276025642](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43276025642) PASSED.

## Evidence matrix from actual Windows runner logs

| Test | Observed outcome |
| --- | --- |
| Production / prior QA / isolated native identifiers distinct and no inherited original storage | **PASS** both mandatory GitHub-hosted Windows 2022 preflights |
| Disposable Python backend on 127.0.0.1:8000 | **READY**, dev-only mode, no compiled backend sidecar or Qwen |
| Tauri unpackaged native debug executable | **PASS**, frontend/src-tauri/target/debug/pilotodin-desktop.exe |
| Native EXE binary identity | **18,318,848 bytes**, SHA-256 965fe3c4f125406b8f1b9d40528f58033aebe29c786b7e83abecaa8a3f493ebc |
| Native app / WebView2 process startup | **PASS**, 5 distinct WebView2 processes with isolated identity and isolated local app root present |
| Production and previous QA app roots during runner test | **ABSENT** before and after; limited to disposable hosted runner, NOT original owner's machine |
| WebView2 remote debugging endpoint | **READY** |
| Finding real native app page with Playwright at 127.0.0.1:5173 | **BLOCKED**, target page not found. Cause NOT established; alternative WebView URL/target, frontend loading or CDP attachment differences require proof |
| Native interactive P4 N2–N12, Quality version behavior, Prepare controls and UX parity | **NOT TESTED**. The probe stopped before creating synthetic projects or clicking any target controls |
| Actual physical 8 GB, sustained offline Qwen/analytics | **NOT TESTED** |
| Installer/NSIS/MSI, EXE transfer/upload, owner install, cloud use, model training | **NONE** |
| Historical owner whole-app-data tree | **STRICT FAIL UNCHANGED** (320 baseline files vs 346 observed, 74 browser/cache candidates, historic writer UNKNOWN). No original-data access or baseline rewriting |

**CRITICAL interpretation:** GitHub Actions SUCCESS **only** validates compiled native bootstrap and tested source-storage separation. It DOES NOT certify any P4 native UI/negative behavior, offline model, P4 Gate C or P4 exit. The native script intentionally treats its inability to attach to an expected dev page as BLOCKED rather than making a false PASS claim.

## One-use freeze and next evidence

One-shot native workflow **disarmed permanently** at [0639f425](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0639f425ee3c5b2c830c51a17a14ec40edcc4aa0), after final run dispatch. **Further native compilation requires fresh explicit owner approval.** Current run did not create an installer or any transferable build artifact. No physical owner Windows or original application data touched. No phase changes.

**P4 ACTIVE; P4-R01–R06 OPEN; original Gate C UNVERIFIED; original whole app-data historical STRICT FAIL; P5 NOT AUTHORISED; P8 NOT CERTIFIED.** A future separately approved interactive QA should first diagnose actual WebView2 CDP target/URL enumeration without inventing a cause or replaying this one-use compilation. Real 8 GB/offline Qwen and operational decision utility remain separate.
