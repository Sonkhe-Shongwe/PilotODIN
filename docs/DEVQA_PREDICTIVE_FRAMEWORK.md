# PilotODIN DevQA: default workspace and predictive preflight v1

**Owner decision:** 26 October 2026. **Implementation:** source committed on `feature/live-dev-workspace-20261023`; actual Windows setup acceptance **PENDING**. This is a development-process capability, not a product milestone.

## Three separate kinds of state

| Location | What lives there |
|---|---|
| GitHub source branch | Tracked app source, QA tools, feature roadmap |
| `%LOCALAPPDATA%\PilotODIN\DevQA` | Local **synthetic QA** run folders, test exports, diagnostics |
| `docs/SESSION_HANDOFF_CURRENT.md` and Issue #2 | Permanent decisions, verified test evidence and exact next action |

The QA root is **not** PilotODIN's normal user project directory. The Windows setup launcher creates everything. No manual folder creation is needed.

### Per-run layout (automatically created)

```text
%LOCALAPPDATA%\PilotODIN\DevQA\
  runs\
    FRAMEWORK-V1-<UTC>-<random>\
      manifest.json
      workspace\
      fixtures\
      exports\
      logs\
      diagnostics\
  archive\
    FRAMEWORK-V1-<UTC>-<random>.zip
```

Each run is new; existing run files are neither overwritten nor deleted. A new future test launcher should use the run's **workspace** as its process-scoped `PILOTODIN_HOME`, not change the user's global environment. Its synthetic exports belong in that run's **exports** folder, and the verifier must still establish the **actual Windows Save As location** if users select somewhere else. No folder traversal, unrestricted cleanup or data imports into user projects.

## v1 owner setup

From the GitHub Desktop checkout, with any uncommitted changes preserved, run the single `Run_PilotODIN_DevQA_Foundation.bat`. It uses an already available `.venv-live\Scripts\python.exe` (or `py -3`), no dependency install. It calls `tools/qa_foundation.py check --phase FRAMEWORK-V1` to:
1. Safely create a unique local QA run and a risk-register manifest with `product_acceptance=NOT_TESTED`.
2. Execute **eight** targeted Python synthetic foundation unit tests (workspace isolation, uniqueness/no deletion, path protections, protected PowerShell variables, likely PDF/path/process failure signs, Python syntax and strict per-file hash).
3. Perform **read-only static preflight** against `tools/qa_foundation.py` and current representative `tools/Verify_P2_Native_Live_Report_Local.ps1`.
4. Produce a status-only diagnostic ZIP (result JSON + self-test log). It may contain test-local paths. It does **not** include user datasets.

Outcomes: `READY_FOR_SCOPED_TESTS` (setup source checks passed), `REVIEW_REQUIRED` (no blocker, but flagged risk needs developer judgement), or `BLOCKED` (test or source check failed). **None means application, Tauri, P2 or Windows release PASS.** The new preflight is conservative text scanning, **not a formal PowerShell semantic parser or guarantee of no bugs**; it does not execute old tests.

For an explicitly selected upcoming script, run `python tools/qa_foundation.py preflight tools/<script>.ps1` before asking the owner to test it. Run manifests preserve phase, pending checks and six risk questions. `qa_foundation.py init --phase <phase>` creates an additional QA run when a future launcher is deliberately integrated.

## Predictive development contract

Before new code, assess and scope the relevant risks below, including *a failure of the failure handler*. Avoid a long check for every possible theoretical bug.

| Risk | Evidence needed before Windows acceptance |
|---|---|
| PowerShell initialization | Avoid protected variables, test branching/early exceptions, diagnostics path known |
| Paths and filenames | New per-run default, saved **actual** OS location checked, strict expected basename |
| Repeated PDF generation | Test-only reproducibility when hash-checking across independent renders; no production guarantee |
| Original dataset & project integrity | Isolated synthetic `PILOTODIN_HOME`, hashes before and after |
| Cancel, partial write, server unavailable | Affected negative test + defined rollback and honest FAIL |
| Diagnostic/retry recovery | One status archive; rerun **only** an independent failing phase when possible |
| QA acceptance | Source preflight, owner-executed Windows evidence and released app acceptance tracked **separately** |

Workflow: current GitHub HEAD/handoff/QA -> define risk scenarios -> implement smallest change -> source/preflight -> scoped owner Windows gate -> evidence/continuity update. Never silently downgrade assertions because tests are inconvenient.

## What v1 deliberately does NOT do

It does not rewrite existing `Run_PilotODIN_P2_*.bat` launchers, automatically select a Windows native Save As folder, patch production React/Rust/FastAPI, start Qwen, consume hosted Actions, install packages or run an installer. Migrating the *next* selected P2 launcher to this run manager requires separate source review and actual Windows acceptance of the foundation first. There is no automatic cleanup or global OS state.

**P2 continuity retained:** Last full report-to-Tauri dev run completed six scoped owner PASS phases, but the follow-up read-only recovery found **both exact versioned HTML/PDF files missing in Downloads**. Final on-disk native byte integrity is **UNVERIFIED/FAIL** and must not be promoted by this tooling setup. E2 licensed offline Qwen+8 GB peak, general P5 scheduler, P6/P7 and P8/E-01–E-24 remain open.

**Next one owner action:** Pull latest feature branch preserving uncommitted changes, then run `Run_PilotODIN_DevQA_Foundation.bat` once. Share screenshot or the single diagnostics ZIP if blocked. This is the only owner run needed for this v1 setup check.

## Foundation v1 targeted hardening before first owner run (26 October 2026)

A focused source review identified two avoidable error-within-error risks, repaired in the QA framework **only**: (1) failure of Python test discovery previously could abort without producing a diagnostic result; the foundation now catches discovery/execution errors and reports BLOCK with a status archive, and records setup readiness in the run manifest while leaving `product_acceptance=NOT_TESTED`; (2) linked QA exports directories could redirect saved-file verification outside the intended synthetic run, so the verifier now rejects symlinks/junctions and hashes files in bounded 1 MiB blocks instead of reading whole outputs into RAM. Added two synthetic regression tests for both risks. **Actual owner Windows verification is still pending**. These changes do not migrate existing P2 launchers, fix the P2 missing versioned exports, or certify native Windows product behavior.

## First actual owner Windows setup result (26 Oct 2026)

Owner Windows screenshot of `Run_PilotODIN_DevQA_Foundation.bat` shows `SELF TESTS: 10 PASS` with a unique DevQA local run and archive, `QA FOUNDATION: REVIEW_REQUIRED (product acceptance NOT_TESTED)`. First foundation setup **ACCEPTED WITH REVIEW**. Sole flagged `SAVE-PATH` finding is true for the older P2 Native Live Report runner, which accepts relative text such as `Downloads` and fails its final path check. The diagnostics ZIP printed by DevQA has not been uploaded for direct inspection. The result does **not** certify P2, Tauri native output bytes or release acceptance. Proposed one-task migration: default a new P2 acceptance run to dedicated DevQA `exports`, check real original native names/hashes without ambiguous path prompts, handle alternate absolute destination only with explicit provenance and fail-closed evidence. This design has not been implemented as of this checkpoint. No existing QA evidence has been overwritten.
