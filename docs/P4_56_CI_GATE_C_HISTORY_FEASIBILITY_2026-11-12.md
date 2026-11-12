# PilotODIN 1.0 | P4-56 Gate C internal CI decision feasibility audit

**Date of evidence:** 12 November 2026. **Scope:** READ-ONLY GitHub REST/connected GitHub records and prior repo Gate C policy. **NO model fitting, workflow execution, new CI, native build, installation, access to original owner Windows app/data, paid service, new business-owner consent or gate waiver.**

## 1. Original Gate C policy, not rewritten to fit our data

Controlling [P4-50 minimum real-business evidence intake](./P4_50_EVIDENCE_INTAKE_AND_SINGLE_NATIVE_READINESS_2026-11-12.md) and [P4-46 closure policy](./P4_46_CLOSURE_EVIDENCE_AND_DECISION_BOUNDARY_2026-11-12.md) require: **a legitimate decision and accountable owner; independently verifiable real outcome/label provenance; documented prediction moment and feature availability; entity/time separation; fair measurable existing-process baseline; measured decision costs, errors and benefit; lawful use, safeguards, signoff**.

The user rejected reliance on unreturned Capital Bikeshare cold outreach and approved *investigation* of a real PilotODIN-owned CI decision. This audit investigates eligibility. It does **not** assert an approved independent business use case, owner signoff, causal utility or Gate C PASS merely because user is repository maintainer.

## 2. GitHub primary data actually reviewed

Repository: [Sonkhe-Shongwe/PilotODIN](https://github.com/Sonkhe-Shongwe/PilotODIN), branch `feature/live-dev-workspace-20261023`. Verified current branch head before this audit: `2963ba321d23a34632a7ba2204b744a019dd0d8a`.

GitHub Actions API reported **1,079 runs** filtered to this branch. A naive `per_page=100` request with pages 1–11 exposed only the first **1,000**, although `total_count` remained 1,079. To retrieve all **1,079 distinct run IDs**, partitioned by immutable **created date**, then paginated:

- `GET /repos/Sonkhe-Shongwe/PilotODIN/actions/runs?branch=feature%2Flive-dev-workspace-20261023&created=2026-10-01..2026-10-23&per_page=100&page=1` -> **4**.
- Same endpoint `created=2026-10-24`, pages 1–5 -> **446**.
- Same endpoint `created=2026-11-03..2026-11-12`, pages 1–7 -> **629**.
- These windows are non-overlapping and sum to 1,079. No runs were reported for 25 Oct–2 Nov in this branch history. Data availability is **a 20-day recent development-history snapshot**, not the entire lifetime of the repository.

The retrieved records contain workflow name, run ID, `head_sha`, event `push/pull_request`, statuses/conclusions, created/run-started/updated timestamps and run attempt. Count each run ID once, never impute a conclusion for a queued/cancelled/skipped run.

| Branch run result | Count |
| --- | ---: |
| Successful | **762** |
| Failed | **207** |
| Cancelled (censored, NOT failures) | **101** |
| Queued (unknown outcomes, NOT failures) | **8** |
| Skipped (NOT failures) | **1** |
| **Total** | **1,079** |

**969 completed success-or-failure runs**; raw *run-level* failure proportion `207/969=21.36%`. This is **not** a commit-level defect prevalence, future failure probability, root-cause attribution or a reliable candidate model's measured accuracy.

- **453 distinct `head_sha` values**, far fewer than 1,079 runs. **267 commits** have multiple runs; **186** have one. **125 SHAs** have one or more failure, including **68 that also have a successful workflow** and 57 with failure but no success in the observed snapshot. These are not independent labelled examples without defining a specific workflow and attribution.
- **26 different workflow names** with radically different intended checks and trigger/cancellation behaviour; `883 push` and `196 pull_request` events. All observed `run_attempt=1`; this does **not** prove absence of retries elsewhere, because separate corrective commits occur.
- Time concentration: **446 runs / 104 failures on 24 Oct**, **177 runs / 27 failures on 5 Nov**. Together **623/1079=57.74%** of all runs and **131/207=63.29%** of failure runs. Any random split would leak neighbouring development episodes and overstate generalisation; chronology/group isolation is mandatory.
- Completed successful runs have median about **61 seconds**, failed runs median about **45 seconds**, computed as `updated_at - run_started_at`. Sum of all recorded failed-run elapsed times ~**2.94 hours**, but these elapsed measurements are NOT staff debugging time, billable compute minutes, time-to-fix, or business costs. A two-minute extra manual review of all 453 distinct commits would require **906 minutes (15.1 hours)** before any claimed time saved. It is not valid to infer net benefit by directly comparing these unlike quantities.

### Candidate workflow concentration (completed outcomes only)

| Workflow | Total runs | Success | Failure | Cancelled | Other | Unique SHAs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 Isolated Frontend Verification | 214 | 126 | 31 | 57 | 0 | **214** |
| Live Development Fast Checks | 198 | 148 | 50 | 0 | 0 | 100 |
| Build E - Frontend Compilation | 160 | 115 | 45 | 0 | 0 | 99 |
| Live Development Backend Regression | 92 | 83 | 9 | 0 | 0 | 92 |
| P2 Report Export Draft Safety | 70 | 43 | 22 | 5 | 0 | 70 |
| P4 Target Review Queue and Transparent Ranking | 65 | 53 | 6 | 5 | 1 queued | 65 |

**Provisional choice for an instrumentation/shadow study, NOT a trained target:** **P1 Isolated Frontend Verification**, because 214 runs correspond to 214 separate SHAs, instead of many duplicate executions of the same SHA. **BUT** 57/214 were cancelled, 31 confirmed failures and 126 confirmed successes; cancellations remain separate, and a limited recent history will not prove forecast generalisation. The workflow is not independently approved as an operational business objective.

## 3. Real failure/job-step and pre-run commit evidence, not imagined classification

A bounded, cross-date, cross-workflow diagnostic retrieved **18 failed run job summaries** and **9 decoded failed-job logs** (24 Oct, 5 Nov, 9 Nov, 12 Nov). This is a **targeted qualitative sample**, NOT a randomly representative distribution or exhaustive root-cause analysis. Examples:

| Observed source | Verifiable event | What it permits / what it does not |
| --- | --- | --- |
| [Run 40104754453](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/40104754453), commit [2800f3a](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/2800f3a89e8005612187b8d1f461187e3a91f3e9) | Workflow source `.github/workflows/frontend-compile.yml` only changed; run failed TypeScript `TS18047` on `src/QualityWorkspace.tsx` | GitHub failure and specific diagnostic are real. The changed workflow file is **not** that TS component; failure is not proof the pushed change introduced a code defect |
| [Run 40102343550](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/40102343550) | Frontend behavioural test `scatter view offers real zoom/pan...` failed | Real failing contract/test. Code-defect responsibility and time to fix **not independently established** |
| [Run 42108740549](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42108740549), commit [de3be2](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/de3be2394b4defe7384a3207d2e11e434d268780) | A **test-only change** tightening report handoff assertions triggered failure | Deliberate stronger tests may be intended to expose pre-existing gaps; do not label all such red runs as avoidable new regressions |
| [Run 42075292011](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42075292011) | Disposable browser comparison failed a visibility assertion | Another distinct failure category; requires triage |
| [Run 42679079261](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/42679079261), commit [9e6b39](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/9e6b39bac32ec60582b612cfeeac9600da57d264) | TypeScript `TS2304` on `mountedIsHeldArchived` after a UI fix | True source-build failure; no human debugging-duration proof |
| [Run 43173363772](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43173363772) | Existing Python regression assertion failed following a stricter identifier-screen change; later source correction recorded in P4-48 | Behavioural regression example, not an independent benchmark of lost engineer time |
| [Run 43195506498](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/43195506498), [corrected by later source](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/cd7ce3d000c3c69f67cadacde6f8445e7bee68cf) | Public bike research-script wrong file path, `FileNotFoundError` before fitting; following corrected run succeeded | True research orchestration failure, not an application defect or an operational business incident |

Additional verification: **8 sample commit detail records** expose change-path lists, change counts, message and commit time **before the corresponding GitHub workflow starts** in this observed sample. A candidate pre-push decision could therefore use diff/paths and original commit content as features, but this sample does **NOT** verify availability and capture for all 453 SHAs, nor whether the developer would have acted differently.

**Critically, the existing repository records do not independently capture:**
- An actual pre-push/manual **review decision** for each change and its timestamp.
- Review effort or CI-failure **human remediation minutes** with a reliable audit trail.
- Whether a particular failure was caused by the pushed change versus an existing unrelated problem, an expected tightening of tests, CI resource pressure, or configuration.
- Counterfactual results of performing an extra preflight review versus the existing baseline of running CI as usual.
- Business costs, interruptions or owner-approved objective thresholds.

## 4. Research go/no-go

**Data provenance: qualified PASS for descriptive evidence.** GitHub run outcomes, commit metadata and job-step logs are genuine, externally timestamped records that can be independently fetched. Exact meaning of post-run `conclusion` is understood.

**Prediction target and independence: NOT READY.** "any workflow fails" is ambiguous across 26 different jobs and multiple same-SHA runs. A narrower fixed-workflow definition such as "this P1 source verification fails" is feasible to *investigate*, but cancellations are censored and root-cause/expected-test labels have to be independently audited. Chronological commit grouping is essential.

**As-of feature timing: partly supported.** Pre-push source diffs and test files can be known in advance; the user actually needs a review rule **before push or before initiating a manual check**. Post-run logs, eventual conclusion, fix-commit history and future branch-state must never be input features. Do not infer future developer behaviour from the final Git history.

**Decision/action: plausible but unproven.** Owner could decide to run specific focused preflight checks or perform risk-based review **before pushing**. The standing CI workflow remains enabled; do not skip or suppress safety verification based on model predictions. A human-maintainer claim is not automatically independent approval of a legitimate business use case.

**Measured decision utility / fair baseline: FAIL / NOT SUPPLIED.** No recorded actual action, human-debugging time, missed defect costs, measured baseline review effort, or prospective benefit. GitHub wall-clock duration alone cannot establish labour savings or ROI. Any fitting now would create another predictive score, not Gate C evidence. No model was fitted here.

**Verdict: CI use case is eligible for a small prospective measurement pilot, NOT Gate C closure. P4-R01 remains OPEN.**

## 5. Frozen prospective shadow study protocol; no monitoring was activated

**Purpose:** Determine whether an owner-controlled pre-push **targeted extra check** can be justified compared with the existing standard CI workflow, without touching native Windows or the protected app. This is a plan, not a launch of monitoring, an altered CI trigger or a promise of data collection in the background.

1. **Before a new push or requested PR verification, record:** decision time (ISO timestamp), SHA or reproducible patch identifier, branch, base SHA, changed paths, source/test/workflow categories, an objective `extra_preflight_recommended` yes/no and a one-sentence rationale. The recommended rule must be frozen before seeing the new CI outcome; no use of job logs, eventual status, future fixes or current branch head.
2. **Keep ordinary CI unchanged.** Initially use **shadow-only** risk recommendations that do not change checks, and record which additional targeted check would have been requested; do not automatically run scripts, alter workflows or deploy a model. For changes already tested elsewhere, separately record the existing review evidence.
3. **After CI concludes, separately log:** exact run IDs/workflow ID, completed outcome versus cancellation/queue, failed job step(s), whether failure is new/actionable or expected/pre-existing/infra, and how that classification was independently checked. Never silently turn censored results into a success.
4. **Record measured time:** actual human preflight review minutes (if review is later explicitly trialled), existing no-review process, human diagnosis/fix minutes, build/runner elapsed metrics separately, and severity/false-alarm/impact. Missing time remains **NOT SUPPLIED**, not 0.
5. **First feasibility checkpoint:** aim for a limited **20–30 distinct new changes** over varied days, only to test whether logging is complete and categories can be consistently labelled. This count is **NOT** an acceptance pass threshold, statistical sample-size guarantee, permission for another model fit, or proof of measurable benefit. Do a sample-size and measurement-design review before a later controlled intervention comparison.
6. **Any eventual intervention trial:** require separate owner authorisation, predeclared measurable utility threshold, consistent baseline and time windows, no weakening of existing safety checks, report false positives and negatives, and independent reproducibility/review. If costs overwhelm the benefits or no genuine business objective exists, record **NO SUITABLE OBJECTIVE** and leave Gate C OPEN.

**Suggested owner confirmation item (not signed yet):** Who makes the actual pre-push decision; which extra check is permitted; expected time cost; what qualifies as an avoidable CI incident; and whether an internal non-revenue software engineering workflow genuinely satisfies the P4 business Gate C charter. A scope change needs explicit approval rather than silently rewriting the gate.

## 6. Preservation and P4 phase decision

The GitHub API reads did not invoke any GitHub Actions workflow, run a model, create a runnable app, install native artefacts, access original owner-machine paths, delete a cache, rebaseline or modify any private data. The later publication of this **report** is a documentation action only and cannot be called another CI acceptance pass.

**P4 ACTIVE, R01–R06 OPEN, P5 NOT AUTHORISED, P8 NOT CERTIFIED.** In particular historical R06 entire original app-local-data **STRICT FAIL** persists (trusted 320 vs observed 346 files, 74 browser/cache *candidates*, historical writer UNKNOWN). P4-47 native compilation single-use authority consumed. One-off P4-55 public research fit authority consumed. No cache waiver or original safety-risk deferral has been granted.
