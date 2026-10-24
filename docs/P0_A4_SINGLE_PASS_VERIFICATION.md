# PilotODIN P0 closeout -> A4 readiness: consolidated local checkpoint

**Status:** Verification tooling committed; not yet executed on owner's Windows checkout. This is NOT A3/A4 sign-off or a release build.

## Why this exists

Replace multiple A2/A3 pull/run/screenshot cycles with a single local checkout and one reproducible command. The automation validates the existing deterministic A2/A3 and reporting/export foundations before A4 development; it deliberately does not claim full UI, installer, actual 8 GB or local-Qwen acceptance.

## One owner action (after development batch)

1. In GitHub Desktop select branch `feature/live-dev-workspace-20261023`, then **Fetch/Pull** the finished checkpoint once. Do not discard local modifications.
2. Double-click `Run_PilotODIN_P0_A4_Verification.bat` from the repository root; alternatively run the isolated environment's `python.exe tools/Verify_P0_A4_Readiness.py`.
3. Read the final `AUTOMATED P0/A4 READINESS: PASS/FAIL` result. The command prints a temporary results folder containing `result.json`, separate phase logs and Pytest JUnit XML. Share only the failure summary or redacted relevant logs if the run fails. Logs are local and are not uploaded automatically.

## Tool contract

- Uses exactly the existing `.venv-live\Scripts\python.exe` and `frontend/node_modules`; no implicit package installation.
- Requires the correct working branch and validates the known A2/A3 regression test file inventory.
- Creates unique temporary `PILOTODIN_HOME` and never accesses the existing production data directory through the test environment.
- Runs frontend behavioural tests, one TypeScript/Vite production build, one backend syntax pass, then one deduplicated combined backend pytest pass.
- Includes A2 Quality/Explore/report evidence, A3 ML and prediction, plus data-export and approval regressions already present in the repository.
- Logs every phase (including failures), exits nonzero if any fail and records the commit being evaluated.
- Does not use GitHub Actions, download models, build an installer, create a GitHub release, approve data changes or update QA automatically.
- Some tests may touch synthetic local test fixtures or use TestClient; do not conflate with a UI/hardware result.

## Gate for proceeding to A4 implementation

**Automated P0/A4 readiness:** all four phases pass on an up-to-date, clean commit and any failing data-integrity/ML assertions are repaired. After automated tests pass, carry out one deliberately short real Windows smoke session using a disposable project to confirm:
1. A3: Prepare > Model > Evaluate > Predict, valid incident hour 12, and impossible 25 rejected (the latter already observed previously); prediction correctly displays result and warnings.
2. A3: reopen saved experiment into Evaluate, inspect held-out baseline and bounded feature sensitivity.
3. A2: saved Explore evidence reopens in project and is available in Deliver without leaking across projects.
4. A4: create report with verified evidence, save revision, export HTML/PDF, and inspect legibility, version labels and same figures. Check native Save As behaviour separately in a desktop build when native shell is available.

**If a gate fails:** fix and rerun the smallest failing automated scope first, then one final consolidated run. Do not repeatedly ask the owner to pull minor commits. No claim of full macro sign-off without corresponding evidence.

**Deferred, not waived:** full native desktop/installer, WebView2 offline payload, bundled inference generation, concurrent ML + AI on physical 8 GB, all 24 Build E acceptance scenarios, broad accessibility and crash/upgrade recovery. A bounded early E2 feasibility test is still an architectural obligation, independent of this A4 gate.

## Why A4 is not from scratch

Existing `backend/reports.py` persists immutable report revisions and locally renders HTML/PDF. `frontend/src/ReportWorkspace.tsx` already provides a report editor and evidence selection. Existing regressions cover revision fidelity, cross-project evidence restrictions and HTML/PDF source values. A4 should improve experience and evidence coverage without replacing those verified contracts.

## Tracking

Latest pre-tooling A3 fix: `aff63899a46f` (group/time split-key exclusion). Its post-fix local regressions were unexecuted at the last QA entry. This tooling must not change that historical evidence. Report actual run results in Master QA Issue #2 only after the owner completes verification.

Related: `docs/CONTINUE_HERE.md`, `docs/MACRO_A2_CONSOLIDATED_ACCEPTANCE.md`, `docs/MACRO_A3_ML_ACCEPTANCE.md`, `docs/PILOTODIN_CONSOLIDATED_ROADMAP_COMPLEXITY_LAST.md`.
