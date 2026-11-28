# PilotODIN P4 N12 | Stage 1 source-verified reference evidence worksheet

**21 November 2026 | Reference status: PARTIAL, not a full native green.**

This worksheet implements the [reference-first Stage 1 success contract](./P4_N12_STAGE1_GOLDEN_REFERENCE_AND_BACKWARD_VERIFICATION_2026-11-21.md): correctness requirement -> independently observed witness -> actual source function and predicate -> existing regression -> controlled counterexample -> gap. It is the first source-to-evidence worksheet, not a change to Windows process acceptance.

**Reviewed source:** [documentation HEAD 168b967](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/168b9670db26e97e075a86dbaef6b3dd92f1e396). **Last tested implementation:** [0511aca](https://github.com/Sonkhe-Shongwe/PilotODIN/commit/0511aca1e192ff4aa0950ac1255dcbd1b887b8f2), [CI #44903523887](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44903523887) 4/4 SUCCESS (970 Python passed, six skipped, 417 subtests, 104 frontend/Vite and hosted Windows AF_PIPE with synthetic subprocesses). These tests do not prove real native Stage 1 acceptance.

**Machine-readable traceability:** [S01-S11 reference map](./P4_N12_STAGE1_SOURCE_EVIDENCE_MAP_2026-11-21.json), with an automated consistency test at [tests/test_p4_n12_source_evidence_map.py](../tests/test_p4_n12_source_evidence_map.py). The test checks eleven real source functions, predicate strings, named existing regression functions, and fail-closed metadata. A passing worksheet test establishes traceability only.

## Independent actual evidence, not invented success

| Property | Real approved Stage 1 #44893498723 | Truthful classification |
| --- | --- | --- |
| Launcher original handle vs ETW payload | Exact original-handle birth and exit match | PARTIAL VERIFIED, launcher only |
| Main app original handle vs ETW payload | Exact original-handle birth and exit match | PARTIAL VERIFIED, app only |
| Sysmon Event 5 termination vs ETW payload | ETW later: launcher +32,932 ticks (3.2932 ms), app +77,625 ticks (7.7625 ms) | DISPUTED exact-cross-source predicate; not permission for a tolerance |
| WebView process events | Six WebView roles and one network role; Sysmon/ETW event evidence with exact ETW start images | OBSERVED roles, not an invariant of exactly seven |
| Independent retained original child handles | **None available** from that historic native capture | MISSING; cannot reconstruct retrospectively |
| ETW loss counters | Zero events/log/realtime buffers lost; five buffers written | Valid for that capture, not proof of observer polling completeness |
| Normal app close and profile | App started, became ready and closed ordinarily; protected endpoints MATCH | Real partial evidence; complete profile identity was BLOCKED |
| New private Windows pipe and abort | Windows AF_PIPE tested with synthetic Python process, not PilotODIN/WebView | SYNTHETIC ONLY |

[Actual native timestamp diagnosis](./P4_N12_STAGE1_NATIVE_SYSMON_ETW_EXIT_CLOCK_DIAGNOSIS_44893498723.md) and [last full N12 failure](../qa/p4_research/N12_APP_JOURNEY_RESULT_44838416004.md) govern those facts. Do not call the partial reference a complete green result.

## Source-to-evidence traceability

The exact named test, actual observed claim, positive variation, negative variation and unresolved gap for **each** row are in the JSON file. Each function below was checked against the current repository.

| Invariant | Exact source function | Predicate or failure label | Evidence state |
| --- | --- | --- | --- |
| S01: source/binary and isolated launch scope | [run_one_no_cdp_app](../qa/p4_research/n12_no_cdp_native_path.py) | no-cdp-app-launch-scope-unverified | Real scoped build/launch, new child observer not live-tested |
| S02: app/launcher original handles and ETW | [EtwLifetimes.find](../qa/p4_native/n12_exit_corroboration.py) | etw-and-windows-handle-timestamps-differ | PARTIAL REAL |
| S03: entire child GUID/ancestry inventory | [review_scoped_children](../qa/p4_research/n12_no_cdp_child_handles.py) | unexpected-app-descendant | PARTIAL REAL, original child handles missing |
| S04: independent original child query handles | [ScopedQaChildHandleObserver.sample_once](../qa/p4_research/n12_no_cdp_child_handles.py) | child-query-unavailable | SYNTHETIC ONLY |
| S05: exact original child handles versus ETW payload | [EtwLifetimes.shadow_handle_exit_review](../qa/p4_native/n12_exit_corroboration.py) | etw-original-handle-identity-or-clock-conflict | PARTIAL REAL for app/launcher |
| S06: undisputed Sysmon identity and ETW pair | [EtwLifetimes._no_cdp_sysmon_checks](../qa/p4_native/n12_exit_corroboration.py) | sysmon-exit-not-disputed | PARTIAL REAL, strict exit equality still blocks |
| S07: capture and chronology completeness | [verify_profile_shutdown](../qa/p4_research/n12_no_cdp_browser_identity.py) | no-cdp-profile-process-coverage-unverified | PARTIAL REAL loss counters |
| S08: normal close and independent descendant exit | [run_one_no_cdp_app](../qa/p4_research/n12_no_cdp_native_path.py) | no-cdp-app-did-not-exit-normally | PARTIAL REAL ordinary close |
| S09: private authenticated source-pinned transfer | [n12_private_child_pipe.decode](../qa/p4_research/n12_private_child_pipe.py) | no-cdp-child-pipe-provenance-invalid | SYNTHETIC ONLY |
| S10: justified cross-provider event-clock relationship | [EtwLifetimes._no_cdp_sysmon_checks](../qa/p4_native/n12_exit_corroboration.py) | etw-exit-exactly-matches-sysmon | DISPUTED by real native clock observations |
| S11: redacted diagnostic, never native acceptance | [private_child_handle_diagnostic](../qa/p4_research/n12_no_cdp_child_handles.py) | native_N12_acceptance | SOURCE/SYNTHETIC ONLY |

Every existing test named by the map validates **some source logic**, but test presence is not independent Windows evidence. Missing positive variations must not be claimed to have passed.

## Three concrete source-level questions requiring further proof

### Q1. Exact Sysmon Event 5 time equality

The strict source function EtwLifetimes._no_cdp_sysmon_checks requires Sysmon Event 5 UtcTime to equal the ETW process ExitTime exactly. In the last real run the app and launcher original Windows handles exactly matched ETW while their Sysmon termination timestamps differed. **This is an actual mismatch, not proof that either source is wrong.** Do not set an 8 ms tolerance from these two observations or disable strict checks.

Next source-only task: independent semantic analysis, signed timing/ordering variants, missing/disputed Sysmon exits, PID reuse, wrong full executable images and forged handle clock cases. Any proposed new rule needs a separate reviewed argument.

### Q2. Child born before observer sampling began

The worker in [n12_no_cdp_native_path.py](../qa/p4_research/n12_no_cdp_native_path.py) starts the child observer **after** spawning the app. Yet [private_child_handle_diagnostic](../qa/p4_research/n12_no_cdp_child_handles.py) requires evidence.sampling_started_ticks to be no later than witness birth. A child may legitimately be created immediately after app launch and still be alive when the observer first opens its original handle. That child would be rejected despite valid independent handle and ETW evidence.

**Classification: SOURCE-CONTRACT INCONSISTENCY RISK, NOT YET A REAL CAPTURE OBSERVATION.** Test the distinction between creation time, first observed time and original-handle retention before changing any predicate. Maintain unique PID+birth, source/binary, parent, image and capture-window checks.

### Q3. The role-mix invariant may be too specific

The source review_scoped_children currently demands both a webview role and a webview-network role. Our golden contract explicitly says do not hardcode the observed seven child processes. Whether both roles are universally required in the intended WebView2 QA workload is **not independently established**. Test valid alternate process trees with full independent coverage, along with missing/unbound roles. Never use a missing network child alone as proof of network isolation.

## Controlled test strategy, ranked

1. **Source-only reference variants:** Build S02/S05 app/launcher partial reference with only corroborated properties; explicitly mark all seven historical child original handles as **missing**, not empty-success. Add tamper and clock counterexamples.
2. **Source-only Q2 hypothesis tests:** Prove the pre-observer-born child counterexample while verifying parent/birth/image and capture-stage identity. Keep currently strict native admission untouched.
3. **Source-only clock and Q3 role review:** Separate independently required Windows behavior from assumptions in source predicates; write acceptance and rejection variants, not hardcoded sample-fitting.
4. **Future independent native capture, only with new explicit one-use source-pinned approval:** Assess whether real QA retains every original child handle and whether ETW/Sysmon timestamps can support a justified Stage 1 rule. A single native green becomes a regression reference only after independently validated correctness.
5. **Downstream R02.5/R02.6 and other P4 gates stay separate:** Even a true Stage 1 pass is not FileIO/network, owner-data, RAM inference or P4 closure evidence.

## Governance and current state

Native workflow remains **disabled (if: false)**, consumed one-use approval marker absent. No native app compilation, real WebView2 launch, owner-PC/data access, firewall enforcement, installer build, Stage 2 or change to native acceptance is authorized by this document.

Official score remains **P4 14/20 (70%)**, file-mutation engineering **3/4 (75%)**, R02.5 **0/5**, N12 **0/2**, desktop network **2/3**. [Current handoff](./SESSION_HANDOFF_CURRENT.md#next-engineering-action) and [Phase policy](./PHASE_FOCUS_AND_CLOSURE_POLICY_2026-10-28.md) remain binding.
