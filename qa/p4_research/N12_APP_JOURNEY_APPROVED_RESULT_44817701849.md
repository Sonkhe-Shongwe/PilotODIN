# N12 one-use hosted Windows acceptance | Run 44817701849

**Decision:** No acceptance award. The one specifically approved run completed its two native app journeys but the combined ETW filesystem reducer **BLOCKED** on `ETW event timestamp outside capture`. The earlier filesystem FAIL, network FAIL and coverage BLOCKED remain governing. No retry is authorised by this record.

## Provenance and scope

- Date (UTC): 20 November 2026. Workflow: [P4 N12 Hosted App Journey](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44817701849), run attempt 1, hosted `windows-2022`.
- Frozen reviewed source: `cb8eae6324edcc2336948d5de1630bf4d5a75f40`; activation commit: `d2df3ac6d311895e661b98bca4b5a046fdb18178`.
- Isolated unpackaged QA executable SHA-256: `718710178cd7f22f972b9ab758f62ec1fca3c98fcda36b047b2b878504fcb438`.
- Cargo.lock SHA-256: `cc57cfd0f4fffd9e851dc957cd196895a61fc029a306e5876045e54dfaab1104`.
- Sysmon 15.22 with prechecked Microsoft download SHA-256: `83d31f2478dc6716cfdbf69e5c384bf043072b5f0d8d7b2eea365f709fda4352`.
- Scope: one unpackaged host build, generated CSV, disposable backend and QA storage, native WebView2, Sysmon and ETW. No original owner data, intermediate installer, physical 8 GB run or firewall enforcement. The source checkouts and build receipt passed.

## Public log evidence, by stage

| Stage | Recorded result | Acceptance implication |
| --- | --- | --- |
| One-use source gate, generated prebuild calibration, dependencies and driver syntax | PASS | The gate checked out the approved parent source before staging |
| Native executable compilation and provenance | PASS | Binary and Cargo.lock digests recorded above |
| ETW start, complete protected before-scan | Completed | Both scans were inside the ETW and governing audit interval according to capture markers |
| Initial Sysmon calibration | PASS on read 1 | Controlled generated TCP and UDP fixture observed |
| First native launch/exit and second native relaunch/exit | Completed | Both driver invocations returned successfully; this does **not** award app-wide N12 credit |
| App journey and process cleanup | Completed | The driver stage reached its close-and-reopen path |
| Final generated Sysmon fixture | PASS on read 1 | Final calibration succeeded |
| Protected after-scan | Completed; **MATCH** | No protected endpoint changes; immutable generated Quality source also matched. Intermediate writes are **not** ruled out by matching hashes |
| ETW stop, Sysmon export, Sysmon reduction, ETW export | Completed | Capture artifacts reached the combined reducer |
| Combined ETW reduction | **INTERRUPTED** | `ETW event stream: ETW event timestamp outside capture`. The event direction, count, type and timing distance were not published, so no mechanism is established |
| Governing N12 audit verdict | **NOT PRODUCED** | No R02.5 filesystem PASS and no R02.6 network PASS; no points awarded |

The network diagnostic **before** combined reduction recorded two non-loopback WebView UDP events to port 53 and one non-loopback WebView TCP event to port 443, plus one unexpected backend loopback and two unexpected WebView loopback port-80 events. One backend event-loop wakeup matched a same-process socket pair. It also reported `app-lifecycle-does-not-match-journey`. These are diagnostics, **not** a completed governing network audit. The observed non-loopback connections require an enforcement/attribution decision; they cannot be declared safe or policy-compliant from these records alone.

## Evidence restrictions and next engineering decision

1. Keep `ETW event timestamp outside capture` as a **fail-closed capture-evidence blocker**, not an app product regression proven by this run. Do not silently discard, clamp or extend events, change protected allowlists or turn the failed reduction into a PASS.
2. Reproduce out-of-bounds timestamps **offline** with generated event streams at the `etw_events` schema boundary. Add a small safe classification (before-start vs after-end, relative offset band, event IDs and counts) with no raw path, PID or row values. Capture/ETW boundaries and export provenance must remain verified. Validate underflow, overflow and loss cases. Run routine synthetic CI only.
3. Independently investigate the `app-lifecycle-does-not-match-journey` Sysmon comparison and the unexpected backend/WebView sockets. Do not assume a timing adjustment repairs the network policy. Any live egress firewall check still needs its own approval.
4. Another native journey requires **fresh, source-pinned, one-use owner approval**, a specifically changed blocker and a predicted observable difference. Never rerun this approval attempt.

**Unchanged score:** product-audit fixes 7/7; file-mutation coverage 3/4 (75%); desktop network isolation 2/3 (67%); original owner-data preservation 0/2; N12 acceptance 0/2; official P4 **14/20 (70%)**.

[Workflow log and stage evidence](https://github.com/Sonkhe-Shongwe/PilotODIN/actions/runs/44817701849) · [Current handoff](../../docs/SESSION_HANDOFF_CURRENT.md)
