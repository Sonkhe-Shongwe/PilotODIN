# PilotODIN P4 N12 | Reference-first Stage 1 success contract and backward verification

**Direction adopted:** 21 November 2026. **Status:** DESIGNED, NOT NATIVE-ACCEPTED.  
**Branch:** `feature/live-dev-workspace-20261023`. **Latest independently tested source at this decision:** [`0511aca1e192ff4aa0950ac1255dcbd1b887b8f2`](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0511aca1e192ff4aa0950ac1255dcbd1b887b8f2); [routine synthetic CI #44903523887](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44903523887) **4/4 SUCCESS**: 970 Python tests passed, 6 skipped, 417 subtests, 104 frontend and Vite, hosted-Windows *synthetic* AF_PIPE. Documentation edits after that source do not extend its tested scope.

## Decision and scope

Adopt the owner's **reference-first / backward verification** method. Establish a defensible, independently verified process-lifetime **correctness contract** and **evidence contract**; assemble a partial reference from actual observations; develop positive, negative and boundary fixtures from requirements; compare actual collector, observer, reducer and Windows evidence against those invariants; fix only supported deviations. A fixture that makes a verifier green is **not** evidence that Windows or PilotODIN behaved correctly.

This contract concerns **N12 Stage 1 isolated no-CDP native startup, unique process identities, full scoped WebView2 descendant lifetimes and normal profile shutdown**. It is a prerequisite to considering a native Stage 1 verifier decision, **not** R02.5 filesystem/FileIO, R02.6 network, R06 owner-data preservation, P4 closure or P8 release. Production model choice, number of WebView children and PID values are *not* fixed acceptance constants.

## Source-of-truth hierarchy

1. **Correctness:** Independently motivated Windows process identity, birth, exit, ancestry, ordering, loss and ordinary-close properties. Do not derive these rules solely from the current reducer's implementation or one trace.
2. **Actual evidence:** Previously approved [native lifetime diagnosis #44893498723](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md), full [N12 #44838416004](../qa/p4_research/N12_APP_JOURNEY_RESULT_44838416004.md), exact-source/binary manifest, Sysmon/ETW and original Windows handles where actually retained. The previous run does **not** provide historical original child handles.
3. **Implementation under audit:** `qa/p4_native/n12_exit_corroboration.py`, `qa/p4_research/n12_no_cdp_child_handles.py`, `qa/p4_research/n12_private_child_pipe.py`, `qa/p4_research/n12_no_cdp_native_path.py`, `qa/p4_research/n12_app_lifetime.py`. Code is a **candidate implementation**, not proof its assumptions are correct.
4. **Tests:** Generated/sanitized fixtures and hosted-Windows synthetic AF_PIPE validate code behavior **only within their scope**; they cannot award native PASS or retrospectively create handle evidence.
5. **Governance:** [P4 official scorecard](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard), [acceptance worklist](./P4_80_ACCEPTANCE_WORKLIST_AND_EVIDENCE_INTAKE_2026-11-12.md), [phase and owner consent policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) are unchanged.

## Reference evidence inventory, at the decision date

| Evidence | Actual observed reference | What can be claimed | What remains unverified |
| --- | --- | --- | --- |
| Main launcher original handle vs ETW | Exact birth and exit FILETIMEs match | Independent original-handle corroboration for launcher | Strict Sysmon event-5 `UtcTime` differs by **3.2932 ms** |
| Main PilotODIN app original handle vs ETW | Exact birth and exit FILETIMEs match | Independent original-handle corroboration for app | Strict Sysmon event-5 `UtcTime` differs by **7.7625 ms** |
| WebView2 process set | Six WebView and one network child observed in the last approved native lifetime run, Sysmon and ETW present | Scoped child events and exact ETW start-image path matches | **No original held child handles captured then**; the seven is an observation, not a required constant |
| ETW event loss | Zero reported events and log buffers lost; five buffers written | Completeness counters of that particular capture | Not a guarantee that every future child is captured by the 10-ms polling observer |
| Source pipeline | Source-only child observer, diagnostic reducer and authenticated memory-only pipe integrated | Tested synthetic one-shot transport, rejection and abort behavior | No **real PilotODIN/WebView child capture** at this latest source |
| Profile endpoint preservation | Protected snapshot comparison MATCH in last lifetime run | Endpoint match for that capture | Cannot certify no transient write-and-restore; no full N12 FileIO/network pass |

**Reference state: PARTIAL GREEN FOR SPECIFIC INDEPENDENT APP/LAUNCHER PROPERTIES; NOT ONE FULL GREEN STAGE 1.** Real Stage 1 remains **BLOCKED**. Do not label the latest synthetic CI success as a successful native reference.

## Success invariants and code-to-evidence traceability

| ID | Invariant required for a *candidate* correct Stage 1 execution | Independently required evidence | Owner code / verification surface | Status |
| --- | --- | --- | --- | --- |
| S01 | Source, binary and isolated runner/profile are uniquely pinned, default-off and authorized | Exact reviewed source, executable SHA-256, disposable scoped root, first-attempt hosted identity and fresh separate consent | Native launch preflight; `n12_no_cdp_native_path.py` | Source guards; real new approval **not** held |
| S02 | Exactly one original app process and its launcher are bound; no PID-only or stale joins | Original retained handles, Sysmon GUID/PID/image, ETW sequence, birth comparison | `n12_app_lifetime.py`; `n12_exit_corroboration.py` | App/launcher historically corroborated |
| S03 | Every relevant WebView2 descendant is included, regardless of child count | Independent full Sysmon GUID inventory plus ETW ancestry/unique start and stop; no unbound descendants | `n12_no_cdp_child_handles.py`; profile identity verifier | Real original children **missing** |
| S04 | Every child has a distinct original process query handle captured while still alive | Exact PID+birth, parent PID, full DOS/native image, retained handle after exit; no duplicated/reused PID | `ScopedQaChildHandleObserver` | Synthetic tests only; 10-ms sampling can miss |
| S05 | Each original exit is actually corroborated, not inferred solely from event clocks | Handle `GetProcessTimes` exit + independent ETW stop, identity and chronology; fail on mismatched FILETIME | Shadow handle review; strict `EtwLifetimes.find()` | App/launcher observed; children pending |
| S06 | Independent Sysmon process creation/termination events are consistent with identities and bounded capture | Unique GUID exits and images; capture bounds, parent sequence, no disputed or missing exits | `EtwLifetimes` and source gate | Exact cross-source exit equality still blocks |
| S07 | Source coverage and event order are complete | ETW/Sysmon loss review, unique event sequence, no overlapping PID lifetime, launch < ready < close < profile exit | Reducer + session/manifest | Invariant tested; native acceptance unproven |
| S08 | Normal app close and complete descendant/profile exit, including early children | Original app normal return, bounded profile identity shutdown, all observed child exits and absent extra contenders | `n12_no_cdp_native_path.py` and browser identity | Only partial prior native proof |
| S09 | No incomplete, tampered or source-mismatched witness can produce positive evidence | Fail-closed message schema, auth, max size, start/end markers, collector faults and rejected duplicate | `n12_private_child_pipe.py`, private diagnostic | Hosted Windows synthetic PASS, not native |
| S10 | Any revised Sysmon/ETW clock rule has independent documented justification | Windows event semantics, handle counterexamples, signed source deltas and adversarial tests | Proposed specification change **only after evidence review** | **NOT JUSTIFIED**; original exact rule remains |
| S11 | Scope-specific provenance, privacy and negative results survive handoff | Fixed-label redacted diagnostics; raw identifiers remain private; source-only tests never earn gate points | Reporting, audit and official status | Partial source-only evidence |

**Ordering caveat:** Genuine correctness need not require child exit ordering to mirror child start order. What matters is unique verifiable identity, plausible individual lifetimes, valid ancestry and complete capture boundaries. Do not hardcode exactly seven children, a particular PID, one WebView2 version, or an arbitrary 8 ms tolerance.

## Repeatable reference-based test matrix

| Test | Controlled variation to reference or independent fixture | Expected |
| --- | --- | --- |
| G01 | Preserve all independently supported fields of a complete future native reference, after separate approval | Candidate positive under *independently justified* rules; not auto native PASS |
| G02 | Substitute different valid child count/order with full identity and origin | ACCEPT only if all invariants remain demonstrably true |
| N01 | Remove one original child handle while keeping Sysmon/ETW GUID | BLOCK |
| N02 | Duplicate original child PID/birth or replay old PID with new birth | BLOCK |
| N03 | Wrong parent GUID/PID/sequence, missing ancestor or child outside app tree | BLOCK |
| N04 | Wrong executable DOS/native image, shortened ETW stop without full independent confirmation | BLOCK |
| N05 | Remove ETW start/stop, Sysmon exit or introduce overlap/duplicate sequences | BLOCK |
| N06 | Inject nonzero ETW loss or unsupported capture window/order | BLOCK |
| N07 | Mismatch original-handle FILETIME vs ETW stop or forged clock value | BLOCK |
| N08 | Child starts/exits wholly between 10-ms polls and no held original handle exists | BLOCK; sampler success is not completeness |
| N09 | Wrong binary/source, altered private pipe message, extra fields, wrong auth | BLOCK |
| N10 | Crash sender, fail readiness, abort observer, no original handle release | BLOCK and clean up |
| B01 | Preserve realistic nonzero Sysmon-vs-ETW exit differences seen in the native observation | **Strict current verifier still BLOCKS** until semantics independently resolved; never change tolerance from one sample |
| B02 | Record early/late event headers, truncated ETW stop name and valid/invalid parent chronology | Require distinct independent source checks; never infer identity from prefix alone |
| B03 | Observe a new child not in the reference inventory | Either independently include and corroborate it or BLOCK; never silently ignore |

**Fixture provenance rule:** Archive only privacy-safe synthesized or redacted **derived** reference fixtures, with explicit `synthetic` vs `real-observed` labels, source SHA, schema and generator version. Original owner/device evidence and raw process identifiers must not enter public repository fixtures. Each test must assert its expected failure label, not merely that an exception occurred.

## Work backward in this order

1. **Audit the verifier predicates, not just its PASS strings.** Make an evidence/invariant/implementation matrix and identify which predicates are direct Windows guarantees versus unvalidated assumptions. The currently disputed predicate is exact **Sysmon Event 5 `UtcTime` equals ETW process payload `ExitTime`**.
2. **Build a partial reference from the app and launcher evidence that actually exists**, with absent child handles explicitly recorded as missing. Reproduce existing positive and negative source behavior without silently fabricating a complete green capture.
3. **Use deterministic failing variants to classify the failure:** broken observer/capture, wrong event identity/chronology, actual unexpected lifecycle, or an unjustified cross-source equality requirement. For any suspected spec defect, write a documented independent semantics argument before changing the gate.
4. **Design the smallest independent real native question:** Does this exact source retain original query handles for *every* WebView2 child and corroborate the ETW FILETIMEs while ordinary close occurs? Define full source/binary/runner, coverage/fault and redaction criteria first.
5. **Require a NEW explicit one-use source-pinned owner approval** before activating, compiling or launching a native Windows/Tauri/WebView sample. Without approval, continue only source/synthetic reasoning and tests.
6. **After any approved capture**, accept a baseline only when independent evidence justifies its correctness. Freeze sanitized invariants and generate multiple positive/negative/boundary fixtures; never claim one green run proves all real Windows variants.
7. **Separate N12 Stage 1 from full P4 acceptance.** After successful independent Stage 1, R02.5 filesystem/FileIO, R02.6 network and R06 owner-data gates still need separate unchanged verification.

## Red lines / non-goals

- No temporary "8 ms" or blanket tolerance, no dropping missing WebView2 children, no matching solely by PID, profile path or truncated image, no invented reference trace, and no green based on synthetic fixtures alone.
- Do **not** widen allowed roots, rewrite historical failure results, promote `REVIEWABLE_ONLY` to PASS, turn on the native workflow, restore a consumed approval marker, start Stage 2 or run a Windows installer.
- Do not describe the retrospective app/launcher partial success as an approved full Stage 1 pass.

## Decision milestones

| Milestone | Required proof | Current |
| --- | --- | --- |
| M0: Direction and success-contract audit | Requirements mapped to sources and negative controls; historic evidence retained | **This document, design only** |
| M1: Independently reviewed partial golden reference | App/launcher original-handle/ETW parity, correct source identity and truthful missing-child markers | **Evidence available; reusable fixture not yet built** |
| M2: Full real native child reference | New consented isolated native capture, original handles for every independent child GUID, zero source coverage loss | **NOT DONE** |
| M3: Defensible clock semantics and strict verifier rule | Independent argument and positive+adversarial tests, no unjustified threshold | **NOT DONE** |
| M4: Native Stage 1 verified at exact source | Fresh consented native run accepted under justified unchanged or separately reviewed strict gate | **BLOCKED** |

**Current authoritative score remains [P4 14/20 (70%)](./PROJECT_STATUS_CURRENT.md#p4-engineering-scorecard)**; internal file-mutation 3/4, R02.5 0/5, N12 0/2, network 2/3. This reference strategy does not award acceptance or retroactively alter the last native failures.
